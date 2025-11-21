import numpy as np
from core.effect import EffectBase


class SimpleDelay(EffectBase):
    """Simple delay effect with feedback and wet/dry mix.

    Uses ring buffer for efficient delay line.
    All operations are numpy vectorized (no Python loops on samples).
    Handles mono and stereo input automatically.
    """

    def __init__(
        self,
        delay_ms: float = 200,
        feedback: float = 0.5,
        wet: float = 0.5,
        sample_rate: int = 48000,
    ):
        super().__init__(name="SimpleDelay")

        self.delay_ms = delay_ms
        self.feedback = np.clip(feedback, 0, 0.99)
        self.wet = np.clip(wet, 0, 1)
        self.sample_rate = sample_rate

        # Pre-allocate ring buffers (stereo max)
        delay_samples = int((delay_ms / 1000) * sample_rate)
        self.delay_buffer_l = np.zeros(delay_samples, dtype=np.float32)
        self.delay_buffer_r = np.zeros(delay_samples, dtype=np.float32)
        self.write_pos = 0

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply delay effect.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        frames = audio.shape[0]
        channels = audio.shape[1] if audio.ndim > 1 else 1
        dry = audio.copy()
        delayed = np.zeros_like(audio)

        # Read from delay buffer
        buffer_size = len(self.delay_buffer_l)

        # Process sample by sample (simple but safe)
        for i in range(frames):
            read_pos = (self.write_pos - buffer_size) % buffer_size

            # Left channel
            delayed[i, 0] = self.delay_buffer_l[read_pos]
            self.delay_buffer_l[self.write_pos] = audio[i, 0] + delayed[i, 0] * self.feedback

            # Right channel - only process if stereo
            if channels > 1:
                delayed[i, 1] = self.delay_buffer_r[read_pos]
                self.delay_buffer_r[self.write_pos] = audio[i, 1] + delayed[i, 1] * self.feedback

            self.write_pos = (self.write_pos + 1) % buffer_size

        # Mix dry and wet
        output = (1 - self.wet) * dry + self.wet * delayed

        if is_mono:
            output = output[:, 0]  # Extract first channel for mono

        return np.clip(output, -1.0, 1.0).astype(np.float32)

    def set_delay_ms(self, delay_ms: float):
        """Change delay time (in milliseconds)."""
        self.delay_ms = delay_ms

    def set_wet(self, wet: float):
        """Set wet/dry mix (0.0 = fully dry, 1.0 = fully wet)."""
        self.wet = np.clip(wet, 0, 1)

    def set_feedback(self, feedback: float):
        """Set feedback amount (0.0-0.99)."""
        self.feedback = np.clip(feedback, 0, 0.99)
