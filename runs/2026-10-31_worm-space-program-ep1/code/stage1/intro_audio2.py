"""Sound for the intro sample v2 (crown-cap medallion ident), all synthesized here, no samples.
Timeline: hook 0-2.5, ident 2.5-6.0 (epic score cut by the worm's squeak, then a final chord),
text card 6.0-9.5, story 9.5-12.0 s."""
import os, sys, math
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, sawtooth, fftconvolve
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, '..', 'voices')):
    sys.path.insert(0, p)
try:
    import worm_voice_v2 as V
except ImportError:
    import worm_voice as V

FS = V.FS
DUR = 12.0
rng = np.random.default_rng(42)
dry = np.zeros(int(DUR * FS) + 3 * FS)     # ambience, voices, comedy (small room)
epic = np.zeros_like(dry)                   # score (big hall reverb)

def lp(x, fc, o=2):
    b, a = butter(o, min(fc, FS / 2 - 100) / (FS / 2)); return lfilter(b, a, x)
def hp(x, fc, o=2):
    b, a = butter(o, fc / (FS / 2), 'high'); return lfilter(b, a, x)
def bp(x, lo, hi, o=2):
    b, a = butter(o, [lo / (FS / 2), hi / (FS / 2)], 'band'); return lfilter(b, a, x)
def put(buf, sig, t, gain=1.0):
    i = int(t * FS); e = min(len(buf), i + len(sig)); buf[i:e] += sig[:e - i] * gain
def env(n, a, r, s=1.0):
    e = np.ones(n) * s; na, nr = max(1, int(a * FS)), max(1, int(r * FS))
    e[:na] = np.linspace(0, s, na); e[n - nr:] *= np.linspace(1, 0, nr); return e
def tone(f, dur):
    return np.sin(2 * math.pi * f * np.arange(int(dur * FS)) / FS)
def saw_ens(freqs, dur, voices=3, cents=8):
    t = np.arange(int(dur * FS)) / FS; x = np.zeros_like(t)
    for f in freqs:
        for v in range(voices):
            d = 2 ** ((v - (voices - 1) / 2) * cents / 1200)
            x += sawtooth(2 * math.pi * f * d * t + rng.uniform(0, 6.28))
    return x / (len(freqs) * voices)

# ---------------- score pieces
def braam(dur=1.6, root=32.7):
    n = int(dur * FS); t = np.arange(n) / FS
    x = saw_ens([root, root * 2, root * 3, root * 4], dur, voices=4, cents=12)
    # filter opens then closes: process in blocks
    out = np.zeros(n); blk = 1024
    for i in range(0, n, blk):
        tt = i / FS; fc = 250 + 2200 * math.exp(-((tt - 0.25) / 0.35) ** 2) + 300 * math.exp(-tt * 1.2)
        out[i:i + blk] = lp(x[max(0, i - 2048):i + blk], fc, 2)[-len(out[i:i + blk]):]
    out = np.tanh(out * 3.0) * 0.6 + 0.5 * np.sin(2 * math.pi * root * t)
    return out * env(n, 0.04, 0.7)
def taiko(dur=0.6, f0=140, f1=48):
    n = int(dur * FS); t = np.arange(n) / FS
    body = np.sin(2 * math.pi * np.cumsum(f1 + (f0 - f1) * np.exp(-t * 18)) / FS) * np.exp(-t * 6)
    slap = lp(rng.standard_normal(n), 1800) * np.exp(-t * 60) * 0.6
    return (body + slap)
def crash(dur=2.2):
    n = int(dur * FS); t = np.arange(n) / FS
    return hp(rng.standard_normal(n), 3500) * np.exp(-t * 2.2) * 0.5
def choir(freqs, dur, attack=0.5):
    n = int(dur * FS); t = np.arange(n) / FS
    vib = 1 + 0.006 * np.sin(2 * math.pi * 5.2 * t)
    src = np.zeros(n)
    for f in freqs:
        for v in range(5):
            d = 2 ** ((v - 2) * 7 / 1200)
            src += sawtooth(2 * math.pi * np.cumsum(f * d * vib) / FS + rng.uniform(0, 6.28))
    src /= len(freqs) * 5
    voice = bp(src, 650, 950) * 1.0 + bp(src, 1050, 1300) * 0.6 + bp(src, 2600, 3100) * 0.25   # 'aah'
    breath = bp(rng.standard_normal(n), 900, 3500) * 0.03
    return (voice + breath) * env(n, attack, 0.5)
