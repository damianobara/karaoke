import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from queue import Empty
from core.visualizer import VisualizerBase


class WaveformVisualizer(VisualizerBase):
    """Real-time waveform visualization using matplotlib.

    Runs in separate thread, drops frames if visualization lags.
    Non-blocking - audio thread never waits for visualization.
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        fft_size: int = 512,
        name: str = "Waveform",
    ):
        super().__init__(name=name, max_queue_size=5)

        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.running = True

        # Plot data buffers
        self.waveform_data = np.zeros(fft_size)
        self.freq_data = np.zeros(fft_size // 2)

    def run(self):
        """Main visualization loop (runs in separate thread)."""
        fig, (ax_wave, ax_freq) = plt.subplots(
            2, 1, figsize=(10, 6), tight_layout=True
        )
        fig.suptitle("Audio FX Live - Waveform & Spectrum", fontsize=12)

        # Waveform plot
        ax_wave.set_ylim(-1, 1)
        ax_wave.set_xlim(0, self.fft_size)
        ax_wave.set_ylabel("Amplitude")
        ax_wave.grid(True, alpha=0.3)
        (line_wave,) = ax_wave.plot([], [], lw=1, color="cyan")

        # Frequency plot (power spectrum)
        ax_freq.set_ylim(0, 60)
        ax_freq.set_xlim(0, self.sample_rate // 2)
        ax_freq.set_xlabel("Frequency (Hz)")
        ax_freq.set_ylabel("dB")
        ax_freq.grid(True, alpha=0.3)
        (line_freq,) = ax_freq.plot([], [], lw=1, color="lime")

        def animate(frame):
            """Update animation frame."""
            try:
                # Get latest audio chunk from queue
                audio = self.queue.get_nowait()

                # Extract one channel if stereo
                if audio.ndim > 1:
                    audio = audio[:, 0]

                # Pad or trim to fft_size
                if len(audio) < self.fft_size:
                    audio = np.pad(audio, (0, self.fft_size - len(audio)))
                else:
                    audio = audio[: self.fft_size]

                self.waveform_data = audio

                # Compute FFT (power spectrum)
                window = np.hanning(len(audio))
                fft = np.fft.fft(audio * window)
                power = np.abs(fft[: len(fft) // 2])
                power_db = 20 * np.log10(power + 1e-10)
                self.freq_data = power_db

            except Empty:
                # Queue empty - no new data
                pass

            # Update plots
            line_wave.set_data(np.arange(len(self.waveform_data)), self.waveform_data)
            line_freq.set_data(
                np.fft.fftfreq(self.fft_size, 1 / self.sample_rate)[
                    : len(self.freq_data)
                ],
                self.freq_data,
            )

            return line_wave, line_freq

        anim = animation.FuncAnimation(
            fig, animate, interval=50, blit=True, cache_frame_data=False
        )

        plt.show()
        self.running = False
