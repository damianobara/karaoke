# Tickets - Audio FX Live

## TICKET-001: Logic Bug - Delay Effect Uses Wrong Channel Buffer for Mono Audio
**Severity:** CRITICAL
**File:** `audio_fx_live/effects/delay.py`
**Lines:** 63-68

### Problem Description
When processing mono audio (single channel), the delay effect incorrectly uses `delay_buffer_r` (right channel buffer) instead of reusing `delay_buffer_l` (left channel buffer).

### Code with Bug
```python
if channels > 1:
    delayed[i, 1] = self.delay_buffer_r[read_pos]
    self.delay_buffer_r[self.write_pos] = audio[i, 1] + delayed[i, 1] * self.feedback
else:
    # BUG: Using right channel buffer for mono signal!
    delayed[i, 0] = self.delay_buffer_r[read_pos]
    self.delay_buffer_r[self.write_pos] = audio[i, 0] + delayed[i, 0] * self.feedback
```

### Impact
- Mono input audio is processed with uninitialized/stale data from right channel buffer
- Produces incorrect delay output for mono signals
- Audio artifacts and unexpected behavior

### Expected Behavior
Mono signals should only use `delay_buffer_l`. The right channel buffer should not be involved when `channels == 1`.

### Suggested Fix
```python
# Left channel processing (already correct)
delayed[i, 0] = self.delay_buffer_l[read_pos]
self.delay_buffer_l[self.write_pos] = audio[i, 0] + delayed[i, 0] * self.feedback

# Right channel - only process if stereo
if channels > 1:
    delayed[i, 1] = self.delay_buffer_r[read_pos]
    self.delay_buffer_r[self.write_pos] = audio[i, 1] + delayed[i, 1] * self.feedback
```

---

## TICKET-002: Bare Exception Handlers Hide Real Errors
**Severity:** HIGH
**Files:**
- `audio_fx_live/core/effect.py:42`
- `audio_fx_live/core/visualizer.py:26`
- `audio_fx_live/visualizers/waveform.py:78`
- `audio_fx_live/visualizers/spectrogram.py:88`

### Problem Description
Multiple files use bare `except:` or overly broad `except Exception` handlers that catch ALL exceptions, including `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`. This makes debugging extremely difficult as real errors are silently swallowed.

### Code Examples

**effect.py:42**
```python
except Exception as e:
    print(f"[ERROR] {self.name}: {e} - skipping effect")
    return audio  # Silently continues with unprocessed audio
```

**visualizer.py:26**
```python
try:
    self.queue.put_nowait(audio.copy())
except:  # Bare except catches EVERYTHING
    pass
```

**waveform.py:78 & spectrogram.py:88**
```python
try:
    audio = self.queue.get_nowait()
except:  # Should only catch queue.Empty
    pass
```

### Impact
- `Ctrl+C` (KeyboardInterrupt) may not work properly
- Real bugs are hidden - no stack traces, no logging
- System-level exceptions (`SystemExit`) are caught and ignored
- Makes production debugging nearly impossible

### Suggested Fix
Replace with specific exception types:

```python
# For queue operations
from queue import Empty, Full

try:
    self.queue.put_nowait(audio.copy())
except Full:
    pass  # Expected - queue is full, drop frame

try:
    audio = self.queue.get_nowait()
except Empty:
    pass  # Expected - no new data available

# For effect processing
except (RuntimeError, ValueError, TypeError) as e:
    logging.error(f"{self.name}: {e}")
    return audio
```

---

## TICKET-003: Race Condition - Unprotected Access to Shared `latency_ms`
**Severity:** HIGH
**Files:**
- `audio_fx_live/core/engine.py:89` (write)
- `audio_fx_live/main.py:129` (read)

### Problem Description
The `latency_ms` attribute is written in `engine.start()` and potentially updated during audio processing, but is read from the main thread in `main.py` without any synchronization mechanism. This creates a data race condition.

### Code with Bug

**engine.py (write without lock):**
```python
def start(self):
    # ...
    self.latency_ms = (self.buffer_size / self.sample_rate) * 1000 * 2
```

**main.py (read without lock):**
```python
print(f"   Latency: {engine.latency_ms:.1f}ms")
```

### Impact
- Potential torn reads (reading partial value during write)
- Undefined behavior in multi-threaded context
- Could display incorrect latency values
- On some architectures, could cause crashes

### Suggested Fix
Add a threading lock to protect shared state:

