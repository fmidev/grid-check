#!/usr/bin/env python3

import eccodes as ecc
import gribapi
import sys
import os
import argparse
import yaml
import numpy as np
import logging
import copy
from random import randrange
from datetime import datetime, timedelta

import pydash

class TestNotImplementedException(Exception):
    pass


def get_index_keys():
    return [
        'typeOfProcessedData',
        'typeOfFirstFixedSurface',
        'level',
        'discipline',
        'parameterCategory',
        'parameterNumber',
        'typeOfStatisticalProcessing',
        'endStep',
        'perturbationNumber'
    ]


def get_default_value(keyname):
    if keyname == 'typeOfProcessedData':
        return 1  # deterministic
    elif keyname == 'typeOfFirstFixedSurface':
        return 103  # height
    elif keyname == 'level':
        return 0


def forecast_type_from_grib(gid):
    ty = ecc.codes_get_long(gid, 'typeOfProcessedData')

    if ty == 0:
        return "analysis"
    elif ty == 1:
        return "deterministic"
    elif ty == 3:
        return "control/%d" % ecc.codes_get(gid, "perturbationNumber")
    elif ty == 4:
        return "perturbation/%d" % ecc.codes_get(gid, "perturbationNumber")
    else:
        return "unknown"


def index_grib_files(grib_files):
    logging.info("Indexing grib files")
    index = {}

    index_keys = get_index_keys()
    cnt = 0
    for grib_file in grib_files[0]:
        with open(grib_file) as fp:
            message_no = 0
            offset = 0
            while True:
                gid = ecc.codes_grib_new_from_file(fp)
                if gid is None:
                    break

                ref = index
                for k in index_keys:
                    try:
                        val = ecc.codes_get_long(gid, k)
                    except gribapi.errors.KeyValueNotFoundError as e:
                        val = None

                    if val not in ref:
                        ref[val] = {}
                        ref = ref[val]
                    else:
                        ref = ref[val]

                length = ecc.codes_get_long(gid, 'totalLength')

                ref['file_name'] = grib_file
                ref['message_no'] = message_no
                ref['length'] = length
                ref['offset'] = offset
#                print(ref)

                message_no += 1
                offset += length
                cnt += 1

    logging.info(f"Indexed {cnt} messages from {len(grib_files[0])} file(s)")

    return index


def read_grib_message(index, conditions):
    index_keys = get_index_keys()
    leaf = index
    for ikey in index_keys:
        found = False
        for item in conditions:
            if item['Key'] == ikey:
                try:
                    leaf = leaf[item['Value']]
                except KeyError as e:
                    return None
                found = True
                break
        if not found:
            logging.debug("Data not found from index")
            return None

    return leaf


def read_sample(grid, sample_size):
    if grid is None:
        return None

    if '%' in str(sample_size):
        sample_size = int(int(sample_size[:-1]) * 0.01 * grid.size)
    return np.random.choice(grid, sample_size)


def string_to_timedelta(string):
    if string[-1] == 'h':
        return timedelta(hours=int(string[:-1]))
    t = string.split(":")
    return timedelta(hours=int(t[0]), minutes=int(t[1]), seconds=int(t[2]))


def timedelta_to_grib2metadata(td):
    d = {
        'Grib2MetaData': [{
            'Key': 'endStep',
            'Value': int(td.total_seconds() / 3600)
        }]
    }

    return d


def generate_leadtimes(leadtime_configs):
    leadtimes = []
    for cfg in leadtime_configs:
        current = string_to_timedelta(cfg['Start'])
        stop = string_to_timedelta(cfg['Stop'])
        step = string_to_timedelta(cfg['Step'])

        while current <= stop:
            leadtimes.append(current)
            current += step

    leadtimes.sort()
    return leadtimes


def format_metadata_to_string(metadata):
    string = ""
    for m in metadata:
        string += "%s=%s " % (m['Key'], m['Value'])

    return string


