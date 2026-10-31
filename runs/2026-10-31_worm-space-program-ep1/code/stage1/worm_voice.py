"""Worm gibberish voices v2, synthesized from scratch (no samples, no TTS).
v2 vs v1: soft glottal pulse instead of clicks, breath noise in the voice, per-period jitter/shimmer,
creaky grumble for the skeptic, per-syllable pitch accents, wet 'bloop' on b/p/bl/pl onsets,
4th formant for presence, per-character loudness, a breath before the hero's big speech."""
import math, random
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

FS = 44100
VOWELS = {  # F1, F2, F3, F4 (Hz) adult reference, scaled per character
    'a': (730, 1090, 2440, 3400), 'e': (530, 1840, 2480, 3500), 'i': (300, 2250, 3000, 3700),
    'o': (520, 860, 2400, 3300), 'u': (320, 800, 2250, 3300), 'y': (420, 1450, 2400, 3400),
    'm': (260, 1100, 2300, 3300),
}
CHARS = {
    #          pitch    speed       formant scale  pitch accents  breath     creak     loudness
    'hero':    dict(f0=235, speed=1.05, fscale=1.32, accent=0.14, breath=0.06, creak=0.0, gain=1.0),
    'skeptic': dict(f0=92,  speed=0.55, fscale=1.02, accent=0.04, breath=0.12, creak=0.75, gain=0.9),
    'helper':  dict(f0=360, speed=1.3,  fscale=1.62, accent=0.10, breath=0.05, creak=0.0, gain=0.75),
}

def lp(x, fc, order=2):
    b, a = butter(order, fc / (FS / 2)); return lfilter(b, a, x)

def smooth_noise(n, fc, rng):
    s = lp(rng.standard_normal(n + 2000), fc, 2)[2000:]
    return s / (np.abs(s).max() + 1e-9)

def parse(word):
    out = []
    for syl in word.split('-'):
        idx = next((i for i, c in enumerate(syl) if c in 'aeiouy'), None)
        out.append((syl.replace('m', ''), 'm') if idx is None else (syl[:idx], syl[idx]))
    return out

def syllable_track(sylls, ch, contour, rng):
    c = CHARS[ch]; n_s = len(sylls)
    f0s, F, amp, noi, ntyp, plops = [], [], [], [], [], []
    pos = 0
    for k, (onset, v) in enumerate(sylls):
        dur = rng.uniform(0.10, 0.17) / c['speed']
        if k == n_s - 1:
            dur *= 1.6
        n = int(dur * FS); t = np.linspace(0, 1, n)
        p = np.interp((k + t) / n_s, [0, 0.5, 1], contour)
        accent = 1 + c['accent'] * rng.uniform(-1, 1)          # each syllable gets its own pitch
        f0 = c['f0'] * p * accent * (1 + 0.02 * np.sin(2 * math.pi * 5.5 * np.arange(n) / FS + k))
        tgt = np.array(VOWELS[v]) * c['fscale']
        cn = int(min(0.045, dur * 0.4) * FS)
        Fk = np.tile(tgt, (n, 1)).astype(float)
        a = np.ones(n); nz = np.zeros(n); nt = 0
        if any(x in onset for x in 'bpl'):
            start = np.array([280, 700, 2100, 3200]) * c['fscale']
            g = np.clip(t * n / max(cn, 1), 0, 1)[:, None]
            Fk = start * (1 - g) + tgt * g
        if 'b' in onset or 'p' in onset:
            plops.append(pos)                                   # wet bloop at this onset
        if 'p' in onset or 't' in onset or 'k' in onset or 'h' in onset:
            n0 = int(0.016 * FS); a[:n0] = 0
            m = len(a[n0:n0 + int(0.012 * FS)]); a[n0:n0 + m] *= np.linspace(0, 1, m)
            nz[:int(0.012 * FS)] = 0.5 * np.hanning(int(0.012 * FS)); nt = 1
        if 'sh' in onset or 's' in onset:
            a[:cn] *= 0.15; nz[:cn] = 0.45 * np.hanning(2 * cn)[cn:] ** 0.3; nt = 2
        if 'r' in onset:
            a *= (0.75 + 0.25 * np.sin(2 * math.pi * 28 * np.arange(n) / FS))
        if 'm' in onset or 'n' in onset or v == 'm':
            Fk[:cn] = np.array(VOWELS['m']) * c['fscale']
        env = np.minimum(1, np.minimum(np.arange(n) / (0.012 * FS), (n - np.arange(n)) / (0.035 * FS)))
        k5 = int(0.006 * FS); a = np.convolve(a, np.ones(k5) / k5, 'same')
        f0s.append(f0); F.append(Fk); amp.append(a * env); noi.append(nz * env); ntyp += [nt] * n
        pos += n
    return (np.concatenate(f0s), np.concatenate(F), np.concatenate(amp), np.concatenate(noi),
            np.array(ntyp), plops)

def resonate(x, freqs, bw):
    y = np.zeros_like(x); y1 = y2 = 0.0
    r = math.exp(-math.pi * bw / FS); cosw = np.cos(2 * math.pi * freqs / FS); g = 1 - r
    for i in range(len(x)):
        yi = g * x[i] + 2 * r * cosw[i] * y1 - r * r * y2
        y[i] = yi; y2 = y1; y1 = yi
    return y

