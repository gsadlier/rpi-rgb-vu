import argparse
import logging
import signal
import time
from pathlib import Path

from cavalib import Cava, CavaError, FIFOShortReadError
from matrixlib import Matrix

_logger = logging.getLogger(Path(__file__).stem)

FPS = "fs\N{SUPERSCRIPT MINUS}\N{SUPERSCRIPT ONE}"


class Terminate(Exception):
    pass


def handler(signum, _frame):
    signame = signal.Signals(signum).name
    print(f"Signal handler called with signal {signame} ({signum})")
    raise Terminate()


def main():
    parser = argparse.ArgumentParser(description="Pi RGB LED Matrix VU")
    parser.add_argument("config", type=str, help="Path to JSON matrix config file")
    parser.add_argument(
        "--brightness", type=int, default=255, help="Matrix brightness. 1..255"
    )
    parser.add_argument(
        "--cava-path", type=str, default="/usr/bin/cava", help="Path to cava binary"
    )
    parser.add_argument(
        "--color_hi", "-c2", type=str, default="red", help="Color for 'top' of bars"
    )
    parser.add_argument(
        "--color_lo", "-c1", type=str, default="blue", help="Color for 'bottom' of bars"
    )
    parser.add_argument(
        "--fifo",
        type=str,
        default="/tmp/cava.fifo",
        help="Where to create FIFO for communications with Cava",
    )
    parser.add_argument(
        "--framerate", type=int, default=65, help="Framerate to pass to Cava"
    )
    parser.add_argument(
        "--peak-fade-rate",
        type=float,
        default=0.4,
        help="Rate at which peaks should fade",
    )
    parser.add_argument(
        "--peaks",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show peaks?",
    )
    parser.add_argument("--show-refresh", action="store_true", help="Show refresh rate")
    parser.add_argument("--source", type=str, default="default", help="ALSA source")
    parser.add_argument(
        "--split",
        "-s",
        action="store_true",
        help="Show split pane VU.  Implies --stereo.",
    )
    parser.add_argument("--stereo", action="store_true", help="Stereo output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Be more chatty")
    args = parser.parse_args()

    # Does not make sense to have a split display if we're not showing stereo output.
    if args.split:
        args.stereo = True

    # If we are running as root, then the matrix library will drop privileges
    # and after this point we're in that reduced privilege state.
    m = Matrix(args)

    last_update = None
    signal.signal(signal.SIGTERM, handler)
    try:
        with Cava(m.rows, args) as source:
            while True:
                try:
                    data = source.read()
                except FIFOShortReadError as err:
                    _logger.info("Skipping short block: %d", err.length)
                    continue

                m.render(data)

                if (last_update is None) or (time.time() - last_update > 1):
                    reads, frames = source.get_stats()

                    if last_update is not None:
                        dr = reads - last_reads
                        df = frames - last_frames
                        if (dropped := df - dr) or args.show_refresh:
                            if dropped:
                                print(
                                    f"Cava generating {df:3d} {FPS}, "
                                    f"Matrix displaying {dr:3d} {FPS}. "
                                    f"Dropping {df-dr:3d} {FPS}"
                                )
                            else:
                                print(f"Refreshing at {df:3d} {FPS}")

                    last_reads = reads
                    last_frames = frames
                    last_update = time.time()

    except CavaError as err:
        _logger.error(err)

    except (Terminate, KeyboardInterrupt):
        _logger.info("Bye!")


if __name__ == "__main__":
    main()
