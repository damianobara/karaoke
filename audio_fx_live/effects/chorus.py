import numpy as np
from core.effect import EffectBase


class SimpleChorus(EffectBase):
    """Chorus effect using modulated delay lines.

    Creates a 'thickening' effect by mixing the original signal
    with slightly delayed and pitch-modulated copies.
    All operations are numpy vectorized for real-time performance.
    """

    def __init__(
        self,
        rate: float = 1.5,
        depth: float = 0.3,
        wet: float = 0.5,
        sample_rate: int = 48000,
    ):
        super().__init__(name="SimpleChorus")

        self.rate = np.clip(rate, 0.1, 10.0)  # LFO rate in Hz
        self.depth = np.clip(depth, 0, 1)     # Modulation depth
        self.wet = np.clip(wet, 0, 1)
        self.sample_rate = sample_rate

        # Delay buffer (max ~50ms)
        max_delay_samples = int(0.05 * sample_rate)
        self.delay_buffer_l = np.zeros(max_delay_samples, dtype=np.float32)
        self.delay_buffer_r = np.zeros(max_delay_samples, dtype=np.float32)
        self.write_pos = 0

        # LFO phase
        self.lfo_phase = 0.0

        # Base delay time in samples (~20ms)
        self.base_delay_samples = int(0.02 * sample_rate)

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply chorus effect.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        frames = audio.shape[0]
        channels = audio.shape[1]
        output = np.zeros_like(audio)
        buffer_size = len(self.delay_buffer_l)

        # LFO phase increment per sample
        phase_increment = 2 * np.pi * self.rate / self.sample_rate

        for i in range(frames):
            # Generate LFO value (sine wave)
            lfo_value = np.sin(self.lfo_phase)
            self.lfo_phase += phase_increment
            if self.lfo_phase >= 2 * np.pi:
                self.lfo_phase -= 2 * np.pi

            # Calculate modulated delay time
            modulation = lfo_value * self.depth * self.base_delay_samples * 0.5
            delay_samples = self.base_delay_samples + modulation

            # Calculate read position with fractional delay (linear interpolation)
            read_pos_float = (self.write_pos - delay_samples) % buffer_size
            read_pos_int = int(read_pos_float)
            read_pos_next = (read_pos_int + 1) % buffer_size
            frac = read_pos_float - read_pos_int

            # Left channel
            delayed_l = self.delay_buffer_l[read_pos_int] * (1 - frac) + \
                       self.delay_buffer_l[read_pos_next] * frac
            self.delay_buffer_l[self.write_pos] = audio[i, 0]

            # Right channel (with slight phase offset for stereo width)
            lfo_value_r = np.sin(self.lfo_phase + np.pi * 0.5)
            modulation_r = lfo_value_r * self.depth * self.base_delay_samples * 0.5
            delay_samples_r = self.base_delay_samples + modulation_r

            read_pos_float_r = (self.write_pos - delay_samples_r) % buffer_size
            read_pos_int_r = int(read_pos_float_r)
            read_pos_next_r = (read_pos_int_r + 1) % buffer_size
            frac_r = read_pos_float_r - read_pos_int_r

            if channels > 1:
                delayed_r = self.delay_buffer_r[read_pos_int_r] * (1 - frac_r) + \
                           self.delay_buffer_r[read_pos_next_r] * frac_r
                self.delay_buffer_r[self.write_pos] = audio[i, 1]
            else:
                delayed_r = delayed_l

            # Mix dry and wet
            output[i, 0] = (1 - self.wet) * audio[i, 0] + self.wet * delayed_l
            if channels > 1:
                output[i, 1] = (1 - self.wet) * audio[i, 1] + self.wet * delayed_r

            self.write_pos = (self.write_pos + 1) % buffer_size

        if is_mono:
            output = output[:, 0]

        return np.clip(output, -1.0, 1.0).astype(np.float32)

    def set_rate(self, rate: float):
        """Set LFO rate in Hz (0.1 - 10.0)."""
        self.rate = np.clip(rate, 0.1, 10.0)

    def set_depth(self, depth: float):
        """Set modulation depth (0.0 = no modulation, 1.0 = maximum)."""
        self.depth = np.clip(depth, 0, 1)

    def set_wet(self, wet: float):
        """Set wet/dry mix (0.0 = fully dry, 1.0 = fully wet)."""
        self.wet = np.clip(wet, 0, 1)
