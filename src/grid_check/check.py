import yaml
import numpy as np
import logging
import copy
import os
from random import randrange
from datetime import timedelta
from .tests import *
from .fileutils import read_grids
from .constants import *
import pydash


class TestNotImplementedException(Exception):
    pass


def get_default_value(keyname):
    if keyname == "typeOfProcessedData":
        return 1  # deterministic
    elif keyname == "typeOfFirstFixedSurface":
        return 103  # height
    elif keyname == "level":
        return 0


def forecast_type_from_grib(gid):
    ty = ecc.codes_get_long(gid, "typeOfProcessedData")

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


def read_sample(grids, sample_size, remove_missing=True):
    if grids is None or len(grids) == 0:
        return []

    def sample_without_missing_values(g):
        nonlocal sample_size
        # remove missing values
        ngrid = g.compressed()

        if "%" in str(sample_size):
            sample_size = int(int(sample_size[:-1]) * 0.01 * ngrid.size)

        if g.size == 0:
            logging.warning("All elements of grid are missing")
            return None

        # If majority of grid is missing, don't generate a sample
        miss_ratio = float(ngrid.size) / g.size
        if miss_ratio < 0.40:
            logging.warning(
                "{:.1f}% of grid elements are missing, cannot generate a sample".format(
                    100 * (1 - miss_ratio)
                ),
            )

            return None

        return np.random.choice(ngrid, sample_size)

    def sample_with_missing_values(g):
        nonlocal sample_size
        if "%" in str(sample_size):
            sample_size = int(int(sample_size[:-1]) * 0.01 * g.size)

        # return masked array to normal array
        ngrid = g.data

        # select a random sample
        sample = np.random.choice(ngrid, sample_size)

        # apply mask once again
        sample = np.ma.masked_where(sample == MISS, sample)

        return sample

    ret = []

    func = (
        sample_without_missing_values if remove_missing else sample_with_missing_values
    )

    for g in grids:
        g["Values"] = func(g["Values"])

    return grids


def string_to_timedelta(string):
    if string[-1] == "h":
        return timedelta(hours=int(string[:-1]))
    t = string.split(":")
    return timedelta(hours=int(t[0]), minutes=int(t[1]), seconds=int(t[2]))


def timedelta_to_grib2metadata(td):
    d = {"Grib2MetaData": [{"Key": "endStep", "Value": int(td.total_seconds() / 3600)}]}

    return d


def generate_leadtimes(leadtime_configs):
    leadtimes = []
    for cfg in leadtime_configs:
        current = string_to_timedelta(cfg["Start"])
        stop = string_to_timedelta(cfg["Stop"])
        step = string_to_timedelta(cfg["Step"])

        while current <= stop:
            leadtimes.append(current)
            current += step

    leadtimes.sort()
    return leadtimes


def format_metadata_to_string(metadata):
    string = ""
    for m in metadata:
        string += "%s=%s " % (m["Key"], m["Value"])

    return string


def preprocess(grids, test):
    """
    Preprocess grids before running the test.
    Only if Preprocess key is defined in the test configuration.
    """

    if len(grids) == 0:
        return None

    prep = test.get("Preprocess", None)

    if prep is None:
        return grids

    try:
        # Create local variables for the preprocessing function.
        # This way the preprocessing function can access the variables names
        # directly

        lcl = locals()

        for g in grids:
            lcl[g["Parameter"]] = g["Values"]

        processed = eval(prep["Function"])
        name = prep.get("Rename", None)
        name = name if name is not None else str(prep)

        # TODO: accessing only first grid
        grids[0]["Parameter"] = name
        grids[0]["Values"] = processed

        return grids

    except NameError as e:
        raise Exception("Invalid preprocessing function: {prep}: {e}")


