#!/usr/bin/env python3

import eccodes as ecc
import gribapi
import sys
import os
import argparse
import yaml
import numpy as np
import pprint
import logging
from random import randrange
from datetime import datetime, timedelta


class EnvelopeTestException(Exception):
    pass


class GribMessageNotFoundException(Exception):
    pass


class TestNotImplementedException(Exception):
    pass


def get_index_keys():
    return ['typeOfProcessedData', 'typeOfFirstFixedSurface', 'level', 'discipline', 'parameterCategory', 'parameterNumber', 'forecastTime', 'perturbationNumber']


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
                    val = ecc.codes_get_long(gid, k)
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
    #            print(kv)

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


def timedelta_from_string(string):
    t = string.split(":")
    return timedelta(hours=int(t[0]), minutes=int(t[1]), seconds=int(t[2]))


def timedelta_to_grib2metadata(td):
    d = {
        'Grib2MetaData': [{
            'Key': 'forecastTime',
            'Value': int(td.total_seconds() / 3600)
        }]
    }

    return d


def generate_leadtimes(leadtime_configs):
    leadtimes = []
    for cfg in leadtime_configs:
        current = timedelta_from_string(cfg['Start'])
        stop = timedelta_from_string(cfg['Stop'])
        step = timedelta_from_string(cfg['Step'])

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
    #    print(grid)
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

        return eval(prep)  # np.hypot(grids['U'], grids['V'])

    except KeyError as e:
        if len(grids.keys()) > 1:
            logging.fatal(
                "Don't know how to merge multiple grids without preprocssing directive")
            sys.exit(1)
        return list(grids.values())[0]


def execute_envelope_test(test, forecast_types, leadtimes, parameters, files):
    ret = []

    for ft in forecast_types:
        for lt in leadtimes:
            sample = read_sample(preprocess(read_grids(files, inject(inject(
                parameters, ft), timedelta_to_grib2metadata(lt))), test['Test']), test['Sample'])

            if sample is None:
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

            ret.append(
                {
                    "return_value": retval,
                    "message": f"Forecast type: {format_metadata_to_string(ft['Grib2MetaData'])} Leadtime {lt} Min or max [{smin:.2f} {smax:.2f}] is {word}inside allowed range [{emin:.2f} {emax:.2f}], sample={sample.size}"
                })

    return ret


def execute_variance_test(test, forecast_types, leadtimes, parameters, files):

    ret = []
    for ft in forecast_types:
        for lt in leadtimes:
            sample = read_sample(preprocess(read_grids(files, inject(inject(
                parameters, ft), timedelta_to_grib2metadata(lt))), test['Test']), test['Sample'])

            if sample is None:
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

            ret.append(
                {
                    "return_value": retval,
                    "message": f"Forecast type: {format_metadata_to_string(ft['Grib2MetaData'])} Leadtime {lt} Variance {svar:.2f} is {word}inside given limits [{minvar} {maxvar}], sample={sample.size}"
                })

    return ret


def execute_test(test, forecast_types, leadtimes, parameters, files):

    ty = test['Test']['Type']
    logging.info(f"Executing {ty} test '{test['Name']}'")

    if ty == "ENVELOPE":
        return execute_envelope_test(test, forecast_types, leadtimes, parameters, files)
    elif ty == "VARIANCE":
        return execute_variance_test(test, forecast_types, leadtimes, parameters, files)
    else:
        raise TestNotImplementedException(
            "Unsupported test: %s" % test['Test'])


def inject(conditions, injected):
    if 'Grib2MetaData' in injected:
        injected = injected['Grib2MetaData']

    for inj in injected:  # ['Grib2MetaData']:
        for k, v in conditions.items():
            g2meta = v['Grib2MetaData']
            for item in g2meta:
                if inj['Key'] == item['Key']:
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
        logging.fatal(f"Required parameter '{p}' is not defined")
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
    successful_tests = 0
    failed_tests = 0
    skipped_tests = 0

    return_code = 0
    for test in config['Tests']:
        summaries = execute_test(test, dims['forecast_types'], dims['leadtimes'], tie(
            test['Parameters'], dims['parameters']), files)

        if len(summaries) == 0:
            logging.info("No grids checked")
            skipped_tests += 1

        for summary in summaries:
            retval = int(summary['return_value'])
            if retval > return_code:
                return_code = retval

            if retval == 0:
                #                logging.info(summary['message'])
                successful_tests += 1
            else:
                logging.error(summary['message'])
                failed_tests += 1

    logging.info(
        f"Total Summary: successful tests: {successful_tests}, failed: {failed_tests}, skipped: {skipped_tests}")

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
            parameters[pdef['Name']] = pdef

    except KeyError as e:
        return None

    return parameters


def parse_configuration_file(configuration_file):
    config = None
    with open(configuration_file, 'r') as fp:
        try:
            config = yaml.safe_load(fp)
        except yaml.YAMLError as exc:
            logging.fatal(exc)
            sys.exit(1)

    return config, parse_forecast_types(config), parse_leadtimes(config), parse_parameters(config)


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configuration", type=str,
                        help="configuration file for checker", required=True)
    parser.add_argument("--log-level", type=str,
                        help="log level 1-5", default=3)
    parser.add_argument(
        "files", type=str, help="input files to check", action='append', nargs='+')
    args = parser.parse_args()

    return args


def main():
    args = parse_command_line()
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=args.log_level,
        datefmt='%Y-%m-%d %H:%M:%S')

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        args.configuration)
    dims = {
        'forecast_types': forecast_types,
        'leadtimes': leadtimes,
        'parameters': parameters
    }

    check(config, dims, index_grib_files(args.files))


if __name__ == "__main__":
    main()
