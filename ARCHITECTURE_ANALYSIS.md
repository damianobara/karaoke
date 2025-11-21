# Audio FX Live - Analiza Architektury

## Spis treści
1. [Architektura systemu](#1-architektura-systemu)
2. [Algorytmy efektów audio](#2-algorytmy-efektów-audio)
3. [Algorytmy wizualizacji](#3-algorytmy-wizualizacji)
4. [Model wątków i synchronizacji](#4-model-wątków-i-synchronizacji)

---

## 1. Architektura systemu

### 1.1 Struktura modułów

```
audio_fx_live/
├── core/                    # Rdzeń systemu
│   ├── engine.py           # AudioEngine - zarządzanie strumieniem audio
│   ├── effect.py           # EffectBase - klasa bazowa efektów
│   └── visualizer.py       # VisualizerBase - klasa bazowa wizualizatorów
├── effects/                 # Implementacje efektów
│   ├── delay.py            # Echo/opóźnienie (ring buffer)
│   ├── reverb.py           # Pogłos (algorytm Schroedera)
│   ├── distortion.py       # Przester (waveshaper tanh)
│   └── chorus.py           # Chorus (modulowane opóźnienie)
├── visualizers/             # Wizualizacje
│   ├── waveform.py         # Przebieg czasowy + spektrum
│   └── spectrogram.py      # Spektrogram (waterfall)
├── main.py                  # CLI entry point
└── gui.py                   # Tkinter GUI
```

### 1.2 Główny przepływ danych

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           WEJŚCIE AUDIO                                 │
│                          (Mikrofon/WASAPI)                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AudioEngine._audio_callback()                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  1. audio = indata.copy()  ← Kopiowanie bufora wejściowego      │   │
│  │                                                                  │   │
│  │  2. with effect_lock:      ← Thread-safe dostęp do łańcucha     │   │
│  │     for effect in effects:                                       │   │
│  │         audio = effect(audio)  ← Sekwencyjne przetwarzanie      │   │
│  │                                                                  │   │
│  │  3. outdata[:] = audio     ← Zapis do bufora wyjściowego        │   │
│  │                                                                  │   │
│  │  4. viz.push_audio(audio)  ← Non-blocking do wizualizatorów     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────────┬───────────────┘
                    │                                     │
                    ▼                                     ▼
┌───────────────────────────────────┐   ┌─────────────────────────────────┐
│        WYJŚCIE AUDIO              │   │     KOLEJKA WIZUALIZACJI        │
│       (Głośniki/WASAPI)           │   │    (Queue, max_size=5)          │
└───────────────────────────────────┘   └──────────────┬──────────────────┘
                                                       │
                                                       ▼
                                        ┌─────────────────────────────────┐
                                        │   Wątek wizualizacji            │
                                        │   (matplotlib animation)        │
                                        └─────────────────────────────────┘
```

### 1.3 Łańcuch efektów (Effect Chain)

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Input   │───▶│  Delay   │───▶│  Reverb  │───▶│ Distort  │───▶│  Chorus  │───▶ Output
│  Audio   │    │  (echo)  │    │ (pogłos) │    │(przester)│    │ (gruby)  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │               │
     │          [ON/OFF]        [ON/OFF]        [ON/OFF]        [ON/OFF]
     │               │               │               │               │
     │  Każdy efekt może być:                                        │
     │  - włączony (przetwarza audio)                                │
     │  - wyłączony (pass-through - zwraca oryginał)                 │
     └───────────────────────────────────────────────────────────────┘
```

---

## 2. Algorytmy efektów audio

### 2.1 Delay (Echo) - Ring Buffer

**Koncepcja:** Opóźnienie realizowane przez bufor cykliczny (ring buffer).

```
RING BUFFER (circular delay line)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
      delay_samples = 9600 (200ms @ 48kHz)

 Index:  0   1   2   3   4   5   6   7   ...  9599
       ┌───┬───┬───┬───┬───┬───┬───┬───┬─────┬───┐
Buffer │ x │ x │ x │ x │ x │ x │ x │ x │ ... │ x │
       └───┴───┴───┴───┴───┴───┴───┴───┴─────┴───┘
             ▲                           ▲
             │                           │
         read_pos                    write_pos
         (odczyt                     (zapis nowych
          opóźnionego)               próbek)

Wzór:
  read_pos = (write_pos - delay_samples) % buffer_size
```

**Algorytm przetwarzania:**

```python
# Dla każdej próbki i:
delayed[i] = buffer[read_pos]                        # Odczyt opóźnionej próbki
buffer[write_pos] = input[i] + delayed[i] * feedback # Zapis z feedbackiem
write_pos = (write_pos + 1) % buffer_size            # Przesunięcie wskaźnika

# Miksowanie wet/dry:
output = (1 - wet) * dry + wet * delayed
```

**Diagram sygnałowy:**

```
                    ┌────────────────────────────────┐
                    │          FEEDBACK              │
                    │         (0.0 - 0.99)           │
                    │              ▲                 │
                    │              │                 │
                    │         ┌────┴────┐            │
                    │         │   ×     │ ◄── feedback
                    │         └────┬────┘            │
                    │              │                 │
    input ─────┬────┼──────────────│─────────────────┼─────▶ dry
               │    │              │                 │
               │    │    ┌─────────▼─────────┐       │
               │    │    │   Ring Buffer     │       │
               │    │    │  (delay_samples)  │       │
               │    │    └─────────┬─────────┘       │
               │    │              │                 │
               │    │              ▼                 │
               │    └──────────────┴─────────────────┘
               │                   │
               │                   │ delayed
               │                   ▼
               │              ┌────────┐
               └──────────────│  MIX   │──────────▶ output
                 dry (1-wet)  │ wet/dry│   mixed
                              └────────┘
```

### 2.2 Reverb (Pogłos) - Algorytm Schroedera

**Koncepcja:** Symulacja akustyki pomieszczenia przez kombinację filtrów grzebieniowych (comb) i filtrów allpass.

```
ARCHITEKTURA REVERBU SCHROEDERA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────────────┐
                    │         8 × COMB FILTERS (równoległe)   │
                    │                                         │
              ┌─────┼──▶ Comb 1 (1557 samples) ──┐            │
              │     │                            │            │
              │┌────┼──▶ Comb 2 (1617 samples) ──┼────┐       │
              ││    │                            │    │       │
              ││┌───┼──▶ Comb 3 (1491 samples) ──┼────┼───┐   │
              │││   │                            │    │   │   │
              │││┌──┼──▶ Comb 4 (1422 samples) ──┼────┼───┼─┐ │
              ││││  │          ...               │    │   │ │ │
  input ──────┼┼┼┼──┼──▶ Comb 5-8               ─┼────┼───┼─┼─┤
              ││││  │                            │    │   │ │ │
              ││││  └────────────────────────────│────│───│─│─┘
              ││││                               │    │   │ │
              ││││         ┌────────────────────┐│    │   │ │
              ││││         │                    ▼▼    ▼   ▼ ▼
              ││││         │                  ┌────────────────┐
              ││││         │                  │   SUMA / 8     │
              ││││         │                  └───────┬────────┘
              ││││         │                          │
              ││││         │      ┌───────────────────┼───────────────────┐
              ││││         │      │    4 × ALLPASS FILTERS (szeregowe)    │
              ││││         │      │                   │                   │
              ││││         │      │    ┌─────────────▼──────────────┐    │
              ││││         │      │    │  Allpass 1 (225 samples)   │    │
              ││││         │      │    └─────────────┬──────────────┘    │
              ││││         │      │                  ▼                   │
              ││││         │      │    ┌─────────────────────────────┐   │
              ││││         │      │    │  Allpass 2 (556 samples)   │   │
              ││││         │      │    └─────────────┬──────────────┘   │
              ││││         │      │                  ▼                   │
              ││││         │      │    ┌─────────────────────────────┐   │
              ││││         │      │    │  Allpass 3-4               │   │
              ││││         │      │    └─────────────┬──────────────┘   │
              ││││         │      │                  │                   │
              ││││         │      └──────────────────┼───────────────────┘
              ││││         │                         │
              ││││         │                         ▼ reverb_out
              ││││         │                    ┌─────────┐
              └┴┴┴─────────┴────────────────────│   MIX   │────────▶ output
                   dry (1-wet)                  │ wet/dry │
                                                └─────────┘
```

**Filtr grzebieniowy (Comb Filter):**

```
COMB FILTER z damping (tłumieniem)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    feedback = 0.84
                         │
                    ┌────┴────┐
          ┌────────│    ×    │◄────────────┐
          │        └────┬────┘             │
          │             │                  │
          │    ┌────────▼────────┐         │
          │    │    Lowpass      │         │
          │    │   (damping)     │         │
          │    │                 │         │
          │    │ filtered =      │         │
          │    │   delayed*(1-d) │         │
          │    │   + prev*d      │         │
          │    └────────┬────────┘         │
          │             │                  │
          │    ┌────────▼────────┐         │
          │    │   Delay Line    │         │
          │    │  (1100-1600     │         │
          │    │   samples)      │─────────┘
          │    └────────┬────────┘
          │             │
 input ───┴─────────────▼──────────────────▶ output (delayed)

Wzór: output = delay_buffer[pos]
      delay_buffer[pos] = input + lowpass(feedback * delay_buffer[pos])
```

**Filtr Allpass:**

```
ALLPASS FILTER - dodaje "rozmycie" bez zmiany widma częstotliwości
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

          gain = 0.5
              │
         ┌────┴────┐
         │    ×    │◄──────────────────────────┐
         └────┬────┘                           │
              │                                │
 input ───────┼────────────────────┐           │
              │                    │           │
              ▼                    ▼           │
         ┌─────────┐          ┌─────────┐     │
         │    +    │          │    -    │     │
         └────┬────┘          └────┬────┘     │
              │                    │           │
              ▼                    │           │
    ┌─────────────────┐            │           │
    │   Delay Line    │────────────┼───────────┘
    │   (N samples)   │            │
    └─────────────────┘            │
                                   ▼
                                output

Wzory:
  delayed = buffer[pos]
  buffer[pos] = input + delayed * gain
  output = delayed - input * gain
```

### 2.3 Distortion (Przester) - Waveshaping

**Koncepcja:** Nieliniowe przekształcenie sygnału przez funkcję tanh() dające miękkie nasycenie.

```
WAVESHAPER - krzywa tanh()
━━━━━━━━━━━━━━━━━━━━━━━━━━

     output
       │
    +1 ┼─────────────────────────────────╭───────
       │                              ╭──╯
       │                           ╭──╯
       │                        ╭──╯
       │                     ╭──╯
       │                  ╭──╯
    0  ┼─────────────────╯────────────────────── input
       │              ╭──╯
       │           ╭──╯
       │        ╭──╯
       │     ╭──╯
       │  ╭──╯
   -1  ┼──╯───────────────────────────────────
       └──────────────────────────────────────
          -3        -1    0    1        3


Bez przesterowania (drive=1):   │  Z przesterowaniem (drive=10):
                                │
    output = tanh(input)        │  output = tanh(input × 10)
                                │
    input: -0.5  → output: -0.46│  input: -0.5 → output: -0.9999
    input: -0.1  → output: -0.1 │  input: -0.1 → output: -0.76
    input:  0.1  → output:  0.1 │  input:  0.1 → output:  0.76
    input:  0.5  → output:  0.46│  input:  0.5 → output:  0.9999
```

**Pipeline przetwarzania:**

```
┌─────────┐    ┌───────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐
│  Input  │───▶│   DRIVE   │───▶│   tanh()   │───▶│   TONE     │───▶│  LEVEL   │───▶ Output
│         │    │  (gain)   │    │ waveshaper │    │ (lowpass)  │    │ (output) │
└─────────┘    └───────────┘    └────────────┘    └────────────┘    └──────────┘
                 × drive           soft clip       filter_coef      × level
                (1-20)            (-1 to +1)       (0.1-0.9)        (0-1)

TONE CONTROL (jednobiegunowy filtr dolnoprzepustowy):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
filter_state = prev_state × (1 - coef) + input × coef

coef = 0.1 → ciemny dźwięk (silne filtrowanie wysokich)
coef = 0.9 → jasny dźwięk (minimalne filtrowanie)
```

### 2.4 Chorus - Modulowane opóźnienie

**Koncepcja:** Efekt "pogrubienia" dźwięku przez dodanie opóźnionej kopii z modulowanym czasem opóźnienia.

```
ARCHITEKTURA CHORUS
━━━━━━━━━━━━━━━━━━━

                         LFO (Low Frequency Oscillator)
                                    │
                                    ▼
                              ┌───────────┐
                              │  sin(φ)   │  φ = faza LFO
                              │ rate: 1.5Hz│
                              └─────┬─────┘
                                    │ lfo_value (-1 to +1)
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │ modulation =          │
                        │   lfo × depth ×       │
                        │   base_delay × 0.5    │
                        └───────────┬───────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │       delay_samples =         │
                    │ base_delay (960) + modulation │
                    │     ≈ 20ms ± modulacja        │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
 input ──────┬─────────────────────────────────────────────────▶ dry
             │                      │
             │             ┌────────▼────────┐
             │             │   Ring Buffer   │
             │             │ z interpolacją  │
             │             │   liniową       │
             │             └────────┬────────┘
             │                      │ delayed
             │                      ▼
             │                 ┌─────────┐
             └─────────────────│   MIX   │────────────────────▶ output
                dry (1-wet)    │ wet/dry │
                               └─────────┘


INTERPOLACJA LINIOWA (fractional delay):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pozwala na płynną zmianę czasu opóźnienia bez "skoków"

read_pos_float = 5.7  (pozycja ułamkowa)

  Index:    4        5        6        7
         ┌────┐   ┌────┐   ┌────┐   ┌────┐
Buffer:  │ A  │   │ B  │   │ C  │   │ D  │
         └────┘   └────┘   └────┘   └────┘
                     ▲        ▲
                     │   frac=0.7
                     │        │
                     └────┬───┘
                          │
         output = B × (1-0.7) + C × 0.7
                = B × 0.3 + C × 0.7


STEREO WIDTH (różnica faz):
━━━━━━━━━━━━━━━━━━━━━━━━━━
L channel: lfo_phase
R channel: lfo_phase + π/2  (90° przesunięcie)

To tworzy szerokość stereo - każdy kanał ma inny wzór modulacji
```

**Przebieg LFO w czasie:**

```
LFO sine wave @ 1.5 Hz (cykl co ~0.67s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 +1  ┼      ╭───╮              ╭───╮
     │    ╭─╯   ╰─╮          ╭─╯   ╰─╮
     │   ╱         ╲        ╱         ╲
  0  ┼──╱───────────╲──────╱───────────╲───────▶ time
     │ ╱             ╲    ╱             ╲
     │╱               ╲──╯               ╲
 -1  ┼
     │  ◀── 0.67s ──▶
     │

Delay time oscyluje między:
  min: base_delay - depth×base_delay×0.5 = 960 - 144 = 816 samples (~17ms)
  max: base_delay + depth×base_delay×0.5 = 960 + 144 = 1104 samples (~23ms)
```

---

## 3. Algorytmy wizualizacji

### 3.1 FFT (Fast Fourier Transform) - podstawy

**Koncepcja:** Transformacja sygnału z dziedziny czasu do dziedziny częstotliwości.

```
TRANSFORMACJA FOURIERA
━━━━━━━━━━━━━━━━━━━━━━

DOMENA CZASU (waveform)              DOMENA CZĘSTOTLIWOŚCI (spektrum)
━━━━━━━━━━━━━━━━━━━━━━              ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 amplitude                            magnitude (dB)
     │                                    │
     │  ╭╮ ╭╮                             │   │
     │ ╱  ╲╱  ╲   ╱╲                      │   │  │
  0  ┼╯        ╲─╱  ╲─    ──▶  FFT  ──▶  0┼───┴──┴──┬──┬─────────
     │                                    │         │  │
     └──────────────────▶                 └─────────┴──┴────────▶
        time (samples)                        frequency (Hz)

                                          440Hz  880Hz
                                          (A4)  (A5)

                                          Piki = składowe harmoniczne
```

**Pipeline FFT w wizualizatorach:**

```python
# 1. Okienkowanie (windowing) - redukcja artefaktów
window = np.hanning(fft_size)       # Okno Hanninga
windowed = audio * window            # Mnożenie przez okno

# 2. FFT
fft_result = np.fft.fft(windowed)    # Kompleksowe FFT

# 3. Magnitude (moduł)
magnitude = np.abs(fft_result)       # |Re + jIm|

# 4. Tylko dodatnie częstotliwości (symetria)
positive = magnitude[:fft_size // 2]

# 5. Skala decybelowa
power_db = 20 * np.log10(positive + 1e-10)  # dB = 20×log₁₀(mag)
                                             # +1e-10 zapobiega log(0)
```

**Okienkowanie Hanninga:**

```
OKNO HANNINGA
━━━━━━━━━━━━━

                   ┌──────────────────┐
                  ╱                    ╲
                 ╱                      ╲
    1.0  ──────╱                        ╲──────
              ╱                          ╲
             ╱                            ╲
    0.5  ───╱──────────────────────────────╲───
           ╱                                ╲
          ╱                                  ╲
    0.0  ═╱════════════════════════════════════╲═
         0      128      256      384      512
                       samples

BEZ OKNA:                  Z OKNEM:
┌────────────┐            ╭────────────╮
│            │           ╱              ╲
│  nagłe     │          ╱   łagodne     ╲
│  krawędzie │         ╱    przejścia    ╲
│            │        ╱                    ╲
└────────────┘       ╱                      ╲

→ Artefakty FFT      → Czysty wynik FFT
  (spectral leakage)   (minimalne artefakty)
```

### 3.2 Waveform Visualizer

**Architektura:**

```
┌────────────────────────────────────────────────────────────────────┐
│                     WaveformVisualizer                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  GÓRNY PANEL: Przebieg czasowy                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │ +1 ┼────────────────────────────────────────────           │   │
│  │    │      ╭╮  ╭╮     ╭╮                                     │   │
│  │    │    ╱╲╯ ╲╱  ╲   ╱  ╲  ╱╲   ╱╲                          │   │
│  │  0 ┼───╱─────────╲─╱────╲╱──╲─╱──╲────                     │   │
│  │    │ ╱                           ╲                         │   │
│  │ -1 ┼╯─────────────────────────────────                     │   │
│  │    └──────────────────────────────────▶                    │   │
│  │     0             samples           512                    │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
│  DOLNY PANEL: Spektrum mocy (FFT)                                 │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │60dB┼                                                       │   │
│  │    │    │                                                  │   │
│  │    │   ││                                                  │   │
│  │    │  │││  │                                               │   │
│  │    │ ││││  │  │                                            │   │
│  │    │ ││││ │││ ││ │                                         │   │
│  │ 0dB┼─┴┴┴┴─┴┴┴─┴┴─┴──────────────────────────               │   │
│  │    └────────────────────────────────────────▶              │   │
│  │     0Hz        10kHz                    24kHz              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Pętla animacji:**

```
┌──────────────────────────────────────────────────────────────────┐
│                    ANIMATION LOOP (50ms interval)                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. queue.get_nowait()  ─────▶  Pobierz audio (lub skip)        │
│         │                                                        │
│         │ audio[512]                                             │
│         ▼                                                        │
│  2. if stereo: audio = audio[:, 0]  ─────▶  Tylko lewy kanał    │
│         │                                                        │
│         ▼                                                        │
│  3. window = np.hanning(512)                                     │
│     fft = np.fft.fft(audio * window)                            │
│         │                                                        │
│         ▼                                                        │
│  4. power = np.abs(fft[:256])       ─────▶  Magnitude           │
│     power_db = 20 * log10(power)    ─────▶  Skala dB            │
│         │                                                        │
│         ▼                                                        │
│  5. line_wave.set_data(...)   ─────▶  Update waveform plot      │
│     line_freq.set_data(...)   ─────▶  Update spectrum plot      │
│         │                                                        │
│         ▼                                                        │
│  6. return (line_wave, line_freq)   ─────▶  Blit rendering      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 Spectrogram Visualizer

**Koncepcja:** Wyświetlanie widma częstotliwości w funkcji czasu (waterfall display).

```
SPEKTROGRAM (waterfall)
━━━━━━━━━━━━━━━━━━━━━━━

      Frequency (Hz)
           ▲
   24000 ─┤
          │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
          │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
          │  ░░░░░░░░▒▒░░░░░░░░░░░░░░░░▒▒░░░░░░░░░    <- wyższe harmoniczne
   10000 ─┤  ░░░░░░▒▒▓▓▒▒░░░░░░░░░░░▒▒▓▓▒▒░░░░░░░░
          │  ░░░░▒▒▓▓██▓▓▒▒░░░░░░▒▒▓▓██▓▓▒▒░░░░░░░
          │  ░░░▒▓▓████▓▓▒░░░░░░▒▓▓████▓▓▒░░░░░░░░
          │  ░▒▓█████████▓▒░░░▒▓█████████▓▒░░░░░░░    <- podstawowa + harmoniczne
    1000 ─┤  ▓██████████████▓██████████████▓░░░░░░
          │  █████████████████████████████████████    <- niska częstotliwość
     100 ─┤  █████████████████████████████████████
          └──────────────────────────────────────────▶ Time (s)
              0        1        2        3        4        5

Legend:  ░ = low power  ▒ = medium  ▓ = high  █ = very high
```

**Rolling buffer mechanism:**

```
SPECTROGRAM BUFFER ROLLING
━━━━━━━━━━━━━━━━━━━━━━━━━━

history_length = 100 frames
fft_size // 2 = 256 frequency bins

                     Frame 0   1   2   3   ...  98  99
                   ┌───────────────────────────────────┐
Freq bin 0  (0Hz)  │ ██  ██  ██  ██  ...  ██  ██      │ ← najnowsze
Freq bin 1  (94Hz) │ ▓▓  ▓▓  ▓▓  ██  ...  ▓▓  ▓▓      │
Freq bin 2  (188Hz)│ ▒▒  ▒▒  ▓▓  ▓▓  ...  ▒▒  ▒▒      │
...                │ ...                               │
Freq bin 255       │ ░░  ░░  ░░  ░░  ...  ░░  ░░      │
                   └───────────────────────────────────┘
                                                   ▲
                                                   │
                                            nowy frame

ROLL OPERATION (np.roll):
━━━━━━━━━━━━━━━━━━━━━━━━

Przed roll:  [frame0][frame1][frame2]...[frame99]
                                              ▲
                                         najnowszy

Po roll(-1): [frame1][frame2][frame3]...[  NEW  ]
                                              ▲
                               miejsce na nowy frame

data[-1, :] = new_spectrum  ← wstaw nowe dane
```

---

## 4. Model wątków i synchronizacji

### 4.1 Architektura wielowątkowa

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM THREADS                              │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                    AUDIO THREAD (WASAPI callback)                   ││
│  │                                                                     ││
│  │  Priority: REALTIME (najwyższy)                                    ││
│  │  Timing: każde 10.7ms (512 samples @ 48kHz)                        ││
│  │  Max processing time: ~5ms (50% buffer)                            ││
│  │                                                                     ││
│  │  KRYTYCZNE: Nie może blokować! Każde opóźnienie = underrun         ││
│  │                                                                     ││
│  │  ┌─────────────────────────────────────────────────────────────┐   ││
│  │  │  _audio_callback(indata, outdata, frames, time, status)     │   ││
│  │  │      │                                                       │   ││
│  │  │      ├──▶ effect_lock.acquire()  (blokujące, ale krótkie)   │   ││
│  │  │      ├──▶ for effect: audio = effect(audio)                 │   ││
│  │  │      ├──▶ effect_lock.release()                             │   ││
│  │  │      │                                                       │   ││
│  │  │      └──▶ viz.push_audio(audio)  (NON-BLOCKING!)            │   ││
│  │  └─────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                    │                                     │
│                                    │ Queue (max 5)                       │
│                                    │ put_nowait()                        │
│                                    │ (drop if full)                      │
│                                    ▼                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                   VISUALIZATION THREAD (matplotlib)                 ││
│  │                                                                     ││
│  │  Priority: NORMAL                                                   ││
│  │  Timing: ~50ms (20 FPS)                                            ││
│  │  MOŻE opóźniać - nie wpływa na audio                               ││
│  │                                                                     ││
│  │  ┌─────────────────────────────────────────────────────────────┐   ││
│  │  │  animate(frame)                                              │   ││
│  │  │      │                                                       │   ││
│  │  │      ├──▶ queue.get_nowait()  (NIE BLOKUJE - zwraca Empty)  │   ││
│  │  │      ├──▶ FFT + dB conversion                               │   ││
│  │  │      └──▶ matplotlib update (może być wolne)                │   ││
│  │  └─────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │                       MAIN THREAD (UI/CLI)                          ││
│  │                                                                     ││
│  │  CLI: input() blocking - czeka na komendy                          ││
│  │  GUI: Tkinter mainloop - event driven                              ││
│  │                                                                     ││
│  │  Interakcja z efektami przez Lock:                                 ││
│  │    effect_lock.acquire()                                            ││
│  │    effect.set_wet(0.5)                                             ││
│  │    effect_lock.release()                                            ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Synchronizacja - Thread Safety

```
MECHANIZMY SYNCHRONIZACJI
━━━━━━━━━━━━━━━━━━━━━━━━━

1. EFFECT CHAIN (Lock):
   ┌─────────────────────────────────────────────────────────────┐
   │  effect_lock = threading.Lock()                             │
   │                                                             │
   │  AUDIO THREAD:              MAIN THREAD:                    │
   │  ┌──────────────────┐       ┌──────────────────┐           │
   │  │ with effect_lock:│       │ with effect_lock:│           │
   │  │   for e in effs: │       │   effects.append │           │
   │  │     audio = e()  │       │     (new_effect) │           │
   │  └──────────────────┘       └──────────────────┘           │
   │          │                           │                      │
   │          └───────── MUTEX ───────────┘                      │
   │                                                             │
   │  GWARANCJA: Lista efektów nie zmieni się w trakcie         │
   │             przetwarzania audio                             │
   └─────────────────────────────────────────────────────────────┘

2. VISUALIZER QUEUE (Non-blocking):
   ┌─────────────────────────────────────────────────────────────┐
   │  queue = Queue(maxsize=5)                                   │
   │                                                             │
   │  PRODUCENT (audio thread):     KONSUMENT (viz thread):     │
   │  ┌────────────────────────┐   ┌────────────────────────┐   │
   │  │ try:                   │   │ try:                   │   │
   │  │   queue.put_nowait()   │   │   data = queue.get_    │   │
   │  │ except Full:           │   │         nowait()       │   │
   │  │   pass  # DROP FRAME   │   │ except Empty:          │   │
   │  └────────────────────────┘   │   pass  # KEEP OLD     │   │
   │                               └────────────────────────┘   │
   │                                                             │
   │  GWARANCJA: Audio thread NIGDY nie czeka na wizualizację   │
   │             Wizualizacja może "pomijać" klatki             │
   └─────────────────────────────────────────────────────────────┘
```

### 4.3 Timing diagram

```
TIME →
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUDIO CALLBACK (każde 10.7ms):
│     │     │     │     │     │     │     │     │     │
▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼
┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐   ┌─┐
│A│   │A│   │A│   │A│   │A│   │A│   │A│   │A│   │A│   │A│  (< 5ms each)
└─┘   └─┘   └─┘   └─┘   └─┘   └─┘   └─┘   └─┘   └─┘   └─┘
 │     │     │     │     │     │     │     │     │     │
 └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──▶ Queue
    │     │     │     │     │     │     │     │     │     │
    Q1    Q2    Q3    Q4    Q5   drop  drop   Q1    Q2    Q3

VIZ ANIMATION (każde 50ms):
│                    │                    │
▼                    ▼                    ▼
┌───────────┐        ┌───────────┐        ┌───────────┐
│    VIZ    │        │    VIZ    │        │    VIZ    │  (~30-50ms each)
│  (FFT +   │        │  (FFT +   │        │  (FFT +   │
│  render)  │        │  render)  │        │  render)  │
└───────────┘        └───────────┘        └───────────┘
      │                    │                    │
      └─── consume Q5 ─────┴─── consume Q3 ────┴──▶

Uwagi:
- Q1-Q5 = kolejka max 5 elementów
- "drop" = queue full, frame dropped
- VIZ zawsze bierze najnowszy dostępny frame
- Jeśli VIZ jest wolna, niektóre audio frames są pomijane (OK!)
```

---

## Podsumowanie kluczowych koncepcji

| Komponent | Algorytm | Kluczowa struktura | Złożoność |
|-----------|----------|-------------------|-----------|
| Delay | Ring buffer | Circular array | O(n) |
| Reverb | Schroeder | 8 comb + 4 allpass | O(n) |
| Distortion | Waveshaping | tanh() + lowpass | O(n) |
| Chorus | Modulated delay | LFO + interpolation | O(n) |
| Waveform | FFT | Hanning + fft | O(n log n) |
| Spectrogram | Rolling FFT | 2D buffer + fft | O(n log n) |

**Kluczowe wzorce projektowe:**
1. **Producer-Consumer** - Audio thread → Queue → Viz thread
2. **Chain of Responsibility** - Effect pipeline
3. **Template Method** - EffectBase.process() / VisualizerBase.run()
4. **Double Buffering** - Ring buffers w efektach