def read_data(grid):
    with open(grid['file_name'], "rb") as fp:
        fp.seek(grid['offset'], 0)
        buff = fp.read(grid['length'])
        fp.close()

    gid = ecc.codes_new_from_message(buff)

    values = np.array(ecc.codes_get_values(gid))
    ecc.codes_release(gid)

    return values


def read_grids(index, parameters):
    grids = {}
    for param in parameters:
        grid = read_grib_message(index, parameters[param]['Grib2MetaData'])
        if grid is not None:
            logging.debug(
                f"Read {format_metadata_to_string(parameters[param]['Grib2MetaData'])}")
            grids[param] = read_data(grid)

    diff = list(set(parameters) - set(grids.keys()))

    if len(diff) > 0:
        for param in diff:
            logging.warning(
                f"Unable to find data for '{param}': {format_metadata_to_string(parameters[param]['Grib2MetaData'])}")
        return {}

    return grids


def preprocess(grids, test):
    if len(grids.keys()) == 0:
        return None
    try:
        prep = test['Preprocess']
        locals().update(grids)
        return eval(prep)

    except NameError as e:
        logging.fatal(f"Invalid preprocessing function: {prep}: {e}")
        sys.exit(1)

    except KeyError as e:
        if len(grids.keys()) > 1:
            logging.fatal(
                "Don't know how to merge multiple grids without preprocessing directive")
            sys.exit(1)
        return list(grids.values())[0]


def execute_envelope_test(test, forecast_types, leadtimes, parameters, files):
    ret = {
        'success': 0,
        'fail': 0,
        'skip': 0,
        'summary': []
    }

    for ft in forecast_types:
        lparameters = inject(copy.deepcopy(parameters), ft)
        for lt in leadtimes:
            lparameters = inject(lparameters, timedelta_to_grib2metadata(lt))

            sample = read_sample(preprocess(read_grids(
                files, lparameters), test['Test']), test['Sample'])

            if sample is None:
                ret['skip'] += 1
                continue

            smin = np.amin(sample)
            smax = np.amax(sample)

            emin = test['Test']['MinAllowed']
            emax = test['Test']['MaxAllowed']

            retval = 0
            word = ""

            if smin < emin or smax > emax:
                retval = 1
                word = "not "

            ret['summary'].append(
                {
                    "return_value": retval,
                    "message": f"Forecast type: {format_metadata_to_string(ft['Grib2MetaData'])} Leadtime {lt} Min or max [{smin:.2f} {smax:.2f}] is {word}inside allowed range [{emin:.2f} {emax:.2f}], sample={sample.size}"
                })

            if retval == 0:
                ret['success'] += 1
            elif retval == 1:
                ret['fail'] += 1

    return ret


def execute_variance_test(test, forecast_types, leadtimes, parameters, files):

    ret = {
        'success': 0,
        'fail': 0,
        'skip': 0,
        'summary': []
    }

    for ft in forecast_types:
        lparameters = inject(copy.deepcopy(parameters), ft)
        for lt in leadtimes:
            lparameters = inject(lparameters, timedelta_to_grib2metadata(lt))

            sample = read_sample(preprocess(read_grids(
                files, lparameters), test['Test']), test['Sample'])

            if sample is None:
                ret['skip'] += 1
                continue

            svar = np.var(sample)

            minvar = None
            maxvar = None
            try:
                minvar = test['Test']['MinVariance']
                maxvar = test['Test']['MaxVariance']
            except KeyError as e:
                pass

            if minvar is None and maxvar is None:
                continue

            retval = 0
            word = ""

            if (minvar != None and svar < minvar) or (maxvar != None and svar > maxvar):
                retval = 1
                word = "not "

            ret['summary'].append(
                {
                    "return_value": retval,
                    "message": f"Forecast type: {format_metadata_to_string(ft['Grib2MetaData'])} Leadtime {lt} Variance {svar:.2f} is {word}inside given limits [{minvar} {maxvar}], sample={sample.size}"
                })

            if retval == 0:
                ret['success'] += 1
            elif retval == 1:
                ret['fail'] += 1

    return ret


