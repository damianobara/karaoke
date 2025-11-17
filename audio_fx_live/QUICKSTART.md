# Quick Start

## Installation (1 minute)

```bash
cd audio_fx_live
pip install -r requirements.txt
```

## First Run (2 minutes)

### Step 1: Find Your Devices
```bash
python main.py --list-devices
```

Look for your microphone (has Input channels) and speaker/headphones (has Output channels).

Example output:
```
 1: Microphone (Anker PowerConf C200)
    Input channels:  2
 3: Headphones (Logi Z407)
    Output channels: 2
```

### Step 2: Run Pass-through
```bash
python main.py --input 1 --output 3
```

You should hear your microphone through the speakers with minimal delay (~21ms).

### Step 3: Add Delay Effect
Once running, try these commands:

```
[cmd] e        # Turn ON delay effect - you'll hear echo!
[cmd] w        # Make echo louder (increase wet)
[cmd] f        # Make echo repeat longer (increase feedback)
[cmd] s        # Show current settings
[cmd] q        # Quit
```

## With Visualization

To see a live waveform while processing:

```bash
python main.py --input 1 --output 3 --with-viz
```

A matplotlib window will appear showing:
- **Top graph**: Live audio waveform
- **Bottom graph**: Frequency spectrum (FFT)

Close the window to stop visualization (audio continues).

## Available Commands

| Key | Action |
|-----|--------|
| `e` | **E**nable/disable delay |
| `w` | Increase **W**et (more echo) |
| `d` | **D**ecrease wet (less echo) |
| `f` | Increase **F**eedback (longer repeats) |
| `g` | Decrease feedback |
| `v` | **V**isualizer status |
| `s` | **S**tatus - show settings |
| `?` | Show help |
| `q` | **Q**uit |

## Performance

### Expected Results
- **Latency**: ~21ms (very low - suitable for live use)
- **Underruns**: 0 (no audio dropouts)
- **CPU**: <5% on modern machine

Monitor with command `s`:
```
[cmd] s
[Status]
   Latency: 21.3ms
   Effects: SimpleDelay (ON)
   Delay wet: 0.50
   Delay feedback: 0.40
```

## Troubleshooting

### No audio
```bash
python main.py --list-devices
# Verify input/output indices and use them:
python main.py --input 1 --output 3
```

### Audio crackling/dropouts
Try reducing buffer size (lower latency):
```bash
python main.py --input 1 --output 3 --buffer 256
```

### Visualization laggy
Close the matplotlib window - it will stop drawing but audio continues unaffected.

## File Structure

```
audio_fx_live/
├── main.py              # Run this to use the app
├── config.yaml          # Edit to change default settings
├── requirements.txt     # Dependencies (pip install)
├── README.md            # Full documentation
├── QUICKSTART.md        # This file
├── core/
│   ├── engine.py        # Audio engine (180 lines)
│   ├── effect.py        # Effect base class
│   └── visualizer.py    # Visualizer base class
├── effects/
│   └── delay.py         # Delay effect
└── visualizers/
    └── waveform.py      # Waveform visualization
```

## Adding Your Own Effect

1. Create new file in `effects/`:

```python
# effects/my_effect.py
from core.effect import EffectBase
import numpy as np

class MyEffect(EffectBase):
    def __init__(self):
        super().__init__(name="MyEffect")

    def process(self, audio: np.ndarray) -> np.ndarray:
        # Your effect code here
        # Must return numpy array, same shape as input
        return audio * 0.5  # Example: reduce volume by 50%
```

2. Use in main.py:

```python
from effects.my_effect import MyEffect

my_effect = MyEffect()
engine.add_effect(my_effect)
```

Done! Your effect is now part of the effect chain and fully integrated.

## Next Steps

- Experiment with delay parameters (web, feedback, delay time)
- Add your own effects (see README.md for examples)
- Monitor performance with `[cmd] s`
- Edit `config.yaml` to change defaults

Enjoy real-time audio processing! 🎵
