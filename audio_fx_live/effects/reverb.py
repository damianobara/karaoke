import numpy as np
from scipy import signal
from core.effect import EffectBase


class SimpleReverb(EffectBase):
    """Simple reverb effect using multiple delay lines (Schroeder reverb).

    Simulates room acoustics with comb filters and all-pass filters.
    All operations are numpy vectorized using scipy.signal.lfilter.
    """

    def __init__(
        self,
        room_size: float = 0.5,
        damping: float = 0.5,
        wet: float = 0.3,
        sample_rate: int = 48000,
    ):
        super().__init__(name="SimpleReverb")

        self.room_size = np.clip(room_size, 0, 1)
        self.damping = np.clip(damping, 0, 1)
        self.wet = np.clip(wet, 0, 1)
        self.sample_rate = sample_rate

        # Comb filter delay times (in samples) - prime numbers for natural sound
        base_delays = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
        self.comb_delays = [int(d * (0.5 + room_size * 1.5)) for d in base_delays]

        # All-pass filter delays
        self.allpass_delays = [225, 556, 441, 341]

        # Initialize filter coefficients and states
        self._init_filters()

    def _init_filters(self):
        """Initialize IIR filter coefficients for comb and allpass filters."""
        feedback = 0.84
        damping_coef = self.damping

        # Comb filters with damping (lowpass in feedback loop)
        # H(z) = z^(-D) / (1 - g*(1-d + d*z^(-1))*z^(-D))
        # Simplified: use lfilter with proper coefficients
        self.comb_b = []
        self.comb_a = []
        self.comb_zi = []

        for delay in self.comb_delays:
            # Comb filter: y[n] = x[n-D] + g * lowpass(y[n-D])
            # We approximate with a simpler IIR structure
            b = np.zeros(delay + 1, dtype=np.float32)
            b[delay] = 1.0

            a = np.zeros(delay + 2, dtype=np.float32)
            a[0] = 1.0
            a[delay] = -feedback * (1 - damping_coef)
            a[delay + 1] = -feedback * damping_coef

            self.comb_b.append(b)
            self.comb_a.append(a)
            self.comb_zi.append(None)

        # All-pass filters: H(z) = (-g + z^(-D)) / (1 - g*z^(-D))
        self.allpass_b = []
        self.allpass_a = []
        self.allpass_zi = []
        allpass_g = 0.5

        for delay in self.allpass_delays:
            b = np.zeros(delay + 1, dtype=np.float32)
            b[0] = -allpass_g
            b[delay] = 1.0

            a = np.zeros(delay + 1, dtype=np.float32)
            a[0] = 1.0
            a[delay] = -allpass_g

            self.allpass_b.append(b)
            self.allpass_a.append(a)
            self.allpass_zi.append(None)

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply reverb effect using vectorized scipy.signal.lfilter.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        output = np.zeros_like(audio)

        # Process each channel
        for ch in range(audio.shape[1]):
            channel_input = audio[:, ch]

            # Parallel comb filters - vectorized
            comb_sum = np.zeros_like(channel_input)
            for j in range(len(self.comb_delays)):
                # Initialize filter state if needed
                if self.comb_zi[j] is None:
                    self.comb_zi[j] = signal.lfilter_zi(
                        self.comb_b[j], self.comb_a[j]
                    ).astype(np.float32) * 0

                comb_out, self.comb_zi[j] = signal.lfilter(
                    self.comb_b[j], self.comb_a[j], channel_input, zi=self.comb_zi[j]
                )
                comb_sum += comb_out

            comb_sum /= len(self.comb_delays)

            # Series all-pass filters for diffusion - vectorized
            allpass_out = comb_sum
            for j in range(len(self.allpass_delays)):
                # Initialize filter state if needed
                if self.allpass_zi[j] is None:
                    self.allpass_zi[j] = signal.lfilter_zi(
                        self.allpass_b[j], self.allpass_a[j]
                    ).astype(np.float32) * 0

                allpass_out, self.allpass_zi[j] = signal.lfilter(
                    self.allpass_b[j], self.allpass_a[j], allpass_out, zi=self.allpass_zi[j]
                )

            # Mix wet and dry - vectorized
            output[:, ch] = (1 - self.wet) * channel_input + self.wet * allpass_out

        if is_mono:
            output = output[:, 0]

        return np.clip(output, -1.0, 1.0).astype(np.float32)

    def set_room_size(self, room_size: float):
        """Set room size (0.0 = small, 1.0 = large)."""
        self.room_size = np.clip(room_size, 0, 1)

    def set_damping(self, damping: float):
        """Set damping amount (0.0 = bright, 1.0 = dark)."""
        self.damping = np.clip(damping, 0, 1)

    def set_wet(self, wet: float):
        """Set wet/dry mix (0.0 = fully dry, 1.0 = fully wet)."""
        self.wet = np.clip(wet, 0, 1)
