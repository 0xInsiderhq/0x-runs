"""Episode 1 draft sound for the animatic (stage 2). All synthesized, no samples.
0-9.5 s: the approved intro score, run unchanged from stage1/intro_audio3.py (hook, ident, text card).
9.5-34.0 s: the story (animatic time = story time + 7.0), same synth tools, voices from worm_voice.py (approved 28.10).
Writes  out/ep1_draft_A.wav       music cuts out at the explosion, full silence after it (episode 1 plan)
        out/ep1_draft_B.wav       music never stops, drops low after the explosion (Dima's 30.10 rule, whole episode)
        out/ep1_voices_env.json   loudness of each worm's voice per animatic frame: drives the head pulse
LAYOUT=x (Dima 31.10, v2): the short cut for X. Logo 2 s, card 2 s, story from 6.5 s (story time + 4.0).
  The intro score is rebuilt for that layout (same parts, ident and card events squeezed by 2/3.5, sustained
  parts shortened to match), not cut, so it runs on without a jump. Writes out/ep1_draft_A_x.wav, ep1_draft_B_x.wav;
  the head-pulse json is only written for the full layout (the story frames are the same).
usage: python3 ep1_audio.py            LAYOUT=x python3 ep1_audio.py"""
import os, sys, json, math
import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
ST1 = os.path.join(os.path.dirname(HERE), 'stage1')
sys.path.insert(0, HERE)
import ep1_timing as TM

LAYOUT = os.environ.get('LAYOUT', 'full')
SHIFT = TM.INTRO_SHIFT if LAYOUT == 'full' else 4.0
TOTAL = TM.END + SHIFT
SUFFIX = '' if LAYOUT == 'full' else '_x'
src = open(os.path.join(ST1, 'intro_audio3.py'), encoding='utf-8').read()
if LAYOUT == 'full':
    # ---------------- intro 0-9.5 s: approved v3 score, everything before its 9.5 s story sample
    intro = src.split('# ---------------- story 9.5-12.0')[0].replace('DUR = 12.0', f'DUR = {TOTAL}')
else:
    # only the tools and buffers of intro_audio3; the score itself is laid out below for the short cut
    intro = src.split('# ---------------- one continuous bed')[0].replace('DUR = 12.0', f'DUR = {TOTAL}')
g = {'__file__': os.path.join(ST1, 'intro_audio3.py'), '__name__': 'intro_part'}
exec(compile(intro, 'intro_audio3.py', 'exec'), g)
V, FS, rng = g['V'], g['FS'], g['rng']
dry, epic, vox = g['dry'], g['epic'], g['vox']
put, env, tone, C = g['put'], g['env'], g['tone'], g['C']
braam, taiko, crash, choir = g['braam'], g['taiko'], g['crash'], g['choir']
brass_hit, strings_ost, riser, pad, pluck = g['brass_hit'], g['strings_ost'], g['riser'], g['pad'], g['pluck']
lp, hp, bp, hall = g['lp'], g['hp'], g['bp'], None
EV = TM.EV


def A(t):
    """story seconds -> animatic seconds"""
    return t + SHIFT


