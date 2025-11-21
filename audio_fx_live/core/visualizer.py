from abc import ABC, abstractmethod
from queue import Queue, Full
import numpy as np


class VisualizerBase(ABC):
    """Abstract base class for audio visualizers.

    Visualizers consume audio from queue.
    Must NOT block audio thread.
    Drops frames if visualization lags.
    """

    def __init__(self, name: str = "Visualizer", max_queue_size: int = 5):
        self.name = name
        self.queue: Queue = Queue(maxsize=max_queue_size)
        self.running = False

    def push_audio(self, audio: np.ndarray):
        """Push audio chunk to visualizer queue (non-blocking).

        Drops frame if queue full (no blocking in audio thread).
        """
        try:
            self.queue.put_nowait(audio.copy())
        except Full:
            # Queue full - drop frame, don't block audio
            pass

    @abstractmethod
    def run(self):
        """Main visualization loop.

        Should be called in separate thread.
        Reads from queue, displays visualization.
        """
        pass

    def stop(self):
        self.running = False
