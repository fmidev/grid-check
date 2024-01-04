#!/usr/bin/env python3

import importlib
import sys
import pytest
import os

import_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, import_dir)
gc = importlib.import_module("grid-check")

def test_pcp():

    config = 'pcp.yaml'
    files = [['pcp.grib2']]

    config, forecast_types, leadtimes, parameters = gc.parse_configuration_file(config, None)

    dims = {
        'forecast_types': forecast_types,
        'leadtimes': leadtimes,
        'parameters': parameters
    }

    assert(gc.check(config, dims, gc.index_grib_files(files)) == 0)

def test_strict():

    config = 'pcp.yaml'
    files = [['pcp.grib2']]

    patch = ["LeadTimes[0].Stop=24:00:00"]
    config, forecast_types, leadtimes, parameters = gc.parse_configuration_file(config, patch)

    dims = {
        'forecast_types': forecast_types,
        'leadtimes': leadtimes,
        'parameters': parameters
    }

    assert(gc.check(config, dims, gc.index_grib_files(files), strict=True) == 1)

def test_missing():

    config = 'missing.yaml'
    files = [['missing.grib2']]

    config, forecast_types, leadtimes, parameters = gc.parse_configuration_file(config, None)

    dims = {
        'forecast_types': forecast_types,
        'leadtimes': leadtimes,
        'parameters': parameters
    }

    assert(gc.check(config, dims, gc.index_grib_files(files)) == 1)

def test_tstm():

    config = 'tstm.yaml'
    files = [['tstm.grib2']]

    config, forecast_types, leadtimes, parameters = gc.parse_configuration_file(config, None)

    dims = {
        'forecast_types': forecast_types,
        'leadtimes': leadtimes,
        'parameters': parameters
    }

    assert(gc.check(config, dims, gc.index_grib_files(files)) == 1)