def intro_x():
    """intro_audio3's score laid out for the X cut: hook 0-2.5 as is, ident 2.5-4.5, card 4.5-6.5, story from 6.5.
    Event times inside the ident and the card are squeezed by K; sustained parts (pads, choir, strings, risers)
    are shortened by K too; one-shot hits (taiko, crash, brass, braam) keep their own length and ring on."""
    K = 2.0 / 3.5
    I = lambda t: 2.5 + (t - 2.5) * K          # ident time 2.5-6.0 -> 2.5-4.5
    Cd = lambda t: 4.5 + (t - 6.0) * K         # card time 6.0-9.5 -> 4.5-6.5
    bed = [(0.0, 2.6, [C['C3'], C['Eb3'], C['G3']], 700, 0.22),
           (I(2.45), I(4.1), [C['C3'], C['Eb3'], C['G3'], C['C4']], 1400, 0.3),
           (I(3.95), I(5.45), [C['Ab2'], C['C3'], C['Eb3'], C['Ab3']], 1500, 0.3),
           (I(5.3), Cd(6.25), [C['C3'], C['E4'] / 2, C['G3'], C['C4']], 1600, 0.3),
           (Cd(6.0), Cd(9.65), [C['C2'], C['G2'], C['C3'], C['Eb3']], 520, 0.26),
           (9.45 - 3.0, 10.8 - 3.0, [C['Eb2'] * 2, C['G3'], C['Bb3']], 1000, 0.2),
           (10.65 - 3.0, 12.0 - 3.0, [C['Ab2'], C['C3'], C['Eb3']], 1000, 0.2)]
    for t0, t1, fr, fc, gn in bed:
        put(epic, pad(fr, t1 - t0, fc), t0, gn)
    put(epic, 0.35 * np.sin(2 * math.pi * C['C1'] * np.arange(int(9 * FS)) / FS) * env(int(9 * FS), 1.5, 1.0), 0.0, 0.25)
    # hook 0-2.5: exactly as approved
    put(epic, strings_ost(C['C2'], 1.9), 0.6, 0.14)
    for t0, gn in ((1.0, 0.25), (1.5, 0.3), (2.0, 0.4), (2.25, 0.45)):
        put(epic, taiko(0.5, 120, 45), t0, gn)
    put(epic, choir([C['C4'], C['Eb4'], C['G4']], 2.4, attack=1.4), 0.1, 0.18)
    put(epic, riser(0.9), 1.6, 0.35)
    n = int(2.6 * FS)
    wind = lp(rng.standard_normal(n), 500) * (0.6 + 0.4 * np.sin(np.linspace(0, 3, n)))
    put(dry, wind * env(n, 0.3, 0.2), 0.0, 0.35)
    for c0 in np.arange(0.1, 2.0, 0.37):
        ch = np.zeros(int(0.12 * FS))
        for k in range(3):
            b = tone(4300 + rng.uniform(-80, 80), 0.025) * np.hanning(int(0.025 * FS)); s0 = int(k * 0.035 * FS); ch[s0:s0 + len(b)] += b
        put(dry, ch, c0 + rng.uniform(0, 0.05), 0.05)
    for t0 in (0.45, 0.75, 1.0, 1.25, 1.5):
        put(dry, V.plop(rng, 0.05), t0, 0.55)
    put(vox, V.speak('blorp?', 'hero', seed=31), 1.75, 0.95)
    # ident 2.5-4.5
    T0 = 2.5
    put(epic, braam(1.7), T0, 0.9); put(epic, taiko(0.9, 120, 40), T0, 1.0); put(epic, crash(2.0), T0, 0.45)
    put(epic, choir([C['C4'], C['Eb4'], C['G4'], C['C5']], 1.62 * K, attack=0.35 * K), I(T0 + 0.05), 0.55)
    put(epic, choir([C['Ab3'], C['C4'], C['Eb4'], C['Ab4']], 1.45 * K, attack=0.25 * K), I(3.92), 0.5)
    put(epic, strings_ost(C['C2'], 1.45 * K, step=0.125 * K), I(T0 + 0.05), 0.35)
    put(epic, strings_ost(C['Ab2'] / 2, 1.35 * K, step=0.125 * K), I(3.95), 0.38)
    taiko_t = list(np.arange(T0 + 0.5, 4.75, 0.25)) + list(np.arange(4.75, 5.3, 0.125))
    for k, t0 in enumerate(taiko_t):
        put(epic, taiko(0.45, 150 if k % 2 else 125, 52), I(t0), (0.75 if k % 2 == 0 else 0.5) * (1.0 if t0 < 4.75 else 0.8))
    put(epic, brass_hit([C['Ab2'], C['C3'], C['Eb3'], C['Ab3']], 0.4, 0.8), I(T0 + 0.5), 0.55)
    put(epic, brass_hit([C['Bb2'], C['D4'] / 2, C['F4'] / 2, C['Bb3']], 0.4, 0.9), I(T0 + 1.0), 0.6)
    put(epic, brass_hit([C['Ab2'], C['C3'], C['Eb3'], C['Ab3']], 0.35, 0.85), I(4.6), 0.5)
    put(epic, brass_hit([C['Bb2'], C['D4'] / 2, C['F4'] / 2, C['Bb3']], 0.35, 0.95), I(4.95), 0.55)
    put(epic, riser(0.85 * K), I(4.48), 0.3)
    put(vox, V.speak('rawr!', 'helper', contour=(1.0, 1.55, 2.0), seed=5), I(4.08), 1.6)
    put(dry, V.plop(rng, 0.07), I(5.22), 0.8)
    FIN = I(5.33)
    put(epic, taiko(0.8, 130, 42), FIN, 1.0); put(epic, taiko(0.8, 130, 42), FIN + 0.12, 0.8)
    put(epic, braam(1.4, 32.7), FIN, 0.75); put(epic, crash(2.4), FIN, 0.5)
    put(epic, brass_hit([C['Ab2'], C['C3'], C['Eb3']], 0.16, 0.9), FIN, 0.45)
    put(epic, brass_hit([C['Bb2'], C['D4'] / 2, C['F4'] / 2], 0.16, 0.95), FIN + 0.16, 0.5)
    put(epic, brass_hit([C['C3'], C['G3'], C['C4'], C['E4'], C['G4']], 1.2, 1.0) * env(int(1.2 * FS), 0.01, 0.9), FIN + 0.32, 0.65)
    put(epic, choir([C['C4'], C['E4'], C['G4'], C['C5']], 1.3, attack=0.12), FIN + 0.3, 0.5)
    # card 4.5-6.5: low and mysterious, the heartbeat a little quicker
    for t0 in (6.6, 7.6, 8.6):
        put(epic, taiko(0.7, 95, 38), Cd(t0), 0.45); put(epic, taiko(0.6, 95, 38), Cd(t0) + 0.22, 0.3)
    put(epic, choir([C['C4'], C['Eb4'], C['G4']], 3.4 * K, attack=1.0 * K), Cd(6.05), 0.16)
    n = int(3.6 * K * FS); t = np.arange(n) / FS
    put(dry, np.sin(2 * math.pi * (60 * np.exp(-t * 1.5 / K) + 28) * t) * np.exp(-t * 1.2 / K), Cd(6.2), 0.45)
    for k, t0 in enumerate((7.5, 7.72, 7.94)):
        b = tone(880 if k < 2 else 660, 0.12) * env(int(0.12 * FS), 0.01, 0.06)
        put(dry, V.inside_thimble(b * 3) * 0.6 + b * 0.15, Cd(t0), 0.35)


