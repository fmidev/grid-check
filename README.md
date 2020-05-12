# grid-check

grid-check is a simple tool to check the contents of gridded (meteorological) files for any abnormalities. It's purpose is to quickly catch any possible problems with the quality of grid data.

# Properties

* Written in python3
* Configuration through yaml files
* Initial support for two different test types
  * Envelope test
  * Variance tests
* Support for grib2 data type

# Configuration

Configuration is done through yaml files.

Example:

```
ForecastTypes:
  - Grib2MetaData:
    - Key: typeOfProcessedData
      Value: 4
    - Key: perturbationNumber
      Value: 1-50
LeadTimes:
  - "Start" : "00:00:00"
    "Stop"  : "12:00:00"
    "Step"  : "01:00:00"
Parameters:
  - Name: Temperature
    Grib2MetaData:
      - Key: discipline
        Value: 0
      - Key: parameterCategory
        Value: 0
      - Key: parameterNumber
        Value: 0
  - Name: U
    Grib2MetaData:
      - Key: discipline
        Value: 0
      - Key: parameterCategory
        Value: 2
      - Key: parameterNumber
        Value: 2
      - Key: typeOfFirstFixedSurface
        Value: 103
  - Name: V
    Grib2MetaData:
      - Key: discipline
        Value: 0
      - Key: parameterCategory
        Value: 2
      - Key: parameterNumber
        Value: 3
      - Key: typeOfFirstFixedSurface
        Value: 103
Tests:
  - Name: check t2m envelope
    Sample: 10%
    Parameters:
      - Names:
        - Temperature
    Test:
      Type: ENVELOPE
      MinAllowed: 220
      MaxAllowed: 325
  - Name: check t variance
    Sample: 15%
    Parameters:
      Grib2MetaData:
        - Key: discipline
          Value: 0
        - Key: parameterCategory
          Value: 0
        - Key: parameterNumber
          Value: 0
        - Key: typeOfFirstFixedSurface
          Value: 105
    Test:
      Type: VARIANCE
      MinVariance: 50
  - Name: check ff envelope
    Sample: 20%
    Parameters:
      Names:
        - U
        - V
      Grib2MetaData:
        - Key: level
          Value: 10
    Test:
      Preprocess: np.hypot(U, V)
      Type: ENVELOPE
      MinAllowed: 0
      MaxAllowed: 25
```

Top level keys are:

* ForecastTypes

A mandatory key that defines for which forecast types (deterministic forecast, ensemble member etc) the check is being made.

* LeadTimes

A mandatory key that defines for which leadtimes the check is being made.

* Parameters

An optional key that can be used to predefine variables that can later be used in 'Tests' sections

* Tests

The configuration of the actual tests.

The example file contains three distinct tests for the data.

First test tests that the data values lie between 220 and 325. It takes a sample of the data that equals to 10% of grid size. It uses a predefined parameter 'Temperature'.

Second test tests that the data variance is at least 50. Variance here is the average squared difference from the mean value. Only lower bound for variance is given. This
test is not using a predefined parameter but specifying grib2 keys "inline".

Third test tests that the data values lie between 0 and 25. It uses two predefined parameter U and V, and combines them into one field using numpy function "np.hypot".
The parameter definition is amended by injecting level value '10'.

Input files are given as command line arguments.

# Example

```
$ ./grid-check -c config.yaml one.grib
2020-05-04 14:35:40 INFO     Executing ENVELOPE test
2020-05-04 14:35:40 INFO     No grids checked
2020-05-04 14:35:40 INFO     Executing VARIANCE test
2020-05-04 14:35:40 INFO     Total Summary: successful tests: 1, failed: 0, skipped: 1
```