def glottal(f0, ch, rng):
    """Soft Rosenberg pulse with jitter/shimmer; creak = irregular low pulses with weak every-other pulse."""
    c = CHARS[ch]; n = len(f0)
    jit = 0.025 + 0.12 * c['creak']
    f = f0 * (1 + jit * smooth_noise(n, 40 + 160 * c['creak'], rng))
    ph = np.cumsum(f / FS); frac = ph % 1.0; per = ph.astype(int)
    g = np.where(frac < 0.4, 0.5 * (1 - np.cos(math.pi * frac / 0.4)),
                 np.where(frac < 0.56, np.cos(0.5 * math.pi * (frac - 0.4) / 0.16), 0.0))
    shim = 1 + 0.08 * rng.standard_normal(per.max() + 2)
    if c['creak']:
        shim[1::2] *= (1 - 0.6 * c['creak'])                   # subharmonic = vocal fry
    g = g * shim[per]
    src = np.diff(np.concatenate([[0], g])) * 30
    open_gate = (frac < 0.56).astype(float)
    breath = rng.standard_normal(n) * c['breath'] * (0.4 + open_gate)
    breath = lp(breath, 5000) - lp(breath, 400)
    return src + breath

def plop(rng, dur=0.04):
    n = int(dur * FS); tt = np.arange(n) / FS
    f = 900 * np.exp(-tt / 0.012) + 180
    return np.sin(2 * math.pi * np.cumsum(f) / FS) * np.exp(-tt / 0.01) * rng.uniform(0.25, 0.4)

def speak(words, ch, contour=(1.0, 1.08, 0.95), gap=0.06, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for w in words.split():
        sylls = parse(w.strip('!.?'))
        cont = contour
        if w.endswith('!'):
            cont = (1.0, 1.25, 1.5)
        elif w.endswith('?'):
            cont = (0.95, 0.9, 1.45)
        elif w.endswith('.'):
            cont = (1.0, 0.95, 0.72)
        f0, F, amp, nz, nt, plops = syllable_track(sylls, ch, cont, rng)
        src = glottal(f0, ch, rng)
        v = sum(resonate(src, F[:, k], bw) * w_ for k, (bw, w_) in
                enumerate([(90, 1.0), (120, 0.7), (170, 0.35), (220, 0.18)]))
        v *= amp
        noise = rng.standard_normal(len(nz)) * nz
        b, a = butter(2, [1800 / (FS / 2), 7000 / (FS / 2)], 'band'); hiss = lfilter(b, a, noise)
        burst = lp(noise, 2500)
        noise = np.where(nt == 2, hiss, burst)
        seg = v / (np.abs(v).max() + 1e-9) + 0.35 * noise
        for p0 in plops:
            pl = plop(rng); e = min(len(seg), p0 + len(pl)); seg[p0:e] += pl[:e - p0]
        out.append(seg * CHARS[ch]['gain']); out.append(np.zeros(int(gap / CHARS[ch]['speed'] * FS)))
    return np.concatenate(out)

def breath_in(dur=0.28, seed=3):
    rng = np.random.default_rng(seed); n = int(dur * FS)
    x = rng.standard_normal(n); x = lp(x, 2200) - lp(x, 500)
    env = np.sin(np.linspace(0, math.pi, n)) ** 1.5
    return x * env * 0.12

def room(x, rt=0.28, wet=0.16, seed=1):
    rng = np.random.default_rng(seed)
    n = int(rt * FS); ir = rng.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    ir = lp(ir, 3000); ir /= np.abs(ir).sum() ** 0.5 * 4
    return x + wet * np.convolve(x, ir)[:len(x)]

def inside_thimble(x):
    y = lp(x, 900, 3); d = int(0.0042 * FS); out = y.copy()
    for k in range(1, 9):
        out[k * d:] += (0.55 ** k) * y[:-k * d]
    return out

def sil(sec):
    return np.zeros(int(sec * FS))

if __name__ == '__main__':
    random.seed(7)
    # invented words: blorp = rocket, mngu = no, plui = hooray, count: blu, mo, shlip
    hero_pitch = speak('bli-pa-ta shi-mo blo-ro-pa! ta-pli bu-la-ki blorp!', 'hero', seed=11)
    skep = speak('hm-mm.', 'skeptic', contour=(1.0, 0.92, 0.8), seed=12)
    skep2 = speak('mngu.', 'skeptic', contour=(1.0, 0.95, 0.75), seed=13)
    hop = np.concatenate([speak('hop!', 'helper', seed=14), sil(0.35), speak('hop!', 'helper', seed=15), sil(0.3),
                          speak('pla-pi!', 'helper', seed=16)])
    uh = speak('e-e?', 'hero', contour=(1.0, 0.9, 1.1), seed=17)
    pf = speak('pfu.', 'hero', contour=(1.1, 1.0, 0.78), seed=18)
    count = np.concatenate([speak('blu.', 'hero', contour=(1.0, 1.0, 0.9), seed=19), sil(0.55),
                            speak('mo.', 'hero', contour=(1.08, 1.08, 0.98), seed=20), sil(0.55),
                            speak('shli-ip!', 'hero', seed=21)])
    moo = inside_thimble(speak('mu-u-u.', 'hero', contour=(0.95, 0.85, 0.65), seed=22))
    track = np.concatenate([sil(0.2), breath_in(), sil(0.05), hero_pitch, sil(0.35), skep, sil(0.9), hop, sil(0.9),
                            uh, sil(0.6), pf, sil(0.9), count, sil(1.4), skep2, sil(1.0), moo * 0.6, sil(0.6)])
    track = room(track)
    track = track / (np.abs(track).max() + 1e-9) * 0.89
    wavfile.write('worm_voices_demo.wav', FS, (track * 32767).astype(np.int16))
    print('len', round(len(track) / FS, 2))
