"""engine.py - StormCoordinator orchestrating lighting, audio, scheduling, and OSC.

Central coordination engine managing asynchronous event loops for lighting rendering,
Poisson process lightning strike generation, speed-of-sound delayed audio dispatch,
and network Open Sound Control (OSC) integration.
"""

from __future__ import annotations
import asyncio
import logging
from pathlib import Path
import random
import time
from typing import Optional, Set

from .audio import AudioEngine
from .constants import (
    DEFAULT_OSC_HOST,
    DEFAULT_OSC_PORT,
    SCHEDULER_POLL_SLICE_SEC,
    ZERO_INTENSITY_EPSILON,
)
from .lighting import E131LightingEngine
from .models import StormState, StrikeEvent
from .osc_control import OSCController
from .physics import PhysicsEngine

logger = logging.getLogger("storm_sim.engine")


class StormCoordinator:
    """Main async orchestrator tying together scheduling, lighting, audio, and OSC.

    Coordinates concurrent background loops:
    1. Render loop: drives 44 FPS lighting frames to E1.31 sACN universes.
    2. Scheduler loop: models Poisson-distributed lightning strikes adapting to intensity.
    3. Delayed audio dispatcher: plays thunder after physical acoustic travel delay.
    4. OSC server: listens for incoming remote parameter updates and triggers.

    Attributes:
        state: Shared StormState instance.
        lighting: E131LightingEngine managing DMX output.
        audio: AudioEngine managing polyphonic playback.
        osc: OSCController managing UDP OSC packet dispatch.
    """

    def __init__(
        self,
        state: StormState,
        assets_dir: Optional[Path] = None,
        osc_host: str = DEFAULT_OSC_HOST,
        osc_port: int = DEFAULT_OSC_PORT,
        small_speakers: bool = False,
    ):
        """Initializes coordinator with lighting, audio, and OSC subsystems.

        Args:
            state: Shared StormState configuration.
            assets_dir: Optional path to audio samples directory.
            osc_host: Network interface for OSC UDP server (default: 0.0.0.0).
            osc_port: Port for OSC UDP server (default: 5005).
            small_speakers: If True, tunes procedural thunder for small speaker drivers.
        """
        self.state = state
        self.lighting = E131LightingEngine(state)
        self.audio = AudioEngine(state, assets_dir, small_speakers=small_speakers)
        self.osc = OSCController(
            state,
            self.trigger_strike_now,
            self.halt_all_activity,
            host=osc_host,
            port=osc_port,
        )
        self._background_tasks: Set[asyncio.Task] = set()

    def halt_all_activity(self) -> None:
        """Cancels pending delayed thunderclaps and clears active audio/lighting."""
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()
        self.lighting.clear_all()
        self.audio.clear_voices()

    def trigger_strike_now(
        self,
        forced_dist: Optional[float] = None,
        forced_epicenter: Optional[float] = None,
    ) -> None:
        """Generates and triggers an immediate physical lightning strike.

        Flashes the LED strip immediately and schedules an asynchronous delayed
        thunderclap after the acoustic travel delay (distance / speed of sound).

        Args:
            forced_dist: Optional override for strike distance in miles.
            forced_epicenter: Optional override for horizontal epicenter [0.0 - 1.0].
        """
        if self.state.is_zero_intensity:
            return

        now = time.monotonic()
        strike = PhysicsEngine.generate_strike(
            self.state, now, forced_dist, forced_epicenter
        )
        logger.info(
            "STRIKE | Dist: %.2f mi | Epicenter: %.2f | Bri: %.2f | Strokes: %d | "
            "Thunder Delay: %.2fs | LPF: %.0f Hz",
            strike.distance_miles,
            strike.epicenter,
            strike.peak_brightness,
            len(strike.strokes),
            strike.audio_delay_sec,
            strike.audio_lpf_hz,
        )
        self.lighting.trigger_flash(strike)
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._delayed_thunder(strike))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        except RuntimeError:
            # If no running event loop (e.g. called from synchronous test), schedule directly or skip
            pass

    async def _delayed_thunder(self, strike: StrikeEvent) -> None:
        """Waits for speed-of-sound propagation delay before queuing thunder audio.

        Args:
            strike: StrikeEvent containing audio delay in seconds.
        """
        try:
            await asyncio.sleep(strike.audio_delay_sec)
            if self.state.running and not self.state.is_zero_intensity:
                self.audio.schedule_thunder(strike)
        except asyncio.CancelledError:
            pass

    async def _render_loop(self) -> None:
        """Fixed-interval rendering loop updating lighting frames at target FPS."""
        frame_interval = 1.0 / self.state.fps
        was_zero = self.state.is_zero_intensity
        while self.state.running:
            t0 = time.monotonic()
            self.state.update_ramp(t0)

            is_zero = self.state.is_zero_intensity
            if is_zero and not was_zero:
                self.halt_all_activity()
            was_zero = is_zero

            self.lighting.render_frame(t0)
            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0.001, frame_interval - elapsed))

    async def _scheduler_loop(self) -> None:
        """Poisson process strike generator that adapts dynamically to intensity changes.

        Samples exponentially distributed wait times: wait_time = random.expovariate(rate).
        Polls periodically in slices to respond immediately if storm intensity ramps.
        """
        while self.state.running:
            rate = self.state.effective_rate_per_sec
            if rate <= ZERO_INTENSITY_EPSILON:
                await asyncio.sleep(SCHEDULER_POLL_SLICE_SEC)
                continue

            wait_time = random.expovariate(rate)
            slept = 0.0
            while slept < wait_time and self.state.running:
                step = min(SCHEDULER_POLL_SLICE_SEC, wait_time - slept)
                await asyncio.sleep(step)
                slept += step
                new_rate = self.state.effective_rate_per_sec
                if new_rate <= ZERO_INTENSITY_EPSILON or new_rate > rate * 2.0:
                    break

            if (
                self.state.running
                and self.state.effective_rate_per_sec > ZERO_INTENSITY_EPSILON
            ):
                self.trigger_strike_now()

    async def run(self) -> None:
        """Starts lighting, audio, and OSC subsystems and runs concurrent async task loops."""
        self.lighting.start()
        self.audio.start()
        osc_transport = await self.osc.start_server()
        try:
            await asyncio.gather(self._render_loop(), self._scheduler_loop())
        except asyncio.CancelledError:
            pass
        finally:
            self.state.running = False
            self.halt_all_activity()
            osc_transport.close()
            self.lighting.stop()
            self.audio.stop()
            logger.info("Storm Engine shut down cleanly.")

    def stop(self) -> None:
        """Cleanly stops the coordinator, halts activity, and shuts down lighting and audio subsystems."""
        self.state.running = False
        self.halt_all_activity()
        self.lighting.stop()
        self.audio.stop()
