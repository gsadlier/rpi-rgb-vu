import logging
import os
import signal
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from numpy import array

CONFIG = """[general]
autosens = 0
bars = %d
framerate = %d
sleep_timer = 5
[input]
method = alsa
source = %s
[output]
method = raw
raw_target = %s
bit_format = 8bit
channels = %s
[smoothing]
#monstercat = 1
#waves = 1
#noise_reduction = 90
"""


class CavaError(Exception):
    pass


class FIFOShortReadError(Exception):
    def __init__(self, length):
        self.length = length


class Cava:
    def __init__(self, width, args):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.args = args

        ### CAVA CONFIGURATION ###
        bytetype, bytesize, self.bytenorm = ("B", 1, 255)

        self.bars = width
        if self.args.split:
            self.bars *= 2
        self.chunk = bytesize * self.bars
        self.fmt = bytetype * self.bars

        ### Initialise FIFO ###
        self.path = Path(self.args.fifo)
        self._logger.debug("Initialising FIFO %s", self.path)
        if not self.path.exists():
            self._logger.debug("...creating")
            os.mkfifo(self.path)
        elif not self.path.is_fifo():
            raise ValueError("{self.path} is not a FIFO!")
        self._logger.debug("...FIFO is good")

        self.fifo = None
        self.cfg = None
        self.p = None

        self.frame_counter = 0
        self.read_counter = 0

    def handler(self, signum, _frame):
        signame = signal.Signals(signum).name
        self._logger.error("Received %s (%d), timeout", signame, signum)
        raise TimeoutError()

    def __enter__(self):
        config = CONFIG % (
            self.bars,
            self.args.framerate,
            self.args.source,
            self.args.fifo,
            "stereo" if self.args.stereo else "mono",
        )

        self._logger.debug("Using cava config:\n%s", config)

        self.cfg = tempfile.NamedTemporaryFile("w", encoding="utf-8")
        self.cfg.write(config)
        self.cfg.flush()

        self.p = subprocess.Popen(
            [self.args.cava_path, "-p", self.cfg.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
        )

        # If cava is sad, it takes a few milliseconds to fail, so unless we
        # want to do a sleep, which gets unpredictable, it's better just to set
        # a timeout on opening the FIFO.  This catches more potential problems
        # anyway.
        signal.signal(signal.SIGALRM, self.handler)
        signal.alarm(1)
        try:
            self.fifo = self.get_fifo()
        except TimeoutError as err:
            error = self.p.stderr.read().decode()
            self.__exit__()
            raise CavaError(f"Cava failed:\n{error}") from err
        finally:
            signal.alarm(0)

        return self

    def get_fifo(self):
        return self.path.open("rb")

    def __exit__(self, _type=None, _value=None, _traceback=None):
        if self.cfg:
            self.cfg.close()
        if self.fifo:
            self.fifo.close()

        if self.p:
            if rc := self.p.poll():
                self._logger.debug("cava terminated with returncode: %d", rc)

            else:
                self._logger.debug("Terminating cava")
                self.p.terminate()
                try:
                    self.p.wait(timeout=1)

                except subprocess.TimeoutExpired:
                    self._logger.error("Cava failed to terminate.  Issuing SIGKILL.")
                    self.p.kill()

                else:
                    self._logger.debug("Cava exiting normally")

            self.p.stdout.close()
            self.p.stderr.close()

    def read(self):
        # Read the most recent data available from Cava. To ensure we are as
        # responsive as possible, dump frames that are returned too quickly as
        # that indicates they've been sitting in the FIFO.  If we have to wait
        # a bit for the data then we know it's fresh.  20us seems to be about
        # right, but this is likely to vary by platform and system load.

        dt = 0
        i = 0
        while dt < 2e-5:  # 20us
            t0 = time.perf_counter()
            data = self.fifo.read(self.chunk)
            dt = time.perf_counter() - t0
            self.frame_counter += 1
            i += 1

            if not data:
                raise CavaError("FIFO closed unexpectedly")
            if len(data) < self.chunk:
                raise FIFOShortReadError(len(data))

            if i > 100:
                raise CavaError("Failed reach head of FIFO in reasonable time")

        self.read_counter += 1
        return array([i / self.bytenorm for i in struct.unpack(self.fmt, data)])

    def get_stats(self):
        return self.read_counter, self.frame_counter
