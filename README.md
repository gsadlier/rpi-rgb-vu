RPi RGB LED Matrix Audio Visualiser
==================================================

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)

This is basically a Python wrapper around [karlstav](https://github.com/karlstav)'s [CAVA](https://github.com/karlstav/cava) and
[hzeller](https://github.com/hzeller)'s [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix), allowing you to make your RGB
LED Matrices show audio visualisations from Cava.

[worron](https://github.com/worron)'s code in an [issue in the cava repo](https://github.com/karlstav/cava/issues/123#issuecomment-307891020) served as a starting point.

More notes to come.  General sequence as follows:

- Install Cava. You can use the distribution package, but it would be best to build from source.
- Install rpi-rgb-led-matrix.
- `python -mvenv .venv --system-site-packages --prompt RPI-RGB-VU`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- Modify `example.json` to match your Matrix setup.  Refer to [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) if you are unsure.
- `python rgbvu.py -h`


## Potentially Asked Questions

### It only supports ALSA?

I mean, currently, yes, because it's easy and that's what I'm using. It would just be a matter of expanding on the captive config that `cavalib.py` feeds to CAVA.

### rpi-rgb-led-matrix is in C. CAVA is in C.  Why is this in Python? C would be faster.

Yes, C would be faster, but Python is fast enough for this application.  I can get up to 100fps on a Pi4 with six 64x64 panels attached, so there's not a lot of incentive to rewrite in C.
