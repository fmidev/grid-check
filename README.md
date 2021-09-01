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

Example configuration:

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
  - Name: Precipitation
    Grib2MetaData:
      - Key: discipline
        Value: 0
      - Key: parameterCategory
        Value: 1
      - Key: parameterNumber
        Value: 8
      - Key: typeOfFirstFixedSurface
        Value: 103
      - Key: typeOfStatisticalProcessing
        Value: 1
  - Name: Precipitation_lagged
    Parent: Precipitation
    Lag: 6h
Tests:
  - Name: check t2m envelope
    Sample: 10%
    Parameters:
      Names:
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
  - Name: check pcp envelope
    Sample: 40%
    Parameters:
      Names:
        - Precipitation
        - Precipitation_lagged
    Test:
      Preprocess: Precipitation - Precipitation_lagged
      Type: ENVELOPE
      MinAllowed: -0.01
      MaxAllowed: 50
```

Top level keys are:

* ForecastTypes

A mandatory key that defines for which forecast types (deterministic forecast, ensemble member etc) the check is being made.

* LeadTimes

A mandatory key that defines for which leadtimes the check is being made. Time values can be specified in "full time interval", for example one hour is "01:00:00", or 
as shortened hours, for example "1h". Sub-hour times are not supported currently.

* Parameters

An optional key that can be used to predefine variables that can later be used in 'Tests' sections

* Tests

The configuration of the actual tests.

The example file contains four distinct tests for the data.

First test tests that the data values lie between 220 and 325. It takes a sample of the data that equals to 10% of grid size. It uses a predefined parameter 'Temperature'.

Second test tests that the data variance is at least 50. Variance here is the average squared difference from the mean value. Only lower bound for variance is given. This
test is not using a predefined parameter but specifying grib2 keys "inline".

Third test tests that the data values lie between 0 and 25. It uses two predefined parameter U and V, and combines them into one field using numpy function "np.hypot".
The parameter definition is amended by injecting level value '10'.

Fourth test tests that 6h precipitation accumulation values lie between -0.01 and 50. The lower interval is defined as such since with grib packing method we can get values
_slightly_ lower than zero, for example -0. Preprocessing is a simple deduction of current precipitation and one recored 6h earlier. The latter is defined as 'Precipitation_lagged',
and it is copying the keys from 'Precipitation' using 'Parent', and it is defining a lag of 6h with 'Lag'.


Input files are given as command line arguments.

# Inline patching

It possible to do simple inline patching to configuration files, to easily modify a configuration on-the-fly.

For this command line option -p, --patch should be used.

For example, to modify the LeadTimes.Stop value in the example yaml, use the following command

```
$ grid-check.py -c <config> -p LeadTimes[0].Stop='24:00:00' ...
```

Multiple -p options can be specified. To remove a key, set the value to "None". A key that does not exists will be created.

Anykind of filtering is not possible to do; for more complex options it is recommended to use a yaml filtering program like `yq` to pre-process the configuration file.


# Example

```
$ grid-check.py -c pcp.yaml pcp.grib2  -d 5
Warning: ecCodes 2.17.0 or higher is recommended. You are running version 2.14.1
2020-05-14 10:11:48 INFO     Indexing grib files
2020-05-14 10:11:48 INFO     Indexed 85 messages from 1 file(s)
2020-05-14 10:11:48 INFO     Executing ENVELOPE test 'check pcp envelope', allowed range: [-0.01, 50]
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=3 perturbationNumber=0 
2020-05-14 10:11:48 WARNING  Unable to find data for 'Precipitation_lagged': discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=-3 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=6 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=0 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=9 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=3 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=12 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Read discipline=0 parameterCategory=1 parameterNumber=8 typeOfFirstFixedSurface=103 typeOfStatisticalProcessing=1 typeOfProcessedData=3 level=0 endStep=6 perturbationNumber=0 
2020-05-14 10:11:48 DEBUG    Forecast type: typeOfProcessedData=3 perturbationNumber=0  Leadtime 6:00:00 Min or max [0.00 23.29] is inside allowed range [-0.01 50.00], sample=29922
2020-05-14 10:11:48 DEBUG    Forecast type: typeOfProcessedData=3 perturbationNumber=0  Leadtime 9:00:00 Min or max [0.00 28.54] is inside allowed range [-0.01 50.00], sample=29922
2020-05-14 10:11:48 DEBUG    Forecast type: typeOfProcessedData=3 perturbationNumber=0  Leadtime 12:00:00 Min or max [-0.00 24.42] is inside allowed range [-0.01 50.00], sample=29922
2020-05-14 10:11:48 INFO     Total Summary: successful tests: 3, failed: 0, skipped: 1
```
