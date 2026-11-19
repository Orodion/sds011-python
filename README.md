# sds011-python
Control for SDS011 over serial interface and simulation for SDS011 for implementation support.

Inspired by kadamski/sds011

https://gist.github.com/kadamski/92653913a53baf9dd1a8

Used python version was 3.7. CI tests Python 3.11 to 3.14.

## Development checks

CI runs exactly these commands (configuration in `setup.cfg`):

```bash
pip install -r requirements-dev.txt
flake8 .
mypy
python -m pytest
```

`pytest` fails if test coverage drops below 80 %.

Documenctaion is included in repository. (sds011-python/doku)

Test scripts included in repository. (sds011-python/test)

Simple example included. (sds011-python/examples)

A binary file with some data frames from my sensor included for testing without device. sds011-python/data

Tested with simulation and real device.

Later I want to add more examples.
And may also try to make a version for micropython to run it on my nodeMCU v3.