# grid-check

grid-check is a simple tool to check the contents of gridded (meteorological) files for any abnormalities. It's purpose is to quickly catch any possible problems with the quality of grid data.

# Properties

* Written in python3
* Configuration through yaml files
* Initial support for two different test types
  * Envelope test
  * Variance tests
* Support for grib data type

# Configuration

Configuration is done through yaml files.

Example:

```
Tests:
  - Name: check t2m envelope
    Sample: 10%
    Grib2MetaData:
      - Key: discipline
        Value: 0
      - Key: parameterCategory
        Value: 0
      - Key: parameterNumber
        Value: 0
      - Key: typeOfFirstFixedSurface
        Value: 105
      - Key: level
        Value: 130
    Test:
      Type: ENVELOPE
      MinAllowed: 220
      MaxAllowed: 325
  - Name: check t variance
    Sample: 15%
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
```

File contains two distinct tests for the data.

First test tests that the data values lie between 220 and 325. It takes a sample of the data that equals to 10% of grid size.

Second tests tests that the data variance is at least 50. Variance here is the average squared difference from the mean value. Only lower bound for variance is given.

Both tests read only specific messages from a grib file that possibly contains many messages.

Input files are given as command line arguments.

# Example

```
$ ./grid-check -c config.yaml one.grib
2020-05-04 14:35:40 INFO     Executing ENVELOPE test
2020-05-04 14:35:40 INFO     No grids checked
2020-05-04 14:35:40 INFO     Executing VARIANCE test
2020-05-04 14:35:40 INFO     Total Summary: successful tests: 1, failed: 0, skipped: 1
```
