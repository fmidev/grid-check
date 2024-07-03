#!/usr/bin/env python3

import importlib
import sys
import pytest
import os
from grid_check import check, parse_configuration_file, index_grib_files

import_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, import_dir)


def test_pcp():

    config = "pcp.yaml"
    files = [["pcp.grib2"]]

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        config, None
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files)) == 0


def test_strict():

    config = "pcp.yaml"
    files = [["pcp.grib2"]]

    patch = ["LeadTimes[0].Stop=24:00:00"]
    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        config, patch
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files), strict=True) == 1


def test_missing():

    config = "missing.yaml"
    files = [["missing.grib2"]]

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        config, None
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files)) == 1


def test_tstm():

    config = "tstm.yaml"
    files = [["tstm.grib2"]]

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        config, None
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files)) == 1


def test_month():

    configfile = "time.yaml"
    files = [["pcp.grib2"]]

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        configfile, None
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files)) == 0

    patch = ["Tests[0].Test.Month=5", "Tests[0].Test.MaxAllowed=10"]
    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        configfile, patch
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files)) == 1


def test_include():
    configfile = "include_test.yaml"
    files = [["tstm.grib2"]]

    config, forecast_types, leadtimes, parameters = parse_configuration_file(
        configfile, None
    )

    dims = {
        "forecast_types": forecast_types,
        "leadtimes": leadtimes,
        "parameters": parameters,
    }

    assert check(config, dims, index_grib_files(files)) == 1