def execute_test(test, forecast_types, leadtimes, parameters, files):

    ty = test['Test']['Type']

    if ty == "ENVELOPE":
        mina = test['Test']['MinAllowed'] if 'MinAllowed' in test['Test'] else None
        maxa = test['Test']['MaxAllowed'] if 'MaxAllowed' in test['Test'] else None

        logging.info(
            f"Executing {ty} test '{test['Name']}', allowed range: [{mina}, {maxa}]")

        return execute_envelope_test(test, forecast_types, leadtimes, parameters, files)
    elif ty == "VARIANCE":
        minv = test['Test']['MinVariance'] if 'MinVariance' in test['Test'] else None
        maxv = test['Test']['MaxVariance'] if 'MaxVariance' in test['Test'] else None

        logging.info(
            f"Executing {ty} test '{test['Name']}', allowed variance: [{minv}, {maxv}]")

        return execute_variance_test(test, forecast_types, leadtimes, parameters, files)
    else:
        raise TestNotImplementedException(
            "Unsupported test: %s" % test['Test'])


def inject(conditions, injected):

    if 'Grib2MetaData' in injected:
        injected = injected['Grib2MetaData']

    for inj in injected:
        for k, v in conditions.items():
            g2meta = v['Grib2MetaData']
            for item in g2meta:
                if inj['Key'] == item['Key']:
                    # if injecting time, check if parameter is lagged
                    if inj['Key'] == 'endStep' and 'Lag' in v:
                        lagged = int((timedelta(
                            hours=inj['Value']) - string_to_timedelta(v['Lag'])).total_seconds() / 3600)
#                        logging.debug(f"Lagging time {inj['Value']} to {lagged}")
                        item['Value'] = lagged
                    else:
                        item['Value'] = inj['Value']
                    found = True
                    break
            if not found:
                g2meta['Key'] = inj['Value']

    return conditions


def tie(req_parameters, parameters):
    ret = {}

    names = []

    try:
        names = req_parameters['Names']

    except KeyError as e:
        pass

    try:
        for name in names:
            ret[name] = parameters[name]

    except KeyError as e:
        logging.fatal(f"Required parameter is not defined: {e}")
        sys.exit(1)

    try:
        meta = req_parameters['Grib2MetaData']

        if len(ret.keys()) == 0:
            randi = randrange(100)
            ret[f"anon_{randi}"] = {}
            ret[f"anon_{randi}"]['Grib2MetaData'] = meta

        else:
            # for parameters
            for name in ret:
                replaced = False
                for newkey in meta:
                    for i, k in enumerate(ret[name]['Grib2MetaData']):
                        if k['Key'] == newkey['Key']:
                            ret[name]['Grib2MetaData'][i] = newkey
                            replaced = True
                    if replaced == False:
                        ret[name]['Grib2MetaData'].append(newkey)

    except KeyError as e:
        pass

    index_keys = get_index_keys()

    # must have value for all index keys

    for ikey in index_keys:
        for k, v in ret.items():
            g2meta = v['Grib2MetaData']
            found = False
            for item in g2meta:
                if item['Key'] == ikey:
                    found = True
                    break
            if not found:
                # add default value
                default = get_default_value(ikey)
#                logging.debug(f"Add default value for {k}: {ikey} => {default}")
                ret[k]['Grib2MetaData'].append({'Key': ikey, 'Value': default})

    return ret


