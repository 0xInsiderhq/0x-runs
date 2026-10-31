"""Sound for the intro sample, all synthesized here (no samples).
Timeline: hook 0-2.5, ident 2.5-5.0, text card 5.0-8.5, story 8.5-11.0 s."""
import sys, math
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import worm_voice as V

FS = V.FS
DUR = 11.0
rng = np.random.default_rng(42)
mix = np.zeros(int(DUR * FS) + FS)

def lp(x, fc, o=2):
    b, a = butter(o, fc / (FS / 2)); return lfilter(b, a, x)
def hp(x, fc, o=2):
    b, a = butter(o, fc / (FS / 2), 'high'); return lfilter(b, a, x)
def bp(x, lo, hi, o=2):
    b, a = butter(o, [lo / (FS / 2), hi / (FS / 2)], 'band'); return lfilter(b, a, x)
def put(sig, t, gain=1.0):
    i = int(t * FS); e = min(len(mix), i + len(sig)); mix[i:e] += sig[:e - i] * gain
def env(n, a, r, sustain=1.0):
    e = np.ones(n) * sustain; na, nr = int(a * FS), int(r * FS)
    e[:na] = np.linspace(0, sustain, na); e[n - nr:] *= np.linspace(1, 0, nr); return e
def tone(freq, dur, kind='sine'):
    t = np.arange(int(dur * FS)) / FS
    if kind == 'saw':
        return sum(np.sin(2 * math.pi * freq * k * t) / k for k in range(1, 14))
    return np.sin(2 * math.pi * freq * t)

# ---------------- hook: night shaft, wind, crickets, pad, wet rise, whispered 'blorp'
n = int(2.6 * FS)
wind = lp(rng.standard_normal(n), 500) * (0.6 + 0.4 * np.sin(np.linspace(0, 3, n)))
put(wind * env(n, 0.3, 0.2), 0.0, 0.45)
for c0 in np.arange(0.1, 2.5, 0.37):
    ch = np.zeros(int(0.12 * FS))
    for k in range(3):
        b = tone(4300 + rng.uniform(-80, 80), 0.025) * np.hanning(int(0.025 * FS))
        s0 = int(k * 0.035 * FS); ch[s0:s0 + len(b)] += b
    put(ch, c0 + rng.uniform(0, 0.05), 0.05)
pad = sum(tone(f, 2.6) for f in (110, 164.8, 220, 246.9)) / 4
put(lp(pad, 900) * env(n, 1.2, 0.4), 0.0, 0.4)
for t0 in (0.45, 0.75, 1.0, 1.25, 1.5):
    put(V.plop(rng, 0.05), t0, 0.5)
gur = lp(rng.standard_normal(int(1.2 * FS)), 300) * env(int(1.2 * FS), 0.2, 0.4)
put(gur, 0.4, 0.35)
put(V.speak('blorp?', 'hero', seed=31) * 0.7, 1.75)

# ---------------- ident: fanfare cut short by the worm's tiny roar
def brass(freqs, dur, bright=1.0):
    n = int(dur * FS); t = np.arange(n) / FS
    x = sum(sum(np.sin(2 * math.pi * f * (1 + 0.003 * np.sin(2 * math.pi * 5 * t)) * k * t) / k ** 1.1 for k in range(1, 10)) for f in freqs)
    x = lp(x, 900 + 2200 * bright)
    return x * env(n, 0.03, 0.12, 1.0) / len(freqs)
def timp(dur):
    n = int(dur * FS); t = np.arange(n) / FS
    roll = sum(np.sin(2 * math.pi * (95 - 15 * t) * t) * (0.6 + 0.4 * np.sin(2 * math.pi * 18 * t)) for _ in [0])
    return lp(roll + 0.2 * rng.standard_normal(n), 400) * np.linspace(0.3, 1, n)
put(timp(1.0), 2.5, 0.45)
C, F, G = (261.6, 329.6, 392.0), (349.2, 440.0, 523.3), (392.0, 493.9, 587.3)
put(brass(C, 0.2, 0.6), 2.55, 0.35)
put(brass(F, 0.2, 0.7), 2.75, 0.35)
put(brass(G, 0.2, 0.8), 2.95, 0.38)
held = brass((261.6, 329.6, 392.0, 523.3), 0.95, 1.0)
held[int(0.27 * FS):] = 0                       # the fanfare is cut dead by the squeak
put(held, 3.15, 0.42)
roar = V.speak('rawr!', 'helper', contour=(1.0, 1.5, 1.9), seed=5)
put(roar, 3.42, 1.3)
for t0 in np.arange(2.5, 5.0, 0.5):            # cursor blink ticks
    put(tone(1800, 0.02) * np.hanning(int(0.02 * FS)), t0, 0.04)
put(V.plop(rng, 0.06), 4.62, 0.7)               # ducks back into the 0

# ---------------- text card: boom, low drone, a faint three-beep 'message'
n = int(3.6 * FS); t = np.arange(n) / FS
boom = np.sin(2 * math.pi * (60 * np.exp(-t * 1.5) + 28) * t) * np.exp(-t * 1.2)
put(boom, 5.0, 0.55)
drone = lp(sum(tone(f, 3.6) for f in (55, 82.4, 110)), 300) * env(n, 0.6, 0.8)
put(drone, 5.0, 0.18)
put(lp(rng.standard_normal(n), 400) * env(n, 0.8, 0.8), 5.0, 0.15)
for k, t0 in enumerate((6.4, 6.62, 6.84)):
    b = tone(880 if k < 2 else 660, 0.12) * env(int(0.12 * FS), 0.01, 0.06)
    put(V.inside_thimble(b * 3) * 0.6 + b * 0.15, t0, 0.35)

# ---------------- story: workshop, fireflies, charcoal scratching, the hero pitches his plan
n = int(2.6 * FS)
hum = lp(rng.standard_normal(n), 250) * env(n, 0.4, 0.5)
put(hum, 8.5, 0.18)
buzz = tone(190, 2.4) * (0.5 + 0.5 * np.sin(2 * math.pi * 31 * np.arange(int(2.4 * FS)) / FS))
put(lp(buzz, 1200) * env(int(2.4 * FS), 0.3, 0.6), 8.55, 0.04)
for t0 in np.arange(8.7, 9.5, 0.12):
    s = bp(rng.standard_normal(int(0.07 * FS)), 1500, 5000) * np.hanning(int(0.07 * FS))
    put(s, t0 + rng.uniform(0, 0.03), 0.04)
put(V.speak('bli-pa-ta shi-mo blo-ro-pa!', 'hero', seed=11), 9.5, 0.75)

out = V.room(mix[:int(DUR * FS)], rt=0.25, wet=0.12)
fade = int(0.5 * FS); out[-fade:] *= np.linspace(1, 0, fade)
out = out / (np.abs(out).max() + 1e-9) * 0.9
wavfile.write(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), 'out', 'intro', 'intro_audio.wav'),
              FS, (out * 32767).astype(np.int16))
print('audio', round(len(out) / FS, 2))
