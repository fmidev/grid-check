#!/usr/bin/env python3

import sys
import argparse
import logging
from grid_check import parse_configuration_file, check, index_grib_files

def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--configuration",
        type=str,
        help="configuration file for checker",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--patch",
        type=str,
        action="append",
        help="modify configuration file with in-line options",
        required=False,
    )
    parser.add_argument("-d", "--log-level", type=int, help="log level 1-5", default=4)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit if error if any test fails or is skipped",
        default=False,
    )
    parser.add_argument(
        "files", type=str, help="input files to check", action="append", nargs="+"
    )
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
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=args.log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        args.configuration, args.patch
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    return check(config, dims, index_grib_files(args.files), args.strict)


if __name__ == "__main__":
    sys.exit(main())
