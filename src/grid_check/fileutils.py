import eccodes as ecc
import gribapi
import numpy as np
import os
import fsspec
import logging
from datetime import datetime,timedelta
from .constants import *


def read_grib_message(index, conditions):
    index_keys = INDEX_KEYS
    leaf = index
    for ikey in index_keys:
        found = False
        for item in conditions:
            if item["Key"] == ikey:
                try:
                    leaf = leaf[item["Value"]]
                except KeyError as e:
                    return None
                found = True
                break
        if not found:
            logging.debug("Data not found from index")
            return None

    return leaf


def index_grib_files(grib_files):
    logging.info("Indexing grib files")
    index = {}

    index_keys = INDEX_KEYS
    cnt = 0

    for grib_file in grib_files[0]:
        wrk_grib_file = grib_file

        if grib_file.startswith("s3://"):
            wrk_grib_file = read_file_from_s3(grib_file)

        with open(wrk_grib_file) as fp:
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

                length = ecc.codes_get_long(gid, "totalLength")

                ref["file_name"] = grib_file
                ref["message_no"] = message_no
                ref["length"] = length
                ref["offset"] = offset

                message_no += 1
                offset += length
                cnt += 1

    logging.info(f"Indexed {cnt} messages from {len(grib_files[0])} file(s)")

    return index


def fsspec_s3():
    s3info = {}
    s3info["client_kwargs"] = {}

    try:
        ep = os.environ["S3_HOSTNAME"]
        if not ep.startswith("http"):
            ep = "https://" + ep
        s3info["client_kwargs"]["endpoint_url"] = ep
    except:
        s3info["client_kwargs"]["endpoint_url"] = "https://lake.fmi.fi"

    try:
        s3info["key"] = os.environ["S3_ACCESS_KEY_ID"]
        s3info["secret"] = os.environ["S3_SECRET_ACCESS_KEY"]
        s3info["anon"] = False
    except:
        s3info["anon"] = True

    return s3info


def read_file_from_s3(grib_file):
    uri = "simplecache::{}".format(grib_file)
    s3info = fsspec_s3()
    try:
        return fsspec.open_local(uri, s3=s3info)
    except Exception as e:
        print(
            "ERROR reading file={} from={} anon={}".format(
                grib_file, s3info["client_kwargs"]["endpoint_url"], s3info["anon"]
            )
        )
        raise e


def read_data(grid):
    """
    Read data values from grib file given the offset and length from index.
    Also provide some additional metadata that is not stored in the index.
    """

    wrk_grib_file = grid['file_name']

    if wrk_grib_file.startswith("s3://"):
        wrk_grib_file = read_file_from_s3(wrk_grib_file)

    with open(wrk_grib_file, "rb") as fp:
        fp.seek(grid["offset"], 0)
        buff = fp.read(grid["length"])
        fp.close()

    gid = ecc.codes_new_from_message(buff)
    ecc.codes_set(gid, "missingValue", MISS)

    ret = {}
    values = np.array(ecc.codes_get_values(gid))
    ret["Values"] = np.ma.masked_where(values == MISS, values)

    dd = ecc.codes_get_long(gid, "dataDate")
    dt = ecc.codes_get_long(gid, "dataTime")
    es = ecc.codes_get_long(gid, "endStep")

    ret["AnalysisTime"] = datetime.strptime(f"{dd}{dt:04d}", "%Y%m%d%H%M")
    ret["ForecastTime"] = ret["AnalysisTime"] + timedelta(hours=es)

    ecc.codes_release(gid)

    return ret


def read_grids(index, parameters):
    def format_metadata_to_string(metadata):
        string = ""
        for m in metadata:
            string += "%s=%s " % (m["Key"], m["Value"])

        return string

    grids = {}
    for param in parameters:
        grid = read_grib_message(index, parameters[param]["Grib2MetaData"])

        if grid is not None:
            logging.debug(
                f"Read {format_metadata_to_string(parameters[param]['Grib2MetaData'])}"
            )
            grids[param] = read_data(grid)

    diff = list(set(parameters) - set(grids.keys()))

    if len(diff) > 0:
        for param in diff:
            logging.warning(
                f"Unable to find data for '{param}': {format_metadata_to_string(parameters[param]['Grib2MetaData'])}"
            )
        return {}

    return grids