```python
# In engine.py __init__
from threading import Lock
self._latency_lock = Lock()

# In engine.py start()
with self._latency_lock:
    self.latency_ms = (self.buffer_size / self.sample_rate) * 1000 * 2

# Add property accessor
@property
def latency_ms_safe(self) -> float:
    with self._latency_lock:
        return self._latency_ms

# In main.py
print(f"   Latency: {engine.latency_ms_safe:.1f}ms")
```

---

## TICKET-004: Performance Violation - Python Loops on Audio Samples
**Severity:** HIGH
**Files:**
- `audio_fx_live/effects/delay.py:55-70`
- `audio_fx_live/effects/reverb.py:67-97`
- `audio_fx_live/effects/distortion.py:55-69`
- `audio_fx_live/effects/chorus.py:60-104`

### Problem Description
All audio effects use Python `for` loops to process individual samples, which directly violates the documented requirement in docstrings: "ZERO Python loops on samples" and "Use only numpy operations".

Python loops are orders of magnitude slower than vectorized NumPy operations, causing latency spikes and potential audio dropouts in real-time processing.

### Code Examples

**delay.py:55-70**
```python
for i in range(frames):  # Loop over every sample!
    read_pos = (self.write_pos - buffer_size) % buffer_size
    delayed[i, 0] = self.delay_buffer_l[read_pos]
    # ... more per-sample operations
    self.write_pos = (self.write_pos + 1) % buffer_size
```

**reverb.py:67-97 (NESTED loops)**
```python
for i in range(frames):  # Outer loop
    sample = channel_input[i]
    for j, (buffer, delay) in enumerate(zip(self.comb_buffers, ...)):  # Inner loop (8x)
        # Per-sample comb filter processing
```

**chorus.py:60-104**
```python
for i in range(frames):
    lfo_value = np.sin(self.lfo_phase)  # np.sin called per sample!
    # ... per-sample delay interpolation
```

### Impact
- Latency requirement (<1ms) cannot be met
- Audio dropouts and glitches during playback
- CPU usage much higher than necessary
- Poor user experience with real-time audio

### Performance Comparison
| Operation | Python Loop | NumPy Vectorized |
|-----------|-------------|------------------|
| 1024 samples | ~500μs | ~5μs |
| Speedup | - | **100x faster** |

### Suggested Fix (Example for Chorus LFO)
```python
# BEFORE (slow)
for i in range(frames):
    lfo_value = np.sin(self.lfo_phase)
    self.lfo_phase += phase_increment

# AFTER (fast - vectorized)
lfo_phases = self.lfo_phase + np.arange(frames) * phase_increment
lfo_values = np.sin(lfo_phases)  # Single vectorized call
self.lfo_phase = lfo_phases[-1] % (2 * np.pi)
```

Note: Some stateful operations (delay buffers) cannot be fully vectorized but can be optimized using `scipy.signal.lfilter` or Cython/Numba JIT compilation.

---

## TICKET-005: Resource Leak - Visualizer Threads Not Properly Cleaned Up
**Severity:** MEDIUM
**Files:**
- `audio_fx_live/visualizers/waveform.py:102-104`
- `audio_fx_live/visualizers/spectrogram.py:104-108`
- `audio_fx_live/main.py:149-152`

### Problem Description
Visualizer threads are started as daemon threads but are never properly joined or cleaned up when the application exits. Additionally, matplotlib figures are not explicitly closed, causing potential resource leaks.

### Code with Bug

**waveform.py:102-104**
```python
def start_threaded(self):
    thread = Thread(target=self.run, daemon=True)
    thread.start()
    return thread  # Thread reference returned but never joined
```

**main.py:149-152**
```python
finally:
    engine.stop()
    if viz:
        viz.stop()
    # viz_thread is NEVER joined!
    # matplotlib figures are NEVER closed!
```

### Impact
- Threads may continue running after main program exits
- Daemon threads are killed abruptly without cleanup
- Matplotlib figures accumulate in memory if visualizer is restarted
- Potential hang on exit if thread is stuck
- Resource leaks over extended usage

### Suggested Fix

**In visualizer classes:**
```python
def start_threaded(self):
    self.running = True
    self._thread = Thread(target=self.run, daemon=False)
    self._thread.start()
    return self._thread

def stop_and_wait(self, timeout: float = 2.0):
    self.running = False
    if hasattr(self, '_thread') and self._thread.is_alive():
        self._thread.join(timeout=timeout)
```

**In main.py:**
```python
finally:
    engine.stop()
    if viz:
        viz.stop()
    if viz_thread and viz_thread.is_alive():
        viz_thread.join(timeout=2.0)
    plt.close('all')  # Clean up matplotlib
```