if LAYOUT != 'full':
    intro_x()


voices = {k: np.zeros_like(vox) for k in ('hero', 'skeptic', 'helper', 'helper2')}


def say(who, words, t, gain=1.0, thimble=False, **kw):
    sig = V.speak(words, 'helper' if who == 'helper2' else who, **kw) * gain
    if thimble:
        sig = V.inside_thimble(sig)
    put(voices[who], sig, A(t)); put(vox, sig, A(t))


# ---------------- sound effects
def clank(base=520.0, dur=0.9):
    n = int(dur * FS); t = np.arange(n) / FS
    x = sum(a * np.sin(2 * math.pi * base * r * t) * np.exp(-t * (3 + 2 * r)) for r, a in ((1, 1), (2.31, 0.6), (3.6, 0.4), (5.1, 0.25)))
    return x * np.minimum(1, t / 0.002) * 0.5


def scrape(dur):
    n = int(dur * FS)
    x = bp(rng.standard_normal(n), 300, 2400) * (0.6 + 0.4 * np.abs(np.sin(2 * math.pi * 23 * np.arange(n) / FS)))
    return x * env(n, 0.02, 0.08)


def ticks(dur, rate, f=(2500, 3400), length=0.02, jitter=0.01):
    out = np.zeros(int((dur + 0.1) * FS))
    for t0 in np.arange(0, dur, 1 / rate):
        c = tone(rng.uniform(*f), length) * np.hanning(int(length * FS))
        put(out, c, t0 + rng.uniform(0, jitter), rng.uniform(0.35, 0.6))
    return out


