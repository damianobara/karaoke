from abc import ABC, abstractmethod
import numpy as np


class EffectBase(ABC):
    """Abstract base class for audio effects.

    All effects MUST process audio in < 1ms.
    Use only numpy operations - NO Python loops on samples.
    """

    def __init__(self, name: str = "Effect", enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def process(self, audio: np.ndarray) -> np.ndarray:
        """Process audio chunk.

        Args:
            audio: numpy array, shape (frames,) or (frames, channels)

        Returns:
            Processed audio with same shape
        """
        pass

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def toggle(self):
        self.enabled = not self.enabled

    def __call__(self, audio: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return audio
        try:
            return self.process(audio)
        except Exception as e:
            print(f"[ERROR] {self.name}: {e} - skipping effect")
            return audio
