import argparse
import json
import logging
import os
import sys
from pathlib import Path

from colour import Color
from rgbmatrix import (  # pylint: disable=import-error
    RGBMatrix,
    RGBMatrixOptions,
    graphics,
)

WHITE = graphics.Color(255, 255, 255)

REQUIRED_PARAMS = {
    "chain_length",
    "cols",
    "hardware_mapping",
    "parallel",
    "rows",
}
OPTIONAL_PARAMS = {
    "drop_priv_group",
    "drop_priv_user",
    "gpio_slowdown",
}
ALL_PARAMS = REQUIRED_PARAMS | OPTIONAL_PARAMS


def colour_to_matrix_color(c):
    return graphics.Color(
        round(c.red * 255),
        round(c.green * 255),
        round(c.blue * 255),
    )


class Matrix:
    def __init__(self, args):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.args = args

        try:
            with Path(args.config).open(encoding="utf-8") as fh:
                cfg = json.load(fh)
        except (json.JSONDecodeError, FileNotFoundError) as err:
            raise argparse.ArgumentError from err

        if extra_params := set(cfg.keys()) - ALL_PARAMS:
            raise ValueError(f"Invalid parameters in config: {sorted(extra_params)}")

        if missing_params := REQUIRED_PARAMS - set(cfg.keys()):
            raise ValueError(
                f"Missing required parameters in config: {sorted(missing_params)}"
            )

        if (self.args.brightness < 1) or (self.args.brightness > 255):
            self._logger.fatal(
                "Invalid brightness: %d. Must be in range 1..255", self.args.brightness
            )
            sys.exit(1)

        if uid := os.getuid():
            self._logger.info("Running as user %d, disabling hardware pulsing", uid)
        else:
            self._logger.info("Running as root.")

        self.rows = cfg["rows"] * cfg["parallel"]
        self.cols = cfg["cols"] * cfg["chain_length"]

        self._logger.info("Drawing Area: %d x %d", self.cols, self.rows)

        options = RGBMatrixOptions()
        options.rows = cfg["rows"]
        options.cols = cfg["cols"]
        options.chain_length = cfg["chain_length"]
        if "gpio_slowdown" in cfg:
            options.gpio_slowdown = cfg["gpio_slowdown"]
        options.parallel = cfg["parallel"]
        options.hardware_mapping = cfg["hardware_mapping"]

        if uid:
            options.disable_hardware_pulsing = True
        else:
            if user := cfg.get("drop_priv_user"):
                options.drop_priv_user = user
            if group := cfg.get("drop_priv_group"):
                options.drop_priv_group = group

        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        self.canvas.brightness = self.args.brightness

        # These contain the peak values seen per column.
        self.max_l = [0] * self.cols
        self.max_r = [0] * self.cols
        self.max = [0] * self.cols

        # Array of colors, indexed by row.
        self.colors = []

        if self.args.split:
            # When we are in split mode we go from hi_color down to lo_color
            # then back up to hi_color again.
            self.colors = [
                colour_to_matrix_color(c)
                for c in Color(self.args.color_hi).range_to(
                    Color(self.args.color_lo), self.rows // 2
                )
            ] + [
                colour_to_matrix_color(c)
                for c in Color(self.args.color_lo).range_to(
                    Color(self.args.color_hi), self.rows // 2
                )
            ]

        else:
            # In normal mode, its a simple scan from hi_color to lo_color
            self.colors = [
                colour_to_matrix_color(c)
                for c in Color(self.args.color_hi).range_to(
                    Color(self.args.color_lo), self.rows
                )
            ]

    def draw_bar(self, x, level):
        n = self.rows - 1
        f = round(level * n)

        # Draw actual volume bar, in layers so each one is a different color
        for y in range(n, n - f, -1):
            graphics.DrawLine(self.canvas, x, y, x, y, self.colors[y])

        if self.args.peaks:
            # update max intensity
            self.max[x] = max(f, self.max[x] - self.args.peak_fade_rate)
            graphics.DrawLine(
                self.canvas,
                x,
                n - round(self.max[x]),
                x,
                n - round(self.max[x]),
                WHITE,
            )

    def draw_split_bar(self, x, level_l, level_r):
        n = (self.rows // 2) - 1
        ll = round(level_l * n)
        lr = round(level_r * n)

        # LEFT. Middle going up.
        for y in range(n, n - ll, -1):
            graphics.DrawLine(self.canvas, x, y, x, y, self.colors[y])
        # RIGHT: Middle going down.
        for y in range(n + 1, n + 1 + lr):
            graphics.DrawLine(self.canvas, x, y, x, y, self.colors[y])

        if self.args.peaks:
            # update max intensity
            self.max_l[x] = max(ll, self.max_l[x] - self.args.peak_fade_rate)
            self.max_r[x] = max(lr, self.max_r[x] - self.args.peak_fade_rate)

            # LEFT PEAK
            graphics.DrawLine(
                self.canvas,
                x,
                n - round(self.max_l[x]),
                x,
                n - round(self.max_l[x]),
                WHITE,
            )
            # RIGHT PEAK
            graphics.DrawLine(
                self.canvas,
                x,
                n + 1 + round(self.max_r[x]),
                x,
                n + 1 + round(self.max_r[x]),
                WHITE,
            )

    def render(self, vu):
        if self.args.split:
            # vu is evenly split between left and right channels, with
            # the right channel being reversed with respect to the left. In
            # order to do a vertical inversion, we pair the first item with the
            # last, the second with the second to last, etc.
            for x, l, r in zip(range(len(vu) // 2), vu, vu[::-1]):
                self.draw_split_bar(x, l, r)
        else:
            for x, v in zip(range(len(vu)), vu):
                self.draw_bar(x, v)

        self.canvas = self.matrix.SwapOnVSync(self.canvas)
        self.canvas.Clear()
