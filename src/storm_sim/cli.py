"""cli.py - Command-line interface and entry point for storm-sim."""

from __future__ import annotations
import argparse
import asyncio
from pathlib import Path
import sys
import threading
from typing import List, Optional

from .constants import (
    ABSOLUTE_MIN_DIST_MILES,
    DEFAULT_ASSETS_DIR,
    DEFAULT_INTENSITY,
    DEFAULT_MASTER_BRIGHTNESS,
    DEFAULT_MASTER_VOLUME,
    DEFAULT_MAX_DIST_MILES,
    DEFAULT_MIN_DIST_MILES,
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    DEFAULT_PIXELS,
    DEFAULT_START_UNIVERSE,
    MIN_DIST_SPAN_MILES,
)
from .engine import StormCoordinator
from .models import StormState


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="storm-sim",
        description="Physics-Based E1.31 (Monochrome White) & Spatial Audio Thunderstorm Simulator",
    )
    parser.add_argument(
        "-i",
        "--intensity",
        type=float,
        default=DEFAULT_INTENSITY,
        help="Master storm intensity [0.0 = off, 1.0 = max]",
    )
    parser.add_argument(
        "--pixels",
        type=int,
        default=DEFAULT_PIXELS,
        help="Number of single-channel white pixels",
    )
    parser.add_argument(
        "--e131-host",
        type=str,
        default=None,
        help="Unicast target IP (omit for multicast)",
    )
    parser.add_argument(
        "--multicast",
        action="store_true",
        default=False,
        help="Force E1.31 multicast mode",
    )
    parser.add_argument(
        "--universe",
        type=int,
        default=DEFAULT_START_UNIVERSE,
        help="Starting E1.31 DMX universe",
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        default=DEFAULT_MIN_DIST_MILES,
        help="Minimum strike distance in miles",
    )
    parser.add_argument(
        "--max-dist",
        type=float,
        default=DEFAULT_MAX_DIST_MILES,
        help="Maximum strike distance in miles",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Override average strikes per minute",
    )
    parser.add_argument(
        "--rain",
        type=float,
        default=None,
        help="Override background rain level [0.0 - 1.0]",
    )
    parser.add_argument(
        "--brightness",
        type=float,
        default=DEFAULT_MASTER_BRIGHTNESS,
        help="Master lighting ceiling [0.0 - 1.0]",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=DEFAULT_MASTER_VOLUME,
        help="Master audio volume [0.0 - 1.0]",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=Path(DEFAULT_ASSETS_DIR),
        help="Directory for WAV assets",
    )
    parser.add_argument(
        "--osc-host",
        type=str,
        default=DEFAULT_OSC_HOST,
        help="OSC listen bind address",
    )
    parser.add_argument(
        "--osc-port",
        type=int,
        default=DEFAULT_OSC_PORT,
        help="OSC listen UDP port",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch the desktop hardware visualizer and control UI",
    )
    return parser.parse_args(args)


def main(args: Optional[List[str]] = None) -> None:
    parsed = parse_args(args)

    use_multicast = parsed.multicast or (parsed.e131_host is None)
    min_d = max(ABSOLUTE_MIN_DIST_MILES, parsed.min_dist)
    max_d = max(min_d + MIN_DIST_SPAN_MILES, parsed.max_dist)

    state = StormState(
        pixels=parsed.pixels,
        e131_host=parsed.e131_host,
        multicast=use_multicast,
        start_universe=parsed.universe,
        intensity=max(0.0, min(1.0, parsed.intensity)),
        min_dist_miles=min_d,
        max_dist_miles=max_d,
        override_rate=parsed.rate,
        override_rain=parsed.rain,
        master_brightness=max(0.0, min(1.0, parsed.brightness)),
        master_volume=max(0.0, min(1.0, parsed.volume)),
    )

    coordinator = StormCoordinator(
        state, parsed.assets_dir, parsed.osc_host, parsed.osc_port
    )

    if parsed.ui:
        from .ui import StormDesktopUI

        def start_async_loop() -> None:
            asyncio.run(coordinator.run())

        engine_thread = threading.Thread(target=start_async_loop, daemon=True)
        engine_thread.start()
        ui = StormDesktopUI(coordinator)
        ui.run()
    else:
        try:
            asyncio.run(coordinator.run())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
