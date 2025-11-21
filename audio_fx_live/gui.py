#!/usr/bin/env python3
"""
Audio FX Live - Simple GUI Launcher
A fast, lightweight Tkinter interface for running the karaoke program.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sounddevice as sd

from core.engine import AudioEngine
from effects.delay import SimpleDelay
from effects.reverb import SimpleReverb
from effects.distortion import SimpleDistortion
from effects.chorus import SimpleChorus
from visualizers.waveform import WaveformVisualizer
from visualizers.spectrogram import SpectrogramVisualizer


class KaraokeGUI:
    """Simple GUI for Audio FX Live karaoke application."""

    def __init__(self, root):
        self.root = root
        self.root.title("Audio FX Live - Karaoke")
        self.root.geometry("500x600")
        self.root.resizable(False, False)

        # State
        self.engine = None
        self.delay = None
        self.reverb = None
        self.distortion = None
        self.chorus = None
        self.visualizer = None
        self.viz_thread = None
        self.is_running = False

        # Get audio devices
        self.devices = sd.query_devices()
        self.input_devices = [(i, d['name']) for i, d in enumerate(self.devices) if d['max_input_channels'] > 0]
        self.output_devices = [(i, d['name']) for i, d in enumerate(self.devices) if d['max_output_channels'] > 0]

        self._create_ui()

    def _create_ui(self):
        """Create the UI elements."""
        # Main container with padding
        main = ttk.Frame(self.root, padding="10")
        main.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main, text="Audio FX Live", font=("Helvetica", 18, "bold"))
        title.pack(pady=(0, 10))

        # Device Selection Frame
        device_frame = ttk.LabelFrame(main, text="Audio Devices", padding="10")
        device_frame.pack(fill=tk.X, pady=5)

        # Input device
        ttk.Label(device_frame, text="Input (Microphone):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.input_var = tk.StringVar()
        self.input_combo = ttk.Combobox(device_frame, textvariable=self.input_var, state="readonly", width=45)
        self.input_combo['values'] = [f"{i}: {name[:40]}" for i, name in self.input_devices]
        if self.input_devices:
            self.input_combo.current(0)
        self.input_combo.grid(row=0, column=1, pady=2, padx=5)

        # Output device
        ttk.Label(device_frame, text="Output (Speakers):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.output_var = tk.StringVar()
        self.output_combo = ttk.Combobox(device_frame, textvariable=self.output_var, state="readonly", width=45)
        self.output_combo['values'] = [f"{i}: {name[:40]}" for i, name in self.output_devices]
        if self.output_devices:
            self.output_combo.current(0)
        self.output_combo.grid(row=1, column=1, pady=2, padx=5)

        # Settings Frame
        settings_frame = ttk.LabelFrame(main, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)

        # Buffer size
        ttk.Label(settings_frame, text="Buffer Size:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.buffer_var = tk.StringVar(value="512")
        buffer_combo = ttk.Combobox(settings_frame, textvariable=self.buffer_var, state="readonly", width=15)
        buffer_combo['values'] = ["256", "512", "1024", "2048"]
        buffer_combo.current(1)
        buffer_combo.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)

        # Visualizer
        ttk.Label(settings_frame, text="Visualizer:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=(20, 0))
        self.viz_var = tk.StringVar(value="None")
        viz_combo = ttk.Combobox(settings_frame, textvariable=self.viz_var, state="readonly", width=15)
        viz_combo['values'] = ["None", "Waveform", "Spectrogram"]
        viz_combo.current(0)
        viz_combo.grid(row=0, column=3, sticky=tk.W, pady=2, padx=5)

        # Effects Frame
        effects_frame = ttk.LabelFrame(main, text="Effects", padding="10")
        effects_frame.pack(fill=tk.X, pady=5)

        # Delay effect
        self.delay_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(effects_frame, text="Delay (Echo)", variable=self.delay_enabled,
                       command=self._toggle_delay).grid(row=0, column=0, sticky=tk.W)

        ttk.Label(effects_frame, text="Wet:").grid(row=0, column=1, padx=(20, 5))
        self.delay_wet = tk.DoubleVar(value=0.3)
        delay_wet_scale = ttk.Scale(effects_frame, from_=0, to=1, variable=self.delay_wet,
                                    length=100, command=self._update_delay)
        delay_wet_scale.grid(row=0, column=2)

        ttk.Label(effects_frame, text="Feedback:").grid(row=0, column=3, padx=(20, 5))
        self.delay_feedback = tk.DoubleVar(value=0.4)
        delay_fb_scale = ttk.Scale(effects_frame, from_=0, to=0.95, variable=self.delay_feedback,
                                   length=100, command=self._update_delay)
        delay_fb_scale.grid(row=0, column=4)

        # Reverb effect
        self.reverb_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(effects_frame, text="Reverb", variable=self.reverb_enabled,
                       command=self._toggle_reverb).grid(row=1, column=0, sticky=tk.W, pady=5)

        ttk.Label(effects_frame, text="Wet:").grid(row=1, column=1, padx=(20, 5))
        self.reverb_wet = tk.DoubleVar(value=0.3)
        reverb_wet_scale = ttk.Scale(effects_frame, from_=0, to=1, variable=self.reverb_wet,
                                     length=100, command=self._update_reverb)
        reverb_wet_scale.grid(row=1, column=2)

        # Distortion effect
        self.distortion_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(effects_frame, text="Distortion", variable=self.distortion_enabled,
                       command=self._toggle_distortion).grid(row=2, column=0, sticky=tk.W, pady=5)

        ttk.Label(effects_frame, text="Drive:").grid(row=2, column=1, padx=(20, 5))
        self.distortion_drive = tk.DoubleVar(value=5.0)
        dist_drive_scale = ttk.Scale(effects_frame, from_=1, to=20, variable=self.distortion_drive,
                                     length=100, command=self._update_distortion)
        dist_drive_scale.grid(row=2, column=2)

        # Chorus effect
        self.chorus_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(effects_frame, text="Chorus", variable=self.chorus_enabled,
                       command=self._toggle_chorus).grid(row=3, column=0, sticky=tk.W, pady=5)

        ttk.Label(effects_frame, text="Depth:").grid(row=3, column=1, padx=(20, 5))
        self.chorus_depth = tk.DoubleVar(value=0.5)
        chorus_depth_scale = ttk.Scale(effects_frame, from_=0, to=1, variable=self.chorus_depth,
                                       length=100, command=self._update_chorus)
        chorus_depth_scale.grid(row=3, column=2)

        # Control Buttons
        button_frame = ttk.Frame(main)
        button_frame.pack(fill=tk.X, pady=20)

        self.start_btn = ttk.Button(button_frame, text="Start Karaoke", command=self._start, width=20)
        self.start_btn.pack(side=tk.LEFT, padx=5, expand=True)

        self.stop_btn = ttk.Button(button_frame, text="Stop", command=self._stop, width=20, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5, expand=True)

        # Status
        status_frame = ttk.LabelFrame(main, text="Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.status_text = tk.Text(status_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.status_text.pack(fill=tk.BOTH, expand=True)

        self._log("Ready. Select devices and click 'Start Karaoke'.")

    def _log(self, message):
        """Log a message to the status area."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def _get_selected_device_index(self, combo_value, device_list):
        """Extract device index from combo selection."""
        if not combo_value:
            return None
        try:
            idx = int(combo_value.split(":")[0])
            return idx
        except (ValueError, IndexError):
            return None

    def _start(self):
        """Start the audio engine."""
        if self.is_running:
            return

        try:
            input_idx = self._get_selected_device_index(self.input_var.get(), self.input_devices)
            output_idx = self._get_selected_device_index(self.output_var.get(), self.output_devices)
            buffer_size = int(self.buffer_var.get())

            self._log(f"Starting with buffer={buffer_size}...")

            # Create engine
            self.engine = AudioEngine(
                buffer_size=buffer_size,
                sample_rate=48000,
                input_device=input_idx,
                output_device=output_idx,
                channels=2,
            )

            # Create effects
            self.delay = SimpleDelay(
                delay_ms=200,
                feedback=self.delay_feedback.get(),
                wet=self.delay_wet.get(),
                sample_rate=48000,
            )
            self.reverb = SimpleReverb(sample_rate=48000)
            self.distortion = SimpleDistortion(sample_rate=48000)
            self.chorus = SimpleChorus(sample_rate=48000)

            # Set initial states
            if not self.delay_enabled.get():
                self.delay.enabled = False
            self.reverb.enabled = self.reverb_enabled.get()
            self.distortion.enabled = self.distortion_enabled.get()
            self.chorus.enabled = self.chorus_enabled.get()

            # Create visualizer if selected
            viz_type = self.viz_var.get()
            if viz_type != "None":
                if viz_type == "Spectrogram":
                    self.visualizer = SpectrogramVisualizer(sample_rate=48000, name="Spectrogram")
                else:
                    self.visualizer = WaveformVisualizer(sample_rate=48000, name="Waveform")
                self.engine.add_visualizer(self.visualizer)

            # Start engine
            self.engine.start()

            # Add effects
            self.engine.add_effect(self.delay)
            self.engine.add_effect(self.reverb)
            self.engine.add_effect(self.distortion)
            self.engine.add_effect(self.chorus)

            # Start visualizer thread
            if self.visualizer:
                self.viz_thread = threading.Thread(target=self.visualizer.run, daemon=True)
                self.viz_thread.start()
                self._log("Visualizer started")

            self.is_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.input_combo.config(state=tk.DISABLED)
            self.output_combo.config(state=tk.DISABLED)

            self._log(f"Audio running! Latency: {self.engine.latency_ms:.1f}ms")
            self._log("Adjust effects using the sliders above.")

        except Exception as e:
            self._log(f"Error: {e}")
            messagebox.showerror("Error", f"Failed to start: {e}")

    def _stop(self):
        """Stop the audio engine."""
        if not self.is_running:
            return

        try:
            if self.engine:
                self.engine.stop()
                self.engine = None

            if self.visualizer:
                self.visualizer.stop()
                self.visualizer = None

            self.delay = None
            self.reverb = None
            self.distortion = None
            self.chorus = None

            self.is_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.input_combo.config(state="readonly")
            self.output_combo.config(state="readonly")

            self._log("Stopped.")

        except Exception as e:
            self._log(f"Error stopping: {e}")

    def _toggle_delay(self):
        """Toggle delay effect."""
        if self.delay:
            self.delay.enabled = self.delay_enabled.get()
            self._log(f"Delay: {'ON' if self.delay.enabled else 'OFF'}")

    def _toggle_reverb(self):
        """Toggle reverb effect."""
        if self.reverb:
            self.reverb.enabled = self.reverb_enabled.get()
            self._log(f"Reverb: {'ON' if self.reverb.enabled else 'OFF'}")

    def _toggle_distortion(self):
        """Toggle distortion effect."""
        if self.distortion:
            self.distortion.enabled = self.distortion_enabled.get()
            self._log(f"Distortion: {'ON' if self.distortion.enabled else 'OFF'}")

    def _toggle_chorus(self):
        """Toggle chorus effect."""
        if self.chorus:
            self.chorus.enabled = self.chorus_enabled.get()
            self._log(f"Chorus: {'ON' if self.chorus.enabled else 'OFF'}")

    def _update_delay(self, _=None):
        """Update delay parameters."""
        if self.delay:
            self.delay.set_wet(self.delay_wet.get())
            self.delay.set_feedback(self.delay_feedback.get())

    def _update_reverb(self, _=None):
        """Update reverb parameters."""
        if self.reverb:
            self.reverb.set_wet(self.reverb_wet.get())

    def _update_distortion(self, _=None):
        """Update distortion parameters."""
        if self.distortion:
            self.distortion.set_drive(self.distortion_drive.get())

    def _update_chorus(self, _=None):
        """Update chorus parameters."""
        if self.chorus:
            self.chorus.set_depth(self.chorus_depth.get())

    def on_close(self):
        """Handle window close."""
        self._stop()
        self.root.destroy()


def main():
    """Main entry point for GUI."""
    root = tk.Tk()
    app = KaraokeGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