def brass_hit(freqs, dur=0.45, bright=1.0):
    n = int(dur * FS); t = np.arange(n) / FS
    x = saw_ens(freqs, dur, voices=3, cents=6)
    a = lp(x, 900 + 2600 * bright) * np.minimum(1, t / 0.02) * (0.55 + 0.45 * np.exp(-t * 5))
    return np.tanh(a * 2.0) * env(n, 0.01, 0.12)
def strings_ost(note, dur, step=0.125):
    out = np.zeros(int(dur * FS))
    for k, t0 in enumerate(np.arange(0, dur - 0.05, step)):
        s = lp(saw_ens([note, note * 2], 0.1, voices=3, cents=10), 1400) * env(int(0.1 * FS), 0.005, 0.05)
        i = int(t0 * FS); out[i:i + len(s)] += s * (1.0 if k % 4 == 0 else 0.65)
    return out
def riser(dur):
    n = int(dur * FS); t = np.arange(n) / FS
    nz = rng.standard_normal(n); out = np.zeros(n); blk = 2048
    for i in range(0, n, blk):
        fc = 300 + 5000 * (i / n) ** 2
        out[i:i + blk] = bp(nz[max(0, i - 4096):i + blk], fc * 0.7, fc * 1.3)[-len(out[i:i + blk]):]
    rev_cym = hp(rng.standard_normal(n), 4000) * (t / dur) ** 3
    return (out * (t / dur) ** 1.5 * 0.8 + rev_cym * 0.6)

C = {'C1': 32.7, 'C2': 65.41, 'G2': 98.0, 'C3': 130.8, 'Eb3': 155.6, 'G3': 196.0, 'Ab2': 103.8, 'Bb2': 116.5,
     'C4': 261.6, 'Eb4': 311.1, 'G4': 392.0, 'Ab3': 207.7, 'Bb3': 233.1, 'D4': 293.7, 'F4': 349.2, 'E4': 329.6, 'C5': 523.3}

# ---------------- hook: night shaft ambience (as v1) + a riser into the ident
n = int(2.6 * FS)
wind = lp(rng.standard_normal(n), 500) * (0.6 + 0.4 * np.sin(np.linspace(0, 3, n)))
put(dry, wind * env(n, 0.3, 0.2), 0.0, 0.45)
for c0 in np.arange(0.1, 2.0, 0.37):
    ch = np.zeros(int(0.12 * FS))
    for k in range(3):
        b = tone(4300 + rng.uniform(-80, 80), 0.025) * np.hanning(int(0.025 * FS)); s0 = int(k * 0.035 * FS); ch[s0:s0 + len(b)] += b
    put(dry, ch, c0 + rng.uniform(0, 0.05), 0.05)
put(dry, lp(sum(tone(f, 2.6) for f in (110, 164.8, 220, 246.9)) / 4, 900) * env(n, 1.2, 0.4), 0.0, 0.35)
for t0 in (0.45, 0.75, 1.0, 1.25, 1.5):
    put(dry, V.plop(rng, 0.05), t0, 0.5)
put(dry, lp(rng.standard_normal(int(1.2 * FS)), 300) * env(int(1.2 * FS), 0.2, 0.4), 0.4, 0.35)
put(dry, V.speak('blorp?', 'hero', seed=31) * 0.7, 1.75)
put(epic, riser(0.9), 1.6, 0.35)

# ---------------- ident 2.5-6.0: epic build, cut dead by the squeak at 4.08, final chord at 5.33
T0 = 2.5
put(epic, braam(1.7), T0, 0.9)
put(epic, taiko(0.9, 120, 40), T0, 1.0)
put(epic, crash(2.0), T0, 0.45)
put(epic, choir([C['C4'], C['Eb4'], C['G4'], C['C5']], 1.62, attack=0.35), T0 + 0.05, 0.55)
put(epic, strings_ost(C['C2'], 1.55), T0 + 0.05, 0.35)
for k, t0 in enumerate(np.arange(T0 + 0.5, 4.06, 0.25)):          # taiko ostinato, accent on the beat
    put(epic, taiko(0.45, 150 if k % 2 else 125, 52), t0, 0.75 if k % 2 == 0 else 0.5)