def execute_test(test, forecast_types, leadtimes, parameters, files):
    ty = test["Test"]["Type"]

    remove_missing = True
    classname = None

    if ty == "ENVELOPE":
        classname = EnvelopeTest
    elif ty == "VARIANCE":
        classname = VarianceTest
    elif ty == "MEAN":
        classname = MeanTest
    elif ty == "MISSING":
        remove_missing = False
        classname = MissingTest
    else:
        raise TestNotImplementedException("Unsupported test: %s" % test["Test"])

    ret = {"success": 0, "fail": 0, "skip": 0, "summary": []}

    for ft in forecast_types:
        lparameters = inject(copy.deepcopy(parameters), ft)
        for lt in leadtimes:
            lparameters = inject(lparameters, timedelta_to_grib2metadata(lt))
            grids = read_grids(files, lparameters)
            grids = [{"Parameter": x, **grids[x]} for x in grids.keys()]

            samples = read_sample(
                preprocess(grids, test["Test"]),
                test["Sample"],
                remove_missing=remove_missing,
            )

            if len(samples) == 0:
                ret["skip"] += 1
                continue

            for sample in samples:
                if sample is None or sample["Values"] is None:
                    ret["skip"] += 1

                    continue

                parameter = sample["Parameter"]
                status = classname(test)(sample)
                return_code = status["return_code"]

                if return_code == 0:
                    ret["success"] += 1
                elif return_code == 1:
                    ret["fail"] += 1

                message = ""

                for kv in ft["Grib2MetaData"]:
                    if kv["Key"] == "typeOfProcessedData":
                        if str(kv["Value"]) != "2":
                            message = f"Forecast type: {format_metadata_to_string(ft['Grib2MetaData'])}"
                        break

                message += f"Leadtime {lt} Parameter {parameter} {status['message']}"

                ret["summary"].append({"return_value": return_code, "message": message})

    return ret


def inject(conditions, injected):
    if "Grib2MetaData" in injected:
        injected = injected["Grib2MetaData"]

    for inj in injected:
        for k, v in conditions.items():
            g2meta = v["Grib2MetaData"]
            for item in g2meta:
                if inj["Key"] == item["Key"]:
                    # if injecting time, check if parameter is lagged
                    if inj["Key"] == "endStep" and "Lag" in v:
                        lagged = int(
                            (
                                timedelta(hours=inj["Value"])
                                - string_to_timedelta(v["Lag"])
                            ).total_seconds()
                            / 3600
                        )
                        #                        logging.debug(f"Lagging time {inj['Value']} to {lagged}")
                        item["Value"] = lagged
                    else:
                        item["Value"] = inj["Value"]
                    found = True
                    break
            if not found:
                g2meta["Key"] = inj["Value"]

    return conditions


def tie(req_parameters, parameters):
    ret = {}

    names = []

    try:
        names = req_parameters["Names"]

    except KeyError as e:
        pass

    try:
        for name in names:
            ret[name] = parameters[name]

    except KeyError as e:
        raise Exception(f"Required parameter is not defined: {e}")

    try:
        meta = req_parameters["Grib2MetaData"]

        if len(ret.keys()) == 0:
            randi = randrange(100)
            ret[f"anon_{randi}"] = {}
            ret[f"anon_{randi}"]["Grib2MetaData"] = meta

        else:
            # for parameters
            for name in ret:
                replaced = False
                for newkey in meta:
                    for i, k in enumerate(ret[name]["Grib2MetaData"]):
                        if k["Key"] == newkey["Key"]:
                            ret[name]["Grib2MetaData"][i] = newkey
                            replaced = True
                    if replaced == False:
                        ret[name]["Grib2MetaData"].append(newkey)

    except KeyError as e:
        pass

    index_keys = INDEX_KEYS

    # must have value for all index keys

    for ikey in index_keys:
        for k, v in ret.items():
            g2meta = v["Grib2MetaData"]
            found = False
            for item in g2meta:
                if item["Key"] == ikey:
                    found = True
                    break
            if not found:
                # add default value
                default = get_default_value(ikey)
                #                logging.debug(f"Add default value for {k}: {ikey} => {default}")
                ret[k]["Grib2MetaData"].append({"Key": ikey, "Value": default})

    return ret


def check(config, dims, files, strict=False):
    success = 0
    fail = 0
    skip = 0

    return_code = 0
    combined_errors = []

    for test in config["Tests"]:
        summaries = execute_test(
            test,
            dims["forecast_types"],
            dims["leadtimes"],
            tie(test["Parameters"], dims["parameters"]),
            files,
        )

        success += summaries["success"]
        fail += summaries["fail"]
        skip += summaries["skip"]

        if len(summaries["summary"]) == 0:
            logging.info("No grids checked")

        for summary in summaries["summary"]:
            retval = summary["return_value"]
            if retval > return_code:
                return_code = retval

            if retval == 0:
                # test was successful
                logging.info(summary["message"])
            elif retval == -1:
                # test was skipped with ok status, for example month didn't match
                # log with debug level as it was not a failure and produces a lot of output
                logging.debug(summary["message"])
            elif retval == 1:
                # test failed
                logging.error(summary["message"])
                combined_errors.append(
                    {"name": test["Name"], "message": summary["message"]}
                )

    logging.info(
        f"Total Summary: successful tests: {success}, failed: {fail}, skipped: {skip}"
    )

    if len(combined_errors) > 0:
        logging.error("Summary of errors:")
        for err in combined_errors:
            logging.error("'{}': {}".format(err["name"], err["message"]))

    if strict and (fail > 0 or skip > 0):
        return_code = 1

    return return_code


