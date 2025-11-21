import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from threading import Thread
from queue import Empty
from core.visualizer import VisualizerBase


class SpectrogramVisualizer(VisualizerBase):
    """Real-time spectrogram visualization using matplotlib.

    Shows frequency content over time as a waterfall display.
    Runs in separate thread, drops frames if visualization lags.
    Non-blocking - audio thread never waits for visualization.
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        fft_size: int = 512,
        history_length: int = 100,
        name: str = "Spectrogram",
    ):
        super().__init__(name=name, max_queue_size=5)

        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.history_length = history_length
        self.running = True

        # Spectrogram data buffer (time x frequency)
        self.spectrogram_data = np.zeros((history_length, fft_size // 2))
        self.freq_bins = np.fft.fftfreq(fft_size, 1 / sample_rate)[: fft_size // 2]

    def run(self):
        """Main visualization loop (runs in separate thread)."""
        fig, ax = plt.subplots(figsize=(12, 6), tight_layout=True)
        fig.suptitle("Audio FX Live - Spectrogram (Frequency over Time)", fontsize=12)

        # Setup spectrogram display
        extent = [0, self.history_length * 0.05, 0, self.sample_rate // 2]
        im = ax.imshow(
            self.spectrogram_data.T,
            aspect="auto",
            origin="lower",
            extent=extent,
            cmap="viridis",
            vmin=0,
            vmax=60,
            interpolation="nearest",
        )

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Frequency (Hz)")
        ax.set_ylim(0, 10000)  # Focus on 0-10kHz range for better visibility

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label("Power (dB)", rotation=270, labelpad=15)

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

                # Compute FFT (power spectrum)
                window = np.hanning(len(audio))
                fft = np.fft.fft(audio * window)
                power = np.abs(fft[: len(fft) // 2])
                power_db = 20 * np.log10(power + 1e-10)

                # Shift spectrogram data (scroll down)
                self.spectrogram_data = np.roll(self.spectrogram_data, -1, axis=0)

                # Add new spectrum at the end
                self.spectrogram_data[-1, :] = power_db

            except Empty:
                # Queue empty - no new data
                pass

            # Update image
            im.set_data(self.spectrogram_data.T)

            return (im,)

        anim = animation.FuncAnimation(
            fig, animate, interval=50, blit=True, cache_frame_data=False
        )

        plt.show()
        self.running = False

    def start_threaded(self):
        """Start visualizer in background thread."""
        thread = Thread(target=self.run, daemon=True)
        thread.start()
        return thread
