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
        """Apply chorus effect using vectorized numpy operations.

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
        buffer_size = len(self.delay_buffer_l)

        # Generate all LFO phases at once - vectorized
        phase_increment = 2 * np.pi * self.rate / self.sample_rate
        lfo_phases = self.lfo_phase + np.arange(frames) * phase_increment

        # Generate LFO values for left and right channels - vectorized
        lfo_values_l = np.sin(lfo_phases)
        lfo_values_r = np.sin(lfo_phases + np.pi * 0.5)  # Phase offset for stereo

        # Update LFO phase for next block
        self.lfo_phase = (lfo_phases[-1] + phase_increment) % (2 * np.pi) if frames > 0 else self.lfo_phase

        # Calculate modulated delay times - vectorized
        modulation_l = lfo_values_l * self.depth * self.base_delay_samples * 0.5
        modulation_r = lfo_values_r * self.depth * self.base_delay_samples * 0.5
        delay_samples_l = self.base_delay_samples + modulation_l
        delay_samples_r = self.base_delay_samples + modulation_r

        # Calculate write positions for all samples - vectorized
        write_positions = (self.write_pos + np.arange(frames)) % buffer_size

        # Calculate read positions with fractional delay - vectorized
        read_pos_float_l = (write_positions - delay_samples_l) % buffer_size
        read_pos_int_l = read_pos_float_l.astype(np.int32)
        read_pos_next_l = (read_pos_int_l + 1) % buffer_size
        frac_l = read_pos_float_l - read_pos_int_l

        read_pos_float_r = (write_positions - delay_samples_r) % buffer_size
        read_pos_int_r = read_pos_float_r.astype(np.int32)
        read_pos_next_r = (read_pos_int_r + 1) % buffer_size
        frac_r = read_pos_float_r - read_pos_int_r

        # Read from delay buffers with linear interpolation - vectorized
        delayed_l = (self.delay_buffer_l[read_pos_int_l] * (1 - frac_l) +
                    self.delay_buffer_l[read_pos_next_l] * frac_l)

        if channels > 1:
            delayed_r = (self.delay_buffer_r[read_pos_int_r] * (1 - frac_r) +
                        self.delay_buffer_r[read_pos_next_r] * frac_r)
        else:
            delayed_r = delayed_l

        # Write to delay buffers - vectorized
        self.delay_buffer_l[write_positions] = audio[:, 0]
        if channels > 1:
            self.delay_buffer_r[write_positions] = audio[:, 1]

        # Update write position for next block
        self.write_pos = (self.write_pos + frames) % buffer_size

        # Mix dry and wet - vectorized
        output = np.zeros_like(audio)
        output[:, 0] = (1 - self.wet) * audio[:, 0] + self.wet * delayed_l
        if channels > 1:
            output[:, 1] = (1 - self.wet) * audio[:, 1] + self.wet * delayed_r

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
