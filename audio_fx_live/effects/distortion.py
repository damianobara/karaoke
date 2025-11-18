import numpy as np
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

        # Simple lowpass filter for tone control
        self.filter_state_l = 0.0
        self.filter_state_r = 0.0

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply distortion effect.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        # Apply drive (pre-gain)
        gained = audio * self.drive

        # Soft clipping using tanh for smooth distortion
        distorted = np.tanh(gained)

        # Tone control (simple one-pole lowpass filter)
        # Higher tone value = brighter sound (less filtering)
        filter_coef = 0.1 + self.tone * 0.8  # Range from heavy filtering to minimal

        output = np.zeros_like(distorted)

        for ch in range(distorted.shape[1]):
            if ch == 0:
                filter_state = self.filter_state_l
            else:
                filter_state = self.filter_state_r

            # Apply simple lowpass filter sample by sample
            for i in range(distorted.shape[0]):
                filter_state = filter_state * (1 - filter_coef) + distorted[i, ch] * filter_coef
                output[i, ch] = filter_state

            if ch == 0:
                self.filter_state_l = filter_state
            else:
                self.filter_state_r = filter_state

        # Apply output level
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
