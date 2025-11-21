import numpy as np
from scipy import signal
from core.effect import EffectBase


class SimpleDistortion(EffectBase):
    """Distortion effect using waveshaping/clipping.

    Provides adjustable overdrive/distortion with tone control.
    All operations are numpy vectorized for real-time performance.
    """

    def __init__(
        self,
        drive: float = 5.0,
        tone: float = 0.5,
        level: float = 0.5,
        sample_rate: int = 48000,
    ):
        super().__init__(name="SimpleDistortion")

        self.drive = np.clip(drive, 1.0, 20.0)
        self.tone = np.clip(tone, 0, 1)
        self.level = np.clip(level, 0, 1)
        self.sample_rate = sample_rate

        # Initialize filter state for lfilter (stereo)
        self.zi_l = None
        self.zi_r = None

    def _get_filter_coefficients(self):
        """Get one-pole lowpass filter coefficients based on tone setting.

        One-pole lowpass: y[n] = (1-a)*y[n-1] + a*x[n]
        Transfer function: H(z) = a / (1 - (1-a)*z^(-1))
        """
        filter_coef = 0.1 + self.tone * 0.8  # Range from heavy filtering to minimal
        b = np.array([filter_coef], dtype=np.float32)
        a = np.array([1.0, -(1 - filter_coef)], dtype=np.float32)
        return b, a

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply distortion effect using vectorized operations.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        channels = audio.shape[1]

        # Apply drive (pre-gain) - vectorized
        gained = audio * self.drive

        # Soft clipping using tanh for smooth distortion - vectorized
        distorted = np.tanh(gained)

        # Tone control using vectorized lfilter
        b, a = self._get_filter_coefficients()

        # Initialize filter states if needed
        if self.zi_l is None:
            self.zi_l = signal.lfilter_zi(b, a).astype(np.float32) * 0
        if self.zi_r is None:
            self.zi_r = signal.lfilter_zi(b, a).astype(np.float32) * 0

        output = np.zeros_like(distorted)

        # Process left channel - vectorized via lfilter
        output[:, 0], self.zi_l = signal.lfilter(b, a, distorted[:, 0], zi=self.zi_l)

        # Process right channel if stereo
        if channels > 1:
            output[:, 1], self.zi_r = signal.lfilter(b, a, distorted[:, 1], zi=self.zi_r)

        # Apply output level - vectorized
        output = output * self.level

        if is_mono:
            output = output[:, 0]

        return np.clip(output, -1.0, 1.0).astype(np.float32)

    def set_drive(self, drive: float):
        """Set drive amount (1.0 = clean, 20.0 = heavy distortion)."""
        self.drive = np.clip(drive, 1.0, 20.0)

    def set_tone(self, tone: float):
        """Set tone (0.0 = dark/mellow, 1.0 = bright)."""
        self.tone = np.clip(tone, 0, 1)

    def set_level(self, level: float):
        """Set output level (0.0 = silent, 1.0 = full)."""
        self.level = np.clip(level, 0, 1)
