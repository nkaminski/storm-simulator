"""ui.py - Desktop visualizer and interactive hardware control bench.

Provides a Tkinter-based desktop interface with real-time LED array visualization,
speed-of-sound pending thunder queue tracking, click-to-strike interaction,
and live slider controls for all simulation parameters.
"""

from __future__ import annotations
import asyncio
import threading
import time
from typing import List, Optional

import numpy as np

from .constants import (
    ABSOLUTE_MAX_DIST_MILES,
    ABSOLUTE_MIN_DIST_MILES,
    CLICK_STRIKE_DEFAULT_DIST_MILES,
    DEFAULT_FPS,
    LED_CANVAS_HEIGHT,
    MAX_DISPLAY_SEGMENTS,
    UI_ACCENT_BLUE,
    UI_BG_DARK,
    UI_CANVAS_BG,
    UI_PANEL_BG,
    UI_TEXT_MAIN,
    UI_TEXT_MUTED,
    UI_WINDOW_HEIGHT,
    UI_WINDOW_WIDTH,
)
from .engine import StormCoordinator
from .models import StormState, StrikeEvent


class StormDesktopUI:
    """Native desktop hardware visualizer and control panel.

    Displays an animated canvas reflecting real-time DMX pixel values across the strip,
    live telemetry readouts, slider controls for storm intensity, lighting gain, and audio
    volume, and a queue of acoustic wavefronts in transit at the speed of sound.

    Attributes:
        coordinator: Shared StormCoordinator instance.
        state: Shared StormState configuration.
        lighting: Shared E131LightingEngine instance.
        root: Root Tk window.
        canvas: Tkinter Canvas displaying LED strip brightness.
    """

    def __init__(self, coordinator: StormCoordinator):
        """Initializes desktop UI window, styles, layout, and strike tracker hook.

        Args:
            coordinator: Running StormCoordinator instance.

        Raises:
            RuntimeError: If tkinter is not available in the current Python environment.
        """
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError as e:
            raise RuntimeError(
                "Tkinter is required to run the desktop visualizer. "
                "Install python3-tk or run headless without --ui."
            ) from e

        self.tk = tk
        self.ttk = ttk
        self.coordinator = coordinator
        self.state = coordinator.state
        self.lighting = coordinator.lighting

        self.root = tk.Tk()
        self.root.title("Storm-Sim | E1.31 Monochrome & Spatial Audio Test Bench")
        self.root.geometry(f"{UI_WINDOW_WIDTH}x{UI_WINDOW_HEIGHT}")
        self.root.configure(bg=UI_BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._tracked_strikes: List[StrikeEvent] = []
        self._patch_strike_tracker()

        self._configure_styles()
        self._build_layout()

    def _patch_strike_tracker(self) -> None:
        """Hooks the lighting engine flash trigger to track active strikes in the UI telemetry."""
        orig_trigger = self.lighting.trigger_flash

        def hooked_trigger(strike: StrikeEvent) -> None:
            orig_trigger(strike)
            self._tracked_strikes.append(strike)

        self.lighting.trigger_flash = hooked_trigger

    def _configure_styles(self) -> None:
        """Configures ttk widget styles and color scheme for dark test bench theme."""
        style = self.ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except self.tk.TclError:
            pass
        style.configure("TFrame", background=UI_BG_DARK)
        style.configure("Panel.TFrame", background=UI_PANEL_BG)
        style.configure(
            "TLabel",
            background=UI_PANEL_BG,
            foreground=UI_TEXT_MAIN,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Header.TLabel",
            background=UI_BG_DARK,
            foreground=UI_ACCENT_BLUE,
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=UI_PANEL_BG,
            foreground=UI_TEXT_MUTED,
            font=("Consolas", 9),
        )
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=6)

    def _build_layout(self) -> None:
        """Constructs visualizer canvas, parameter sliders, triggers, and telemetry."""
        # 1. Top LED Array Visualizer Section
        top_frame = self.ttk.Frame(self.root, padding=(16, 12, 16, 6))
        top_frame.pack(fill=self.tk.X)

        header_row = self.ttk.Frame(top_frame)
        header_row.pack(fill=self.tk.X, pady=(0, 6))
        self.ttk.Label(
            header_row,
            text="E1.31 MONOCHROME WHITE PIXEL ARRAY (CLICK STRIP TO TRIGGER STRIKE AT EPICENTER)",
            style="Header.TLabel",
        ).pack(side=self.tk.LEFT)
        self.lbl_fps_status = self.ttk.Label(
            header_row,
            text=f"Pixels: {self.state.pixels} | Universes: {len(self.lighting.universes)}",
            style="Muted.TLabel",
        )
        self.lbl_fps_status.configure(background=UI_BG_DARK)
        self.lbl_fps_status.pack(side=self.tk.RIGHT)

        self.canvas = self.tk.Canvas(
            top_frame,
            height=LED_CANVAS_HEIGHT,
            bg=UI_CANVAS_BG,
            highlightthickness=1,
            highlightbackground="#334155",
            cursor="crosshair",
        )
        self.canvas.pack(fill=self.tk.X)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        # 2. Main Controls & Telemetry Split
        mid_frame = self.ttk.Frame(self.root, padding=(16, 8, 16, 12))
        mid_frame.pack(fill=self.tk.BOTH, expand=True)

        # Left Column: Parameter Sliders
        ctrl_panel = self.ttk.Frame(mid_frame, style="Panel.TFrame", padding=14)
        ctrl_panel.pack(side=self.tk.LEFT, fill=self.tk.BOTH, expand=True, padx=(0, 8))

        self.var_intensity = self.tk.DoubleVar(value=self.state.intensity)
        self._add_slider(
            ctrl_panel,
            "Master Storm Intensity (0 = Killswitch)",
            self.var_intensity,
            0.0,
            1.0,
            self._on_intensity_change,
        )

        self.var_min_dist = self.tk.DoubleVar(value=self.state.min_dist_miles)
        self._add_slider(
            ctrl_panel,
            "Min Strike Distance (miles)",
            self.var_min_dist,
            ABSOLUTE_MIN_DIST_MILES,
            10.0,
            self._on_min_dist_change,
        )

        self.var_max_dist = self.tk.DoubleVar(value=self.state.max_dist_miles)
        self._add_slider(
            ctrl_panel,
            "Max Strike Distance (miles)",
            self.var_max_dist,
            0.5,
            ABSOLUTE_MAX_DIST_MILES,
            self._on_max_dist_change,
        )

        self.var_brightness = self.tk.DoubleVar(value=self.state.master_brightness)
        self._add_slider(
            ctrl_panel,
            "Master Lighting Ceiling",
            self.var_brightness,
            0.0,
            1.0,
            lambda v: setattr(self.state, "master_brightness", float(v)),
        )

        self.var_volume = self.tk.DoubleVar(value=self.state.master_volume)
        self._add_slider(
            ctrl_panel,
            "Master Audio Volume",
            self.var_volume,
            0.0,
            1.0,
            lambda v: setattr(self.state, "master_volume", float(v)),
        )

        sep = self.ttk.Separator(ctrl_panel, orient="horizontal")
        sep.pack(fill=self.tk.X, pady=10)

        has_manual = self.state.override_rain is not None or self.state.override_rate is not None
        self.var_override_enable = self.tk.BooleanVar(value=has_manual)
        chk = self.ttk.Checkbutton(
            ctrl_panel,
            text="Enable Manual Overrides (Decouple Rate & Rain from Intensity)",
            variable=self.var_override_enable,
            command=self._on_toggle_overrides,
        )
        chk.pack(anchor=self.tk.W, pady=(0, 6))

        init_rate = (
            self.state.override_rate
            if self.state.override_rate is not None
            else (self.state.effective_rate_per_sec * 60.0)
        )
        self.var_rate_override = self.tk.DoubleVar(value=init_rate)
        _, self.lbl_rate_val = self._add_slider(
            ctrl_panel,
            "Strike Rate (strikes / min)",
            self.var_rate_override,
            0.0,
            60.0,
            self._on_rate_override_change,
        )

        init_rain = (
            self.state.override_rain
            if self.state.override_rain is not None
            else self.state.effective_rain_level
        )
        self.var_rain_override = self.tk.DoubleVar(value=init_rain)
        _, self.lbl_rain_val = self._add_slider(
            ctrl_panel,
            "Rain Level [0.0 - 1.0]",
            self.var_rain_override,
            0.0,
            1.0,
            self._on_rain_override_change,
        )
        if self.state.override_rain is not None:
            self.lbl_rain_val.configure(text=f"{init_rain:.2f} (Manual)")
        else:
            self.lbl_rain_val.configure(text=f"{init_rain:.2f} (Auto)")
        if self.state.override_rate is not None:
            self.lbl_rate_val.configure(text=f"{init_rate:.1f} (Manual)")
        else:
            self.lbl_rate_val.configure(text=f"{init_rate:.1f} (Auto)")

        # Right Column: Live Telemetry & Action Triggers
        right_panel = self.ttk.Frame(
            mid_frame, style="Panel.TFrame", padding=14, width=360
        )
        right_panel.pack(side=self.tk.RIGHT, fill=self.tk.BOTH, padx=(8, 0))
        right_panel.pack_propagate(False)

        self.ttk.Label(
            right_panel,
            text="MANUAL TRIGGERS & TELEMETRY",
            font=("Segoe UI", 11, "bold"),
            foreground=UI_ACCENT_BLUE,
        ).pack(anchor=self.tk.W, pady=(0, 10))

        btn_grid = self.ttk.Frame(right_panel, style="Panel.TFrame")
        btn_grid.pack(fill=self.tk.X, pady=(0, 12))

        self.ttk.Button(
            btn_grid,
            text="⚡ Random Strike",
            command=lambda: self.coordinator.trigger_strike_now(),
        ).pack(fill=self.tk.X, pady=3)
        self.ttk.Button(
            btn_grid,
            text="💥 Overhead Bolt (0.15 mi, Center)",
            command=lambda: self.coordinator.trigger_strike_now(0.15, 0.5),
        ).pack(fill=self.tk.X, pady=3)
        self.ttk.Button(
            btn_grid,
            text="🌩️ Distant Sheet Flash (5.5 mi)",
            command=lambda: self.coordinator.trigger_strike_now(5.5, None),
        ).pack(fill=self.tk.X, pady=3)
        self.ttk.Button(
            btn_grid, text="🛑 Kill Storm (Intensity = 0)", command=self._kill_storm
        ).pack(fill=self.tk.X, pady=3)

        self.lbl_telemetry = self.ttk.Label(
            right_panel, text="", style="Muted.TLabel", justify=self.tk.LEFT
        )
        self.lbl_telemetry.pack(fill=self.tk.X, pady=(8, 8))

        self.ttk.Label(
            right_panel,
            text="PENDING THUNDER QUEUE (SPEED OF SOUND):",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor=self.tk.W, pady=(6, 4))
        self.txt_queue = self.tk.Text(
            right_panel,
            height=10,
            bg=UI_CANVAS_BG,
            fg="#38BDF8",
            font=("Consolas", 9),
            relief=self.tk.FLAT,
            padx=8,
            pady=6,
        )
        self.txt_queue.pack(fill=self.tk.BOTH, expand=True)

    def _add_slider(
        self,
        parent,
        label_text: str,
        var,
        min_v: float,
        max_v: float,
        callback,
    ) -> None:
        """Helper building a labeled horizontal slider with live numerical readout."""
        row = self.ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill=self.tk.X, pady=4)
        top = self.ttk.Frame(row, style="Panel.TFrame")
        top.pack(fill=self.tk.X)
        self.ttk.Label(top, text=label_text).pack(side=self.tk.LEFT)
        val_lbl = self.ttk.Label(top, text=f"{var.get():.2f}", style="Muted.TLabel")
        val_lbl.pack(side=self.tk.RIGHT)

        def on_slide(val_str: str) -> None:
            v = float(val_str)
            val_lbl.configure(text=f"{v:.2f}")
            callback(v)

        scale = self.ttk.Scale(
            row,
            from_=min_v,
            to=max_v,
            variable=var,
            orient=self.tk.HORIZONTAL,
            command=on_slide,
        )
        scale.pack(fill=self.tk.X, pady=(2, 0))
        return scale, val_lbl

    def _on_canvas_click(self, event) -> None:
        """Triggered when the user clicks the simulated LED canvas: fires strike at mouse X position."""
        width = max(1, self.canvas.winfo_width())
        epicenter = max(0.0, min(1.0, event.x / width))
        if self.state.is_zero_intensity:
            self.var_intensity.set(0.25)
            self.state.intensity = 0.25
        self.coordinator.trigger_strike_now(
            forced_dist=CLICK_STRIKE_DEFAULT_DIST_MILES, forced_epicenter=epicenter
        )

    def _on_intensity_change(self, val: float) -> None:
        """Callback for master intensity slider changes."""
        self.state.ramp_duration = 0.0
        self.state.intensity = val
        if self.state.is_zero_intensity:
            self.coordinator.halt_all_activity()

    def _on_min_dist_change(self, val: float) -> None:
        """Callback for minimum strike distance slider changes."""
        self.state.min_dist_miles = min(val, self.state.max_dist_miles - 0.05)

    def _on_max_dist_change(self, val: float) -> None:
        """Callback for maximum strike distance slider changes."""
        self.state.max_dist_miles = max(val, self.state.min_dist_miles + 0.05)

    def _on_toggle_overrides(self) -> None:
        """Toggles decoupled manual micro-overrides for strike rate and rain volume."""
        if self.var_override_enable.get():
            self.state.override_rate = float(self.var_rate_override.get())
            self.state.override_rain = float(self.var_rain_override.get())
            if hasattr(self, "lbl_rain_val"):
                self.lbl_rain_val.configure(text=f"{self.state.override_rain:.2f} (Manual)")
            if hasattr(self, "lbl_rate_val"):
                self.lbl_rate_val.configure(text=f"{self.state.override_rate:.1f} (Manual)")
        else:
            self.state.override_rate = None
            self.state.override_rain = None
            if hasattr(self, "lbl_rain_val"):
                eff_rain = self.state.effective_rain_level
                self.var_rain_override.set(eff_rain)
                self.lbl_rain_val.configure(text=f"{eff_rain:.2f} (Auto)")
            if hasattr(self, "lbl_rate_val"):
                eff_rate = self.state.effective_rate_per_sec * 60.0
                self.var_rate_override.set(eff_rate)
                self.lbl_rate_val.configure(text=f"{eff_rate:.1f} (Auto)")

    def _on_rate_override_change(self, val: float) -> None:
        """Callback for manual strike rate override slider."""
        self.state.override_rate = float(val)
        if hasattr(self, "var_override_enable"):
            self.var_override_enable.set(True)
        if hasattr(self, "lbl_rate_val"):
            self.lbl_rate_val.configure(text=f"{val:.1f} (Manual)")

    def _on_rain_override_change(self, val: float) -> None:
        """Callback for manual rain volume override slider."""
        self.state.override_rain = float(val)
        if hasattr(self, "var_override_enable"):
            self.var_override_enable.set(True)
        if hasattr(self, "lbl_rain_val"):
            self.lbl_rain_val.configure(text=f"{val:.2f} (Manual)")

    def _kill_storm(self) -> None:
        """Emergency killswitch: sets intensity to 0 and clears all lighting and audio."""
        self.var_intensity.set(0.0)
        self.state.intensity = 0.0
        self.coordinator.halt_all_activity()

    def _update_ui_tick(self) -> None:
        """Periodic UI refresh timer updating canvas pixels and telemetry queue."""
        if not self.state.running:
            return

        if abs(self.var_intensity.get() - self.state.intensity) > 0.005:
            self.var_intensity.set(self.state.intensity)

        # In Auto mode (manual overrides disabled), keep sliders in sync with intensity
        if hasattr(self, "var_override_enable") and not self.var_override_enable.get():
            eff_rain = self.state.effective_rain_level
            if abs(self.var_rain_override.get() - eff_rain) > 0.005:
                self.var_rain_override.set(eff_rain)
                if hasattr(self, "lbl_rain_val"):
                    self.lbl_rain_val.configure(text=f"{eff_rain:.2f} (Auto)")
            eff_rate = self.state.effective_rate_per_sec * 60.0
            if abs(self.var_rate_override.get() - eff_rate) > 0.1:
                self.var_rate_override.set(eff_rate)
                if hasattr(self, "lbl_rate_val"):
                    self.lbl_rate_val.configure(text=f"{eff_rate:.1f} (Auto)")

        self.canvas.delete("all")
        w = max(1, self.canvas.winfo_width())
        h = LED_CANVAS_HEIGHT
        dmx = self.lighting.last_frame_dmx
        n_px = len(dmx)

        n_seg = min(n_px, MAX_DISPLAY_SEGMENTS)
        seg_w = w / n_seg

        for i in range(n_seg):
            start_idx = int(i * n_px / n_seg)
            end_idx = max(start_idx + 1, int((i + 1) * n_px / n_seg))
            val = int(np.max(dmx[start_idx:end_idx]))
            disp_v = max(12, val)
            hex_col = f"#{disp_v:02x}{disp_v:02x}{disp_v:02x}"
            x0 = i * seg_w
            self.canvas.create_rectangle(
                x0, 15, x0 + seg_w + 1, h - 15, fill=hex_col, outline=""
            )

        eff_cpm = self.state.effective_rate_per_sec * 60.0
        eff_rain = self.state.effective_rain_level * 100.0
        peak_dmx = int(np.max(dmx)) if len(dmx) else 0
        self.lbl_telemetry.configure(
            text=(
                f"Effective Strike Rate : {eff_cpm:5.1f} / min\n"
                f"Effective Rain Level  : {eff_rain:5.1f} %\n"
                f"Current Peak DMX Byte : {peak_dmx:3d} / 255\n"
                f"Active Thunder Voices : {len(self.coordinator.audio.active_voices)}"
            )
        )

        now = time.monotonic()
        active_lines: List[str] = []
        surviving_strikes: List[StrikeEvent] = []
        for st in self._tracked_strikes:
            rem = (st.timestamp + st.audio_delay_sec) - now
            if rem > 0.0 and not self.state.is_zero_intensity:
                surviving_strikes.append(st)
                active_lines.append(
                    f"Dist: {st.distance_miles:4.2f}mi | X: {st.epicenter:4.2f} | "
                    f"LPF: {st.audio_lpf_hz:4.0f}Hz | Impact: {rem:4.1f}s"
                )
        self._tracked_strikes = surviving_strikes

        self.txt_queue.delete("1.0", self.tk.END)
        if active_lines:
            self.txt_queue.insert(self.tk.END, "\n".join(active_lines))
        else:
            self.txt_queue.insert(self.tk.END, "No thunder wave fronts in transit...")

        self.root.after(int(1000 / DEFAULT_FPS), self._update_ui_tick)

    def _on_close(self) -> None:
        """Window close handler: cleanly stops simulation and destroys window."""
        self.state.running = False
        self.coordinator.halt_all_activity()
        self.root.destroy()

    def run(self) -> None:
        """Starts the Tkinter UI event loop."""
        self.root.after(50, self._update_ui_tick)
        self.root.mainloop()


def run_ui_app(
    coordinator: Optional[StormCoordinator] = None,
    state: Optional[StormState] = None,
) -> None:
    """GUI script entry point for storm-sim-ui.

    Args:
        coordinator: Optional existing StormCoordinator instance.
        state: Optional existing StormState instance if coordinator is not provided.
    """
    if coordinator is None:
        if state is None:
            state = StormState()
        coordinator = StormCoordinator(state)

    def start_async_loop() -> None:
        asyncio.run(coordinator.run())

    engine_thread = threading.Thread(target=start_async_loop, daemon=True)
    engine_thread.start()
    ui = StormDesktopUI(coordinator)
    ui.run()