def tock():
    n = int(0.15 * FS); t = np.arange(n) / FS
    return np.sin(2 * math.pi * 820 * t) * np.exp(-t * 55) + lp(rng.standard_normal(n), 3000) * np.exp(-t * 90) * 0.4


def weld(dur):
    n = int(dur * FS)
    x = bp(rng.standard_normal(n), 2000, 8000) * (0.5 + 0.5 * np.abs(lp(rng.standard_normal(n), 30)) * 4)
    crack = np.zeros(n); idx = rng.integers(0, n - 200, int(dur * 70))
    for i in idx:
        crack[i:i + 120] += rng.uniform(-1, 1) * np.exp(-np.arange(120) / 25)
    t = np.arange(n) / FS
    buzz = lp(np.sign(np.sin(2 * math.pi * 185 * t * (1 + 0.01 * np.sin(2 * math.pi * 6 * t)))), 1500) * 0.15   # firefly
    return (x * 0.5 + crack * 0.6 + buzz) * env(n, 0.03, 0.1)


def crinkle(dur):
    out = np.zeros(int((dur + 0.1) * FS))
    for t0 in rng.uniform(0, dur, int(dur * 45)):
        m = int(rng.uniform(0.004, 0.015) * FS)
        put(out, hp(rng.standard_normal(m), 2500) * np.hanning(m), t0, rng.uniform(0.2, 0.6))
    return out


def boop_off():
    n = int(0.2 * FS); t = np.arange(n) / FS
    f = 880 * np.exp(-t * 6)
    return np.sin(2 * math.pi * np.cumsum(f) / FS) * env(n, 0.005, 0.08) * 0.5


