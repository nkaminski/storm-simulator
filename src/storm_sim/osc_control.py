"""osc_control.py - Open Sound Control (OSC) UDP interface and command dispatcher."""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Callable, Optional

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

from .constants import (
    ABSOLUTE_MAX_DIST_MILES,
    ABSOLUTE_MIN_DIST_MILES,
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    MAX_CONFIGURABLE_PIXELS,
    MIN_DIST_SPAN_MILES,
)
from .models import StormState

logger = logging.getLogger("storm_sim.osc")


class OSCController:
    """Exposes runtime parameters and manual strike triggers over UDP OSC."""

    def __init__(
        self,
        state: StormState,
        trigger_callback: Callable[[Optional[float], Optional[float]], None],
        halt_callback: Callable[[], None],
        host: str = DEFAULT_OSC_HOST,
        port: int = DEFAULT_OSC_PORT,
    ):
        self.state = state
        self.trigger_callback = trigger_callback
        self.halt_callback = halt_callback
        self.host = host
        self.port = port
        self.dispatcher = Dispatcher()
        self._bind_routes()

    def _bind_routes(self) -> None:
        self.dispatcher.map("/storm/intensity", self._on_intensity)
        self.dispatcher.map("/storm/intensity/ramp", self._on_intensity_ramp)
        self.dispatcher.map("/storm/intensity/couple", self._on_couple)
        self.dispatcher.map("/storm/distance/min", self._on_min_dist)
        self.dispatcher.map("/storm/distance/max", self._on_max_dist)
        self.dispatcher.map("/storm/rate", self._on_rate)
        self.dispatcher.map("/storm/rain/level", self._on_rain)
        self.dispatcher.map("/storm/light/gain", self._on_brightness)
        self.dispatcher.map("/storm/audio/gain", self._on_volume)
        self.dispatcher.map("/storm/config/pixels", self._on_pixels)
        self.dispatcher.map("/storm/strike/trigger", self._on_manual_strike)

    def _on_intensity(self, addr: str, val: float) -> None:
        self.state.ramp_duration = 0.0
        self.state.intensity = max(0.0, min(1.0, float(val)))
        if self.state.is_zero_intensity:
            self.halt_callback()
            logger.info(
                "OSC: Intensity set to 0.0 -> Halted all rain, thunder, and lightning."
            )
        else:
            logger.info("OSC: Intensity set to %.2f", self.state.intensity)

    def _on_intensity_ramp(
        self, addr: str, target: float, duration_sec: float
    ) -> None:
        self.state.ramp_start_val = self.state.intensity
        self.state.ramp_target_val = max(0.0, min(1.0, float(target)))
        self.state.ramp_start_time = time.monotonic()
        self.state.ramp_duration = max(0.1, float(duration_sec))
        logger.info(
            "OSC: Ramping intensity from %.2f -> %.2f over %.1fs",
            self.state.ramp_start_val,
            self.state.ramp_target_val,
            self.state.ramp_duration,
        )

    def _on_couple(self, addr: str, *args) -> None:
        self.state.override_rate = None
        self.state.override_rain = None
        logger.info("OSC: Re-coupled rate and rain to master intensity.")

    def _on_min_dist(self, addr: str, val: float) -> None:
        self.state.min_dist_miles = max(
            ABSOLUTE_MIN_DIST_MILES,
            min(self.state.max_dist_miles - MIN_DIST_SPAN_MILES, float(val)),
        )

    def _on_max_dist(self, addr: str, val: float) -> None:
        self.state.max_dist_miles = max(
            self.state.min_dist_miles + MIN_DIST_SPAN_MILES,
            min(ABSOLUTE_MAX_DIST_MILES, float(val)),
        )

    def _on_rate(self, addr: str, val: float) -> None:
        self.state.override_rate = max(0.0, float(val))

    def _on_rain(self, addr: str, val: float) -> None:
        self.state.override_rain = max(0.0, min(1.0, float(val)))

    def _on_brightness(self, addr: str, val: float) -> None:
        self.state.master_brightness = max(0.0, min(1.0, float(val)))

    def _on_volume(self, addr: str, val: float) -> None:
        self.state.master_volume = max(0.0, min(1.0, float(val)))

    def _on_pixels(self, addr: str, val: int) -> None:
        self.state.pixels = max(1, min(MAX_CONFIGURABLE_PIXELS, int(val)))

    def _on_manual_strike(self, addr: str, *args) -> None:
        dist = float(args[0]) if len(args) >= 1 else None
        epi = float(args[1]) if len(args) >= 2 else None
        self.trigger_callback(dist, epi)

    async def start_server(self) -> AsyncIOOSCUDPServer:
        loop = asyncio.get_running_loop()
        server = AsyncIOOSCUDPServer((self.host, self.port), self.dispatcher, loop)
        transport, _ = await server.create_serve_endpoint()
        logger.info("OSC UDP Server listening on %s:%d", self.host, self.port)
        return transport
