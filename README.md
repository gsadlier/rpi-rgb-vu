RPi RGB LED Matrix Audio Visualiser
==================================================

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)

This is basically a Python wrapper around https://github.com/karlstav/cava and
https://github.com/hzeller/rpi-rgb-led-matrix, allowing you to make your RGB
LED Matrices show audio visualisations from Cava.

worron's code in an [issue in the cava repo](https://github.com/karlstav/cava/issues/123#issuecomment-307891020) served as a starting point.

More notes to come.  General sequence as follows:

- Install Cava
- Install rpi-rgb-led-matrix
- `python -mvenv .venv --system-site-packages --prompt RPI-RGB-VU`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `python rgbvu.py -h`