put(epic, brass_hit([C['Ab2'], C['C3'], C['Eb3'], C['Ab3']], 0.4, 0.8), T0 + 0.5, 0.55)
put(epic, brass_hit([C['Bb2'], C['D4'] / 2, C['F4'] / 2, C['Bb3']], 0.4, 0.9), T0 + 1.0, 0.6)
big = brass_hit([C['C3'], C['E4'] / 2, C['G3'], C['C4'], C['E4']], 0.9, 1.0)
put(epic, big, T0 + 1.42, 0.7)                                    # the big C major lands...
CUT = 4.08
cut_i = int(CUT * FS)
epic[cut_i:cut_i + int(1.24 * FS)] = 0                             # ...and is cut dead by the squeak
roar = V.speak('rawr!', 'helper', contour=(1.0, 1.55, 2.0), seed=5)
put(dry, roar, CUT, 2.1)
put(dry, V.plop(rng, 0.07), 5.22, 0.8)                             # ducks back into the soil
FIN = 5.33
put(epic, taiko(0.8, 130, 42), FIN, 1.0); put(epic, taiko(0.8, 130, 42), FIN + 0.12, 0.8)
put(epic, braam(1.4, 32.7), FIN, 0.75)
put(epic, crash(2.4), FIN, 0.5)
fin = brass_hit([C['Ab2'], C['C3'], C['Eb3']], 0.16, 0.9)
put(epic, fin, FIN, 0.45)
put(epic, brass_hit([C['Bb2'], C['D4'] / 2, C['F4'] / 2], 0.16, 0.95), FIN + 0.16, 0.5)
put(epic, brass_hit([C['C3'], C['G3'], C['C4'], C['E4'], C['G4']], 1.2, 1.0) * env(int(1.2 * FS), 0.01, 0.9), FIN + 0.32, 0.65)
put(epic, choir([C['C4'], C['E4'], C['G4'], C['C5']], 1.3, attack=0.12), FIN + 0.3, 0.5)

# ---------------- text card 6.0-9.5 (as v1, shifted), boom after the chord has rung out a bit
n = int(3.6 * FS); t = np.arange(n) / FS
boom = np.sin(2 * math.pi * (60 * np.exp(-t * 1.5) + 28) * t) * np.exp(-t * 1.2)
put(dry, boom, 6.2, 0.5)
put(dry, lp(sum(tone(f, 3.6) for f in (55, 82.4, 110)), 300) * env(n, 0.6, 0.8), 6.1, 0.16)
put(dry, lp(rng.standard_normal(n), 400) * env(n, 0.8, 0.8), 6.1, 0.13)
for k, t0 in enumerate((7.5, 7.72, 7.94)):
    b = tone(880 if k < 2 else 660, 0.12) * env(int(0.12 * FS), 0.01, 0.06)
    put(dry, V.inside_thimble(b * 3) * 0.6 + b * 0.15, t0, 0.35)

# ---------------- story 9.5-12.0 (as v1, shifted)
n = int(2.6 * FS)
put(dry, lp(rng.standard_normal(n), 250) * env(n, 0.4, 0.5), 9.5, 0.18)
buzz = tone(190, 2.4) * (0.5 + 0.5 * np.sin(2 * math.pi * 31 * np.arange(int(2.4 * FS)) / FS))
put(dry, lp(buzz, 1200) * env(int(2.4 * FS), 0.3, 0.6), 9.55, 0.04)
for t0 in np.arange(9.7, 10.5, 0.12):
    s = bp(rng.standard_normal(int(0.07 * FS)), 1500, 5000) * np.hanning(int(0.07 * FS)); put(dry, s, t0 + rng.uniform(0, 0.03), 0.04)
put(dry, V.speak('bli-pa-ta shi-mo blo-ro-pa!', 'hero', seed=11), 10.5, 0.75)

# ---------------- reverbs and mix
def hall(x, rt=2.4, seed=3):
    r = np.random.default_rng(seed); n = int(rt * FS)
    ir = r.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n); ir = lp(ir, 5000); ir[:int(0.012 * FS)] *= 0.2
    ir /= np.sqrt((ir ** 2).sum())
    return fftconvolve(x, ir)[:len(x)]
epic_wet = epic * 0.75 + hall(epic) * 0.55
epic_wet[cut_i:cut_i + int(1.24 * FS)] *= 0.0                       # the cut kills the tail too
fade = np.ones(len(epic_wet)); fi = int(6.4 * FS); fe = int(7.4 * FS)
fade[fi:fe] = np.linspace(1, 0, fe - fi); fade[fe:] = 0
epic_wet *= fade
h_end = int(2.5 * FS); dry[:h_end] *= 1.5
s_beg = int(9.5 * FS); dry[s_beg:] *= 1.5
mix = V.room(dry, rt=0.25, wet=0.12) + epic_wet
out = mix[:int(DUR * FS)]
f2 = int(0.5 * FS); out[-f2:] *= np.linspace(1, 0, f2)
out = out / (np.abs(out).max() + 1e-9) * 0.9
dst = os.path.join(HERE, 'out', 'intro', 'intro_audio2.wav')
wavfile.write(dst, FS, (out * 32767).astype(np.int16))
print('audio', round(len(out) / FS, 2), dst)