---

## TICKET-006: Inaccurate Latency Calculation
**Severity:** MEDIUM
**File:** `audio_fx_live/core/engine.py`
**Line:** 89

### Problem Description
The latency calculation only considers buffer size and arbitrarily multiplies by 2, ignoring actual device latency reported by the audio driver.

### Code with Bug
```python
self.latency_ms = (self.buffer_size / self.sample_rate) * 1000 * 2
```

### Problems
1. The `* 2` multiplier is not explained or justified
2. Ignores actual input/output device latency from `sd.Stream.latency`
3. Provides misleading information to users
4. Different audio interfaces have vastly different latencies

### Impact
- Users see incorrect latency values
- Cannot accurately troubleshoot audio sync issues
- Professional users may distrust the application

### Suggested Fix
```python
def start(self):
    self.stream = sd.Stream(...)
    self.stream.start()

    # Calculate accurate latency
    if self.stream:
        input_latency = self.stream.latency[0]   # seconds
        output_latency = self.stream.latency[1]  # seconds
        buffer_latency = self.buffer_size / self.sample_rate

        total_latency_sec = input_latency + output_latency + buffer_latency
        self.latency_ms = total_latency_sec * 1000
```

---

## TICKET-007: No Device Validation Before Stream Creation
**Severity:** MEDIUM
**File:** `audio_fx_live/core/engine.py`
**Lines:** 96-103

### Problem Description
The audio engine creates a stream with user-provided device indices without validating that those devices actually exist. Invalid devices only fail at runtime with cryptic error messages.

### Code with Bug
```python
def start(self):
    self.stream = sd.Stream(
        device=(self.input_device, self.output_device),  # No validation!
        samplerate=self.sample_rate,
        # ...
    )
```

### Impact
- Cryptic error messages from sounddevice library
- No guidance to user on how to fix the issue
- Poor user experience
- Application crashes instead of graceful handling

### Suggested Fix
```python
def start(self):
    # Validate devices before creating stream
    devices = sd.query_devices()

    if self.input_device is not None:
        if self.input_device < 0 or self.input_device >= len(devices):
            raise ValueError(f"Invalid input device index: {self.input_device}. "
                           f"Use --list-devices to see available devices.")
        if devices[self.input_device]['max_input_channels'] < 1:
            raise ValueError(f"Device {self.input_device} has no input channels.")

    if self.output_device is not None:
        if self.output_device < 0 or self.output_device >= len(devices):
            raise ValueError(f"Invalid output device index: {self.output_device}. "
                           f"Use --list-devices to see available devices.")
        if devices[self.output_device]['max_output_channels'] < 1:
            raise ValueError(f"Device {self.output_device} has no output channels.")

    try:
        self.stream = sd.Stream(...)
    except Exception as e:
        raise RuntimeError(f"Failed to open audio stream: {e}")
```

---

## TICKET-008: Missing Logging Module - Using print() for Errors
**Severity:** LOW
**Files:** Multiple files throughout codebase

### Problem Description
The codebase uses `print()` statements for error messages instead of Python's `logging` module. This makes it impossible to configure log levels, redirect output, or integrate with logging infrastructure.

### Example
```python
# Current (bad)
print(f"[ERROR] {self.name}: {e} - skipping effect")

# Should be
logging.error(f"{self.name}: {e} - skipping effect")
```

### Impact
- Cannot disable debug output in production
- Cannot redirect logs to file
- Cannot integrate with monitoring systems
- Inconsistent error reporting

### Suggested Fix
1. Add logging configuration in main.py
2. Replace all print() error messages with logging calls
3. Use appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

```python
import logging

# In main.py
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# In effect files
logger = logging.getLogger(__name__)
logger.error(f"{self.name}: {e} - skipping effect")
```

---

## Summary

| Ticket | Severity | Component | Issue |
|--------|----------|-----------|-------|
| TICKET-001 | CRITICAL | delay.py | Wrong channel buffer for mono |
| TICKET-002 | HIGH | Multiple | Bare exception handlers |
| TICKET-003 | HIGH | engine.py, main.py | Race condition on latency_ms |
| TICKET-004 | HIGH | All effects | Python loops violate requirements |
| TICKET-005 | MEDIUM | Visualizers | Thread/resource cleanup |
| TICKET-006 | MEDIUM | engine.py | Inaccurate latency calculation |
| TICKET-007 | MEDIUM | engine.py | No device validation |
| TICKET-008 | LOW | Multiple | Using print() instead of logging |
