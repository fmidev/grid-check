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
from datetime import datetime


class EnvelopeTestException(Exception):
    pass


class GribMessageNotFoundException(Exception):
    pass


class TestNotImplementedException(Exception):
    pass


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


def level_from_grib(gid):
    return "%s/%s" % (ecc.codes_get(gid, "typeOfFirstFixedSurface"), ecc.codes_get(gid, 'level'))


def step_from_grib(gid):
    return ecc.codes_get(gid, 'endStep')


def read_grib_message(grib_file):
    with open(grib_file) as fp:
        while True:
            gid = ecc.codes_grib_new_from_file(fp)
            if gid is None:
                raise StopIteration
            yield gid

def read_sample(gid, keys, sample):
   keys.append({'Key' : 'edition', 'Value' : 2})
   if not validate_message(gid, keys):
       return None

   values = np.array(ecc.codes_get_values(gid))

   if '%' in str(sample):
       sample = int(int(sample[:-1]) * 0.01 * values.size)
   sample = np.random.choice(values, sample)

   return sample


def read_simple_metadata(gid):
    return forecast_type_from_grib(gid), step_from_grib(gid), level_from_grib(gid)


def execute_envelope_test(test, files):
    ret = []
    for f in files:
        for gid in read_grib_message(f[0]):
            sample = read_sample(gid, test['Grib2MetaData'], test['Sample'])
            if sample is None:
                continue

            ftype, lt, level = read_simple_metadata(gid)

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
                "return_value" : retval,
                "message" : f"Forecast type: {ftype} Leadtime {lt} Level {level}: Min or max [{smin:.2f} {smax:.2f}] is {word}inside allowed range [{emin:.2f} {emax:.2f}], sample={sample.size}"
              })
            ecc.codes_release(gid)

    return ret


def execute_variance_test(test, files):

    ret = []
    for f in files:
        for gid in read_grib_message(f[0]):
            ftype, lt, level = read_simple_metadata(gid)

            sample = read_sample(gid, test['Grib2MetaData'], test['Sample'])
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
                "return_value" : retval,
                "message" : f"Forecast type: {ftype} Leadtime {lt} Level {level}: Variance {svar:.2f} is {word}inside given limits [{minvar} {maxvar}], sample={sample.size}"
              })
            ecc.codes_release(gid)

    return ret


def execute_test(test, files):

    ty = test['Test']['Type']
    logging.info(f"Executing {ty} test")

    if ty == "ENVELOPE":
        return execute_envelope_test(test, files)
    elif ty == "VARIANCE":
        return execute_variance_test(test, files)
    else:
        raise TestNotImplementedException("Unsupported test: %s" % test['Test'])


def validate_message(gid, keys):
    for key in keys:
        try:
            val = ecc.codes_get_long(gid, key['Key'])
            if val != key['Value']:
                return False
        except gribapi.errors.KeyValueNotFoundError as e:
            logging.error(e)
            return False
    return True


def check(config, files):
    successful_tests = 0
    failed_tests = 0
    skipped_tests = 0

    return_code = 0  
    for test in config['Tests']:
        summaries = execute_test(test, files)

        if len(summaries) == 0:
            logging.info("No grids checked")
            skipped_tests += 1

        for summary in summaries:
            retval = int(summary['return_value'])
            if retval > return_code: return_code = retval

            if retval == 0:
#                logging.info(summary['message'])
                successful_tests += 1 
            else:
                logging.warn(summary['message'])
                failed_tests += 1 

    logging.info(f"Total Summary: successful tests: {successful_tests}, failed: {failed_tests}, skipped: {skipped_tests}")

    sys.exit(return_code)


def parse_configuration_file(configuration_file):
    with open(configuration_file, 'r') as fp:
        try:
            return yaml.safe_load(fp)
        except yaml.YAMLError as exc:
            print(exc)


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c","--configuration", type=str, help="configuration file for checker", required=True)
    parser.add_argument("--log-level", type=str, help="log level 1-5", default=3)
    parser.add_argument("files", type=str, help="input files to check",action='append', nargs='+')
    args = parser.parse_args()

    return args


def main():
    args = parse_command_line()
    logging.basicConfig(
            format='%(asctime)s %(levelname)-8s %(message)s',
            level=args.log_level,
            datefmt='%Y-%m-%d %H:%M:%S')

    config = parse_configuration_file(args.configuration)
    check(config, args.files)


if __name__ == "__main__":
    main()