def parse_forecast_types(config):
    forecast_types = []
    try:
        for ft in config["ForecastTypes"]:
            rng = None
            ty = None

            for item in ft["Grib2MetaData"]:
                if item["Key"] == "perturbationNumber":
                    if "-" in str(item["Value"]):
                        start, stop = item["Value"].split("-")
                        rng = range(int(start), int(stop) + 1)
                    else:
                        rng = [int(item["Value"])]
                if item["Key"] == "typeOfProcessedData":
                    ty = item["Value"]
                    rng = [None]

            for x in rng:
                d = {"Grib2MetaData": []}
                d["Grib2MetaData"].append({"Key": "typeOfProcessedData", "Value": ty})
                d["Grib2MetaData"].append({"Key": "perturbationNumber", "Value": x})
                forecast_types.append(d)

        return forecast_types
    except KeyError as e:
        raise Exception("'ForecastTypes' must be defined")


def parse_leadtimes(config):
    leadtimes = {}
    return generate_leadtimes(config["LeadTimes"])


def parse_parameters(config):
    parameters = {}
    try:
        paramdefs = config["Parameters"]
        for pdef in paramdefs:
            if "Parent" in pdef:
                pdef["Grib2MetaData"] = copy.deepcopy(
                    parameters[pdef["Parent"]]["Grib2MetaData"]
                )
                pdef.pop("Parent", None)
            parameters[pdef["Name"]] = pdef
    except KeyError as e:
        return None

    return parameters


def apply_patch_to_configuration(config, patches):
    for patch in patches:
        (k, v) = patch.split("=")
        element = pydash.get(config, k)

        if element is None:
            logging.debug("PATCH: Adding element {}={} to configuration".format(k, v))

        if v == "None":
            pydash.unset(config, k)
        else:
            # try to cast value to native data format, because
            # eccodes is indexing data with numbers whenever it can
            try:
                v = int(v)
            except ValueError as e:
                try:
                    v = float(v)
                except ValueError as ee:
                    pass

            pydash.set_(config, k, v)

    return config


def parse_configuration_file(configuration_file, patch):
    def include_constructor(loader, node):
        # Get the path of the included file
        included_file_path = loader.construct_scalar(node)

        possible_paths = [
            included_file_path,
            os.path.join(os.path.dirname(configuration_file), included_file_path),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "include",
                os.path.basename(included_file_path),
            ),
        ]

        new_included_file_path = None
        for included_file_path in possible_paths:
            if not os.path.exists(included_file_path):
                continue

            logging.debug(f"Found included file: {included_file_path}")
            new_included_file_path = included_file_path

            break

        if new_included_file_path is None:
            raise FileNotFoundError(
                "Included file {} not found".format(loader.construct_scalar(node))
            )

        included_file_path = new_included_file_path

        # Load the included file
        with open(included_file_path, "r") as included_file:
            included_content = yaml.load(included_file, Loader=yaml.FullLoader)

        # If included content is a list, return its elements individually
        if isinstance(included_content, list):
            return included_content

        return [included_content]

    def construct_sequence_flatten(loader, node):
        """Construct a list while flattening any included lists."""
        value = loader.construct_sequence(node)
        flattened = []
        for item in value:
            if isinstance(item, list):
                flattened.extend(item)
            else:
                flattened.append(item)
        return flattened

    config = None
    with open(configuration_file, "r") as fp:
        try:
            yaml.add_constructor(
                "!include", include_constructor, Loader=yaml.FullLoader
            )
            yaml.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_SEQUENCE_TAG,
                construct_sequence_flatten,
                Loader=yaml.FullLoader,
            )

            config = yaml.load(fp, Loader=yaml.FullLoader)
        except yaml.YAMLError as exc:
            raise Exception(exc)

    if patch is not None:
        config = apply_patch_to_configuration(config, patch)

    logging.info(yaml.dump(config, default_flow_style=False))
    return (
        config,
        parse_forecast_types(config),
        parse_leadtimes(config),
        parse_parameters(config),
    )
