import logging
import numpy as np

# format string so that None is printed as "None" and other values
# are printed as requested


def f(val, str=None):
    if val is None:
        return "None"
    return f"{val:{str}}" if str is not None else f"{val}"


class EnvelopeTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)
        self.name = config.get("Name", "EnvelopeTest")
        self.month = config["Test"].get("Month", None)
        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        sample_min = np.amin(sample["Values"])
        sample_max = np.amax(sample["Values"])

        retval = 0  # OK

        message = f"Min and max [{sample_min:.2f} {sample_max:.2f}], limits [{self.min} {self.max}], sample={sample['Values'].size}"

        if self.month is not None and sample["ForecastTime"].month != self.month:
            retval = -1  # DISABLED
            message = f"Test skipped due to month mismatch (expected: {self.month}, got: {sample['ForecastTime'].month})"
            return {"name": self.name, "return_code": retval, "message": message}

        logging.debug(
            f"Executing ENVELOPE test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        if (self.min is not None and sample_min < self.min) or (
            self.max is not None and sample_max > self.max
        ):
            retval = 1  # FAILED

        return {"name": self.name, "return_code": retval, "message": message}


class VarianceTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)

        # Backwards compatibility; MinVariance and MaxVariance should not be used
        # in new configurations
        if self.min is None and self.max is None:
            self.min = config["Test"].get("MinVariance", None)
            self.max = config["Test"].get("MaxVariance", None)

        self.name = config.get("Name", "EnvelopeTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        sample_var = np.var(sample["Values"])

        logging.debug(
            f"Executing VARIANCE test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        retval = 0  # OK

        if (self.min is not None and sample_var < self.min) or (
            self.max is not None and sample_var > self.max
        ):
            retval = 1  # FAILED

        return {
            "name": self.name,
            "return_code": retval,
            "message": f"Variance value {sample_var:.2g}, limits [{self.min} {self.max}], sample={sample['Values'].size}",
        }


class MeanTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)
        self.name = config.get("Name", "MeanTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        sample_mean = np.mean(sample["Values"])

        logging.debug(
            f"Executing MEAN test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        retval = 0  # OK

        if (self.min is not None and sample_mean < self.min) or (
            self.max is not None and sample_mean > self.max
        ):
            retval = 1  # FAILED

        return {
            "name": self.name,
            "return_code": retval,
            "message": f"Mean value {sample_mean:.2g}, limits [{self.min} {self.max}], sample={sample['Values'].size}",
        }


class MissingTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)
        self.name = config.get("Name", "MissingTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        missing = np.ma.count_masked(sample["Values"])

        logging.debug(
            f"Executing MISSING test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        if "%" in str(self.min):
            self.min = int(0.01 * sample["Values"].size)
        if "%" in str(self.max):
            self.max = int(0.01 * sample["Values"].size)

        retval = 0  # OK

        if (self.min is not None and missing < self.min) or (
            self.max is not None and missing > self.max
        ):
            retval = 1  # FAILED

        return {
            "name": self.name,
            "return_code": retval,
            "message": f"Number of missing values {missing:.0f}, limits [{self.min} {self.max}], sample={sample['Values'].size}",
        }


class IntegerTest:
    """Test if sample contains only integer numbers"""

    def __init__(self, config):
        self.name = config.get("Name", "IntegerTest")

    def __call__(self, sample):
        arr = sample["Values"]

        logging.debug(f"Executing INTEGER test '{self.name}'")

        retval = 0  # OK

        # Check if all elements are integers or can be safely converted to integers without losing information
        if not np.all(np.mod(arr, 1) == 0):
            retval = 1  # FAILED

        return {
            "name": self.name,
            "return_code": retval,
            "message": f"Data {'contained' if retval == 0 else 'did not contain'} all integers, sample={arr.size}",
        }
