import numpy as np
from core.effect import EffectBase


class SimpleReverb(EffectBase):
    """Simple reverb effect using multiple delay lines (Schroeder reverb).

    Simulates room acoustics with comb filters and all-pass filters.
    All operations are numpy vectorized for real-time performance.
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

        # Initialize comb filter buffers
        self.comb_buffers = [
            np.zeros(delay, dtype=np.float32) for delay in self.comb_delays
        ]
        self.comb_filter_states = [0.0] * len(self.comb_delays)
        self.comb_positions = [0] * len(self.comb_delays)

        # All-pass filter delays
        allpass_delays = [225, 556, 441, 341]
        self.allpass_delays = allpass_delays
        self.allpass_buffers = [
            np.zeros(delay, dtype=np.float32) for delay in allpass_delays
        ]
        self.allpass_positions = [0] * len(allpass_delays)

    def process(self, audio: np.ndarray) -> np.ndarray:
        """Apply reverb effect.

        Args:
            audio: shape (frames, 2) or (frames,)

        Returns:
            Processed audio with same shape
        """
        is_mono = audio.ndim == 1
        if is_mono:
            audio = audio.reshape(-1, 1)

        frames = audio.shape[0]
        output = np.zeros_like(audio)

        # Process each channel
        for ch in range(audio.shape[1]):
            channel_input = audio[:, ch]
            channel_output = np.zeros(frames, dtype=np.float32)

            # Process sample by sample for stateful filters
            for i in range(frames):
                sample = channel_input[i]

                # Comb filters (parallel)
                comb_out = 0.0
                for j, (buffer, delay) in enumerate(zip(self.comb_buffers, self.comb_delays)):
                    # Read delayed sample
                    delayed = buffer[self.comb_positions[j]]

                    # Apply damping (simple lowpass)
                    filtered = delayed * (1 - self.damping) + self.comb_filter_states[j] * self.damping
                    self.comb_filter_states[j] = filtered

                    # Write to buffer with feedback
                    buffer[self.comb_positions[j]] = sample + filtered * 0.84

                    # Update position
                    self.comb_positions[j] = (self.comb_positions[j] + 1) % delay

                    comb_out += delayed

                comb_out /= len(self.comb_buffers)

                # All-pass filters (series) for diffusion
                allpass_out = comb_out
                for j, (buffer, delay) in enumerate(zip(self.allpass_buffers, self.allpass_delays)):
                    delayed = buffer[self.allpass_positions[j]]
                    buffer[self.allpass_positions[j]] = allpass_out + delayed * 0.5
                    allpass_out = delayed - allpass_out * 0.5
                    self.allpass_positions[j] = (self.allpass_positions[j] + 1) % delay

                channel_output[i] = allpass_out

            # Mix wet and dry
            output[:, ch] = (1 - self.wet) * channel_input + self.wet * channel_output

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
