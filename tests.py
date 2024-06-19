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
        self.name = config["Test"].get("Name", "EnvelopeTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        sample_min = np.amin(sample)
        sample_max = np.amax(sample)

        logging.info(
            f"Executing ENVELOPE test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        retval = True

        if (self.min is not None and sample_min < self.min) or (
            self.max is not None and sample_max > self.max
        ):
            retval = False

        return {
            "return_code": retval,
            "message": f"Min and max [{sample_min:.2f} {sample_max:.2f}], limits [{self.min} {self.max}], sample={sample.size}",
        }


class VarianceTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)

        # Backwards compatibility; MinVariance and MaxVariance should not be used
        # in new configurations
        if self.min is None and self.max is None:
            self.min = config["Test"].get("MinVariance", None)
            self.max = config["Test"].get("MaxVariance", None)

        self.name = config["Test"].get("Name", "EnvelopeTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        sample_var = np.var(sample)

        logging.info(
            f"Executing VARIANCE test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        retval = True

        if (self.min is not None and sample_var < self.min) or (
            self.max is not None and sample_var > self.max
        ):
            retval = False

        return {
            "return_code": retval,
            "message": f"Variance value {sample_var:.2f}, limits [{self.min} {self.max}], sample={sample.size}",
        }


class MeanTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)
        self.name = config["Test"].get("Name", "MeanTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        sample_mean = np.mean(sample)

        logging.info(
            f"Executing MEAN test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        retval = True

        if (self.min is not None and sample_mean < self.min) or (
            self.max is not None and sample_mean > self.max
        ):
            retval = False

        return {
            "return_code": retval,
            "message": f"Mean value {sample_mean:.2f}, limits [{self.min} {self.max}], sample={sample.size}",
        }


class MissingTest:
    def __init__(self, config):
        self.min = config["Test"].get("MinAllowed", None)
        self.max = config["Test"].get("MaxAllowed", None)
        self.name = config["Test"].get("Name", "MissingTest")

        if self.min is None and self.max is None:
            raise ValueError("At least one of MinAllowed or MaxAllowed must be defined")

    def __call__(self, sample):
        missing = np.ma.count_masked(sample)

        logging.info(
            f"Executing MISSING test '{self.name}', allowed range: [{self.min} {self.max}]"
        )

        if "%" in str(self.min):
            self.min = int(0.01 * sample.size)
        if "%" in str(self.max):
            self.max = int(0.01 * sample.size)

        retval = True

        if (self.min is not None and missing < self.min) or (
            self.max is not None and missing > self.max
        ):
            retval = False

        return {
            "return_code": retval,
            "message": f"Number of missing values {missing:.0f}, limits [{self.min} {self.max}], sample={sample.size}",
        }
