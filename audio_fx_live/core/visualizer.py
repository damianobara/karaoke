from abc import ABC, abstractmethod
from queue import Queue, Full
from threading import Thread
from typing import Optional
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
        self._thread: Optional[Thread] = None

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

    def start_threaded(self) -> Thread:
        """Start visualizer in background thread.

        Returns the thread for later joining.
        """
        self.running = True
        self._thread = Thread(target=self.run, daemon=False)
        self._thread.start()
        return self._thread

    def stop(self):
        """Signal the visualizer to stop."""
        self.running = False

    def stop_and_wait(self, timeout: float = 2.0):
        """Stop visualizer and wait for thread to finish.

        Args:
            timeout: Maximum time to wait for thread to finish (seconds).
        """
        self.running = False
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
