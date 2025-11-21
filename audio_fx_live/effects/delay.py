import numpy as np
from scipy import signal
from core.effect import EffectBase


class SimpleDelay(EffectBase):
    """Simple delay effect with feedback and wet/dry mix.

    Uses scipy.signal.lfilter for efficient vectorized delay processing.
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

        # Calculate delay in samples
        self.delay_samples = int((delay_ms / 1000) * sample_rate)

        # Initialize filter state for lfilter (stereo)
        self._init_filter_coefficients()
        self.zi_l = None
        self.zi_r = None

    def _init_filter_coefficients(self):
        """Initialize IIR filter coefficients for delay with feedback.

        Delay with feedback: y[n] = x[n-D] + feedback * y[n-D]
        Transfer function: H(z) = z^(-D) / (1 - feedback * z^(-D))
        """
        D = self.delay_samples
        # b coefficients: [0, 0, ..., 0, 1] (D zeros, then 1)
        self.b = np.zeros(D + 1, dtype=np.float32)
        self.b[D] = 1.0
        # a coefficients: [1, 0, 0, ..., 0, -feedback]
        self.a = np.zeros(D + 1, dtype=np.float32)
        self.a[0] = 1.0
        self.a[D] = -self.feedback

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply delay effect using vectorized scipy.signal.lfilter.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        channels = audio.shape[1]
        dry = audio.copy()
        delayed = np.zeros_like(audio)

        # Initialize filter state if needed
        if self.zi_l is None:
            self.zi_l = signal.lfilter_zi(self.b, self.a).astype(np.float32) * 0
        if self.zi_r is None:
            self.zi_r = signal.lfilter_zi(self.b, self.a).astype(np.float32) * 0

        # Process left channel - vectorized via lfilter
        delayed[:, 0], self.zi_l = signal.lfilter(self.b, self.a, audio[:, 0], zi=self.zi_l)

        # Process right channel if stereo
        if channels > 1:
            delayed[:, 1], self.zi_r = signal.lfilter(self.b, self.a, audio[:, 1], zi=self.zi_r)

        # Mix dry and wet - vectorized
        output = (1 - self.wet) * dry + self.wet * delayed

        if is_mono:
            output = output[:, 0]

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