def thunk():
    n = int(0.3 * FS); t = np.arange(n) / FS
    return np.sin(2 * math.pi * (60 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 14) + lp(rng.standard_normal(n), 2000) * np.exp(-t * 120) * 0.5


def roar(dur):
    n = int(dur * FS); t = np.arange(n) / FS
    x = lp(rng.standard_normal(n), 900) * 1.2 + bp(rng.standard_normal(n), 300, 2500) * 0.4
    flick = 0.7 + 0.3 * np.abs(lp(rng.standard_normal(n), 18)) * 3
    return x * flick * np.minimum(1, (t / dur) * 2.5) ** 1.5


def whistle(dur):
    n = int(dur * FS); t = np.arange(n) / FS
    f = 500 + 900 * (t / dur) + 140 * np.sin(2 * math.pi * 6.5 * t)      # the wobble with no nozzle
    return np.sin(2 * math.pi * np.cumsum(f) / FS) * env(n, 0.05, 0.02) * 0.35


def boom():
    n = int(2.4 * FS); t = np.arange(n) / FS
    low = np.sin(2 * math.pi * (30 + 60 * np.exp(-t * 4)) * t) * np.exp(-t * 1.6)
    body = lp(rng.standard_normal(n), 400) * np.exp(-t * 2.2) * 1.4
    return np.tanh((low + body) * 1.8) + crash(2.4) * 0.8


# ---------------- story music: one bed, crossfaded from the intro, builds to the launch
def S(t):
    return A(t)


bed = [  # story time from, to, chord, filter, gain
    (5.0, 5.6, [C['Eb2'] * 2, C['G3'], C['Bb3']], 900, 0.2),
    (5.45, 7.45, [C['C3'], C['Eb3'], C['G3']], 1200, 0.24),
    (7.3, 9.0, [C['Ab2'], C['C3'], C['Eb3']], 1300, 0.26),
    (8.85, 10.5, [C['Eb2'] * 2, C['G3'], C['Bb3']], 1400, 0.28),
    (10.35, 11.85, [C['Bb2'], C['D4'] / 2, C['F4'] / 2], 1500, 0.3),
    (11.7, 13.1, [C['C3'], C['Eb3'], C['G3'], C['C4']], 1700, 0.32),
    (13.0, 15.6, [C['Ab2'], C['Eb3'], C['Bb3']], 600, 0.16),          # extra cap: suspended, quiet
    (15.45, 17.6, [C['C3'], C['G3'], C['C4']], 800, 0.2),             # countdown
    (17.5, 19.35, [C['C3'], C['Eb3'], C['G3'], C['C4']], 2000, 0.32),  # launch
]
for t0, t1, fr, fc, gn in bed:
    put(epic, pad(fr, t1 - t0, fc), S(t0), gn)
n = int((19.35 - 2.5) * FS)
put(epic, 0.35 * np.sin(2 * math.pi * C['C1'] * np.arange(n) / FS) * env(n, 1.0, 0.05), S(2.5), 0.22)

# blueprint 2.5-5.5: the warm plucked theme of the series
motif = [C['Eb4'], C['G4'], C['Bb4'], C['G4'], C['Ab4'], C['C5'], C['Eb5'], C['C5'], C['Bb4'], C['G4'], C['Ab4'], C['Bb4']]
for k, f in enumerate(motif):
    put(epic, pluck(f, 0.5), S(2.55) + k * 0.25, 0.28 if k % 4 == 0 else 0.2)
# build 5.5-13.0: taiko pulse speeds up, strings ostinato, a brass hit on every cut
t = 5.5
while t < 13.0:
    k = int((t - 5.5) * 4)
    put(epic, taiko(0.45, 140 if k % 2 else 118, 50), S(t), 0.45 + 0.35 * (t - 5.5) / 7.5)
    t += 0.5 - 0.25 * (t - 5.5) / 7.5
for (t0, t1), note in zip(((5.5, 7.35), (7.33, 8.95), (8.92, 10.45), (10.42, 11.78), (11.75, 13.0)),
                          (C['C2'], C['Ab2'] / 2, C['Eb2'], C['Bb1'], C['C2'])):
    put(epic, strings_ost(note, t1 - t0, step=0.125 if t0 < 10 else 0.0833), S(t0), 0.22 + 0.04 * (t0 - 5.5))
for k, t0 in enumerate((5.5, 7.33, 8.92, 10.42, 11.75)):
    chords = [[C['C3'], C['Eb3'], C['G3']], [C['Ab2'], C['C3'], C['Eb3']], [C['Eb3'], C['G3'], C['Bb3']],
              [C['Bb2'], C['D4'] / 2, C['F4'] / 2], [C['C3'], C['Eb3'], C['G3'], C['C4']]]
    put(epic, brass_hit(chords[k], 0.35, 0.8), S(t0), 0.4 + 0.05 * k)
put(epic, choir([C['C4'], C['Eb4'], C['G4']], 1.4, attack=0.6), S(11.7), 0.3)
put(epic, brass_hit([C['C3'], C['G3'], C['C4'], C['E4']], 0.9, 1.0) * env(int(0.9 * FS), 0.01, 0.6), S(13.0), 0.5)  # rocket stands
# extra cap 13.0-15.5: quiet, a slow heartbeat
for t0 in (13.6, 14.3, 15.0):
    put(epic, taiko(0.5, 90, 36), S(t0), 0.3)
# countdown 15.5-17.5: snare roll that speeds up, riser
t = 15.5
while t < EV['button']:
    s = bp(rng.standard_normal(int(0.06 * FS)), 1500, 6000) * np.hanning(int(0.06 * FS))
    put(epic, s, S(t), 0.12 + 0.3 * (t - 15.5) / 1.6)
    t += 0.16 - 0.1 * (t - 15.5) / 1.6
put(epic, riser(1.0), S(EV['button']) - 0.9, 0.3)
# launch 17.5-19.3: big and rising to the explosion
put(epic, braam(1.7), S(EV['ignite']), 0.75)
put(epic, choir([C['C4'], C['Eb4'], C['G4'], C['C5']], 1.75, attack=0.5), S(EV['ignite']), 0.5)
for k, t0 in enumerate(np.arange(EV['ignite'], EV['boom'], 0.125)):
    put(epic, taiko(0.4, 150 if k % 2 else 125, 52), S(t0), 0.45 + 0.4 * (t0 - EV['ignite']) / 1.7)
put(epic, brass_hit([C['Ab2'], C['C3'], C['Eb3'], C['Ab3']], 0.4, 0.9), S(EV['liftoff']), 0.55)
put(epic, riser(1.0), S(EV['boom']) - 1.0, 0.35)

# ---------------- sound effects and voices on the story
for t0 in np.arange(2.5, 3.25, 0.09):                                    # charcoal scratch
    put(dry, bp(rng.standard_normal(int(0.07 * FS)), 1200, 5000) * np.hanning(int(0.07 * FS)), S(t0) + rng.uniform(0, 0.02), 0.25)
put(dry, crinkle(0.35), S(3.3), 0.25)                                    # paper turned
put(dry, ticks(0.8, 3.0, (1500, 2000), 0.03, 0.0), S(3.75), 0.35)        # head taps on the blueprint
say('hero', 'bli-pa-ta shi-mo blo-ro-pa! blorp!', EV['hero_pitch'], 1.05, seed=11)
say('skeptic', 'hm-mm.', EV['skeptic_hm'], 1.0, contour=(1.0, 0.92, 0.8), seed=12)
for j, who in ((EV['jerk1'], 'helper'), (EV['jerk2'], 'helper2')):        # the can: wind-up, jerk
    put(dry, V.plop(rng, 0.06), S(j - 0.25), 0.6)
    put(dry, scrape(0.35), S(j), 0.5); put(dry, clank(470, 0.8), S(j) + 0.02, 0.45)
    say(who, 'hop!', j - 0.05, 1.1, seed=14 if who == 'helper' else 15)
put(dry, ticks(1.5, 16), S(7.35), 0.4)                                   # caps rolling
say('helper', 'pla-pi!', EV['plapi'], 1.0, seed=16)
for t0 in np.arange(7.4, 8.9, 0.3):
    put(dry, V.plop(rng, 0.05), S(t0), 0.35)                              # wet crawl
put(dry, scrape(0.25) * 0.5, S(9.3), 0.4); put(dry, tock(), S(EV['match_tock']), 0.7)
say('hero', 'hu-up!', EV['match_tock'] - 0.2, 0.9, seed=23)
put(dry, weld(1.3), S(EV['weld']), 0.45)
put(dry, crinkle(1.2), S(EV['foil']), 0.45)
say('hero', 'e-e?', EV['uh'], 1.0, contour=(1.0, 0.9, 1.1), seed=17)
say('hero', 'pfu.', EV['flick'], 1.0, contour=(1.1, 1.0, 0.78), seed=18)
put(dry, V.plop(rng, 0.07), S(EV['flick']), 0.7); put(dry, scrape(0.45) * 0.7, S(EV['flick']) + 0.05, 0.45)
say('hero', 'blu.', EV['blu'], 1.0, contour=(1.0, 1.0, 0.9), seed=19)
say('hero', 'mo.', EV['mo'], 1.0, contour=(1.08, 1.08, 0.98), seed=20)
say('hero', 'shli-ip!', EV['shlip'], 1.1, seed=21)
for t0 in (EV['blu'], EV['mo'], EV['button']):
    put(dry, boop_off(), S(t0) + 0.05, 0.5)
put(dry, thunk(), S(EV['button']), 0.8)
put(dry, roar(EV['boom'] - EV['ignite']), S(EV['ignite']), 0.55)
put(dry, whistle(EV['boom'] - EV['liftoff']), S(EV['liftoff']), 0.6)
put(dry, boom(), S(EV['boom']), 1.0)
for t0 in rng.uniform(EV['boom'] + 0.3, EV['silence'] - 0.05, 40):         # soil and junk raining down
    put(dry, ticks(0.03, 40, (900, 2600), 0.015), S(t0), rng.uniform(0.3, 0.8))
say('hero', 'mu-u-u.', EV['moo'], 0.75, thimble=True, contour=(0.95, 0.85, 0.65), seed=22)

# ---------------- variant B only: after the explosion the score keeps going, low and sad
sad = np.zeros_like(epic)
put(sad, pad([C['C2'], C['G2'], C['Eb3']], TOTAL - A(EV['boom']) - 0.3, 500), S(EV['boom']) + 0.3, 0.18)
for k, f in enumerate([C['G4'], C['Eb4'], C['C4'], C['Bb3'], C['C4']]):
    put(sad, pluck(f, 0.9), S(21.5) + k * 0.9, 0.12)


# ---------------- mix
def hall_rev(x, rt=2.4, seed=3):
    from scipy.signal import fftconvolve
    r = np.random.default_rng(seed); n = int(rt * FS)
    ir = r.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n); ir = lp(ir, 5000); ir[:int(0.012 * FS)] *= 0.2
    ir /= np.sqrt((ir ** 2).sum())
    return fftconvolve(x, ir)[:len(x)]