def check(config, dims, files):
    success = 0
    fail = 0
    skip = 0

    return_code = 0
    for test in config['Tests']:
        summaries = execute_test(test, dims['forecast_types'], dims['leadtimes'], tie(
            test['Parameters'], dims['parameters']), files)

        success += summaries['success']
        fail += summaries['fail']
        skip += summaries['skip']

        if len(summaries['summary']) == 0:
            logging.info("No grids checked")

        for summary in summaries['summary']:
            retval = int(summary['return_value'])
            if retval > return_code:
                return_code = retval

            if retval == 0:
                logging.debug(summary['message'])
            else:
                logging.error(summary['message'])

    logging.info(
        f"Total Summary: successful tests: {success}, failed: {fail}, skipped: {skip}")

    sys.exit(return_code)


def parse_forecast_types(config):
    forecast_types = []
    try:
        for ft in config['ForecastTypes']:
            rng = None
            ty = None

            for item in ft['Grib2MetaData']:
                if item['Key'] == 'perturbationNumber':
                    if '-' in str(item['Value']):
                        start, stop = item['Value'].split('-')
                        rng = range(int(start), int(stop) + 1)
                    else:
                        rng = [int(item['Value'])]
                if item['Key'] == 'typeOfProcessedData':
                    ty = item['Value']
                    rng = [None]

            for x in rng:
                d = {
                    'Grib2MetaData': []
                }
                d['Grib2MetaData'].append(
                    {'Key': 'typeOfProcessedData', 'Value': ty})
                d['Grib2MetaData'].append(
                    {'Key': 'perturbationNumber', 'Value': x})
                forecast_types.append(d)

        return forecast_types
    except KeyError as e:
        logging.fatal("'ForecastTypes' must be defined")
        sys.exit(1)


def parse_leadtimes(config):
    leadtimes = {}
    return generate_leadtimes(config['LeadTimes'])


def parse_parameters(config):
    parameters = {}
    try:
        paramdefs = config['Parameters']
        for pdef in paramdefs:
            if 'Parent' in pdef:
                pdef['Grib2MetaData'] = copy.deepcopy(
                    parameters[pdef['Parent']]['Grib2MetaData'])
                pdef.pop('Parent', None)
            parameters[pdef['Name']] = pdef
    except KeyError as e:
        return None

    return parameters

def apply_patch_to_configuration(config, patches):
    for patch in patches:

        (k,v) = patch.split('=')
        element = pydash.get(config, k)

        if element is None:
            logging.debug("PATCH: Adding element {}={} to configuration".format(k,v))

        if v == 'None':
            pydash.unset(config, k)
        else:
            pydash.set_(config, k, v)

    return config


def parse_configuration_file(configuration_file, patch):
    config = None
    with open(configuration_file, 'r') as fp:
        try:
            config = yaml.safe_load(fp)
        except yaml.YAMLError as exc:
            logging.fatal(exc)
            sys.exit(1)

    if patch is not None:
        config = apply_patch_to_configuration(config, patch)

    return config, parse_forecast_types(config), parse_leadtimes(config), parse_parameters(config)


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configuration", type=str,
                        help="configuration file for checker", required=True)
    parser.add_argument("-p", "--patch", type=str, action='append',
                        help="modify configuration file with in-line options", required=False)
    parser.add_argument("-d", "--log-level", type=int,
                        help="log level 1-5", default=4)
    parser.add_argument(
        "files", type=str, help="input files to check", action='append', nargs='+')
    args = parser.parse_args()

    if args.log_level == 1:
        args.log_level = logging.CRITICAL
    elif args.log_level == 2:
        args.log_level = logging.ERROR
    elif args.log_level == 3:
        args.log_level = logging.WARNING
    elif args.log_level == 4:
        args.log_level = logging.INFO
    elif args.log_level == 5:
        args.log_level = logging.DEBUG

    return args


def main():
    args = parse_command_line()
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=args.log_level,
        datefmt='%Y-%m-%d %H:%M:%S')

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        args.configuration, args.patch)

    dims = {
        'forecast_types': forecast_types,
        'leadtimes': leadtimes,
        'parameters': parameters
    }

    check(config, dims, index_grib_files(args.files))


if __name__ == "__main__":
    main()