def ducker(v):
    e = np.convolve(np.abs(v), np.ones(int(0.03 * FS)) / int(0.03 * FS), 'same')
    sm = np.zeros_like(e); a_up, a_dn = 1 - math.exp(-1 / (0.02 * FS)), 1 - math.exp(-1 / (0.3 * FS)); cur = 0.0
    for i, x in enumerate(e):
        cur += (x - cur) * (a_up if x > cur else a_dn); sm[i] = cur
    lead = int(0.06 * FS); sm = np.concatenate([sm[lead:], np.zeros(lead)])
    return 1 - 0.68 * np.clip(sm / (np.percentile(sm[sm > 1e-4], 90) + 1e-9), 0, 1)


def cut(x, t, fade=0.012):
    y = x.copy(); i = int(t * FS); m = int(fade * FS)
    y[i:i + m] *= np.linspace(1, 0, m); y[i + m:] = 0
    return y


duck = ducker(vox)
N = int(TOTAL * FS)
fx = cut(V.room(dry, rt=0.25, wet=0.12), A(EV['silence']))                # explosion debris, then nothing
vo = V.room(vox, rt=0.25, wet=0.12)
for name, score in (('A', cut(epic, A(EV['boom']) + 0.04)), ('B', epic + sad)):
    music = score * 0.75 + hall_rev(score) * 0.5
    if name == 'A':
        music = cut(music, A(EV['boom']) + 0.04)                          # hall tail cut too: real silence
    out = (fx + vo + music * duck)[:N]
    out = out / (np.abs(out).max() + 1e-9) * 0.9
    os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    wavfile.write(os.path.join(HERE, 'out', f'ep1_draft_{name}{SUFFIX}.wav'), FS, (out * 32767).astype(np.int16))
    print('audio', name, round(len(out) / FS, 2))

# ---------------- head pulse: voice loudness per animatic frame (full layout only: same story frames)
if LAYOUT != 'full':
    sys.exit(0)
envs = {'fps': TM.FPS, 'story0': TM.STORY0}
for k, buf in voices.items():
    vals = []
    for f in range(1, TM.NFRAMES + 1):
        t = A(TM.t_of(f)); seg = buf[max(0, int((t - 0.5 / TM.FPS) * FS)):int((t + 0.5 / TM.FPS) * FS)]
        vals.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    m = max(vals) or 1.0
    envs[k] = [round(min(1.0, v / m * 1.6), 3) for v in vals]
json.dump(envs, open(os.path.join(HERE, 'out', 'ep1_voices_env.json'), 'w'))
print('env frames', TM.NFRAMES, {k: sum(1 for v in envs[k] if v > 0.2) for k in voices})
