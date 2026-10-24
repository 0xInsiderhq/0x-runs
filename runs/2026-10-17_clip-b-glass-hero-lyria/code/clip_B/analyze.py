"""clip_B audio analysis: beat grid, vocal activity/onsets, bass dropouts, vocal-band envelope per video frame.
usage: python3 analyze.py   (reads ../song/song_B.mp3 and audio/vocals.wav, audio/no_vocals.wav; prints a report, writes audio/analysis_raw.json)"""
import os, json, numpy as np, librosa
from scipy import signal
C = os.path.dirname(os.path.abspath(__file__)); SR = 22050; FPS = 24
mix, _ = librosa.load(f"{C}/../song/song_B.mp3", sr=SR, mono=True)
voc, _ = librosa.load(f"{C}/audio/vocals.wav", sr=SR, mono=True)
inst, _ = librosa.load(f"{C}/audio/no_vocals.wav", sr=SR, mono=True)
def rms_db(x, win=0.05, hop=0.01):
    w, h = int(win * SR), int(hop * SR); r = librosa.feature.rms(y=x, frame_length=w, hop_length=h, center=True)[0]
    return np.arange(len(r)) * hop, 20 * np.log10(r + 1e-9)
t, mdb = rms_db(mix); end = float(t[np.where(mdb > -50)[0][-1]])
# beat grid from the instrumental stem
tempo, bt = librosa.beat.beat_track(y=inst, sr=SR, start_bpm=108, units="time", tightness=200)
d = np.diff(bt); T = float(np.median(d[(d > 0.45) & (d < 0.7)]))
k = np.round((bt - 2.44) / T); A = np.vstack([np.ones_like(k), k]).T; t0, T = np.linalg.lstsq(A, bt, rcond=None)[0]
# vocal activity (stem), band 300-3000 Hz
sos = signal.butter(4, [300, 3000], "bandpass", fs=SR, output="sos"); vb = signal.sosfiltfilt(sos, voc)
tv, vdb = rms_db(vb); vmax = np.percentile(vdb, 99); act = vdb > vmax - 24
segs, on = [], None
for i, a in enumerate(act):
    if a and on is None: on = tv[i]
    if not a and on is not None:
        if tv[i] - on > 0.12: segs.append((round(float(on), 2), round(float(tv[i]), 2)))
        on = None
merged = []
for s in segs:
    if merged and s[0] - merged[-1][1] < 0.18: merged[-1] = (merged[-1][0], s[1])
    else: merged.append(s)
on_env = librosa.onset.onset_strength(y=vb, sr=SR, hop_length=256); on_t = librosa.onset.onset_detect(onset_envelope=on_env, sr=SR, hop_length=256, units="time", backtrack=True)
# bass (instrumental < 150 Hz)
sl = signal.butter(4, 150, "lowpass", fs=SR, output="sos"); tb, bdb = rms_db(signal.sosfiltfilt(sl, inst), 0.1, 0.05)
# per-frame vocal envelope (0..1) for the glow
nfr = int(round(end * FPS)); fe = np.zeros(nfr)
for f in range(nfr):
    m = (tv >= f / FPS - 0.02) & (tv < (f + 1) / FPS + 0.02); fe[f] = vdb[m].mean() if m.any() else -90
e = np.clip((fe - (vmax - 36)) / 36, 0, 1); att, rel = 1 - np.exp(-1 / (FPS * 0.03)), 1 - np.exp(-1 / (FPS * 0.18)); s, out = 0.0, []
for x in e: s += (x - s) * (att if x > s else rel); out.append(round(float(s), 3))
raw = dict(sound_end=end, beat_t0=float(t0), beat_T=float(T), bpm=60 / float(T), librosa_beats=[round(float(x), 3) for x in bt],
           vocal_segments=merged, vocal_onsets=[round(float(x), 2) for x in on_t], vocal_env=out,
           bass=dict(t=[round(float(x), 2) for x in tb], db=[round(float(x), 1) for x in bdb]))
json.dump(raw, open(f"{C}/audio/analysis_raw.json", "w"))
print(f"sound ends at {end:.2f} s; tempo {60 / T:.2f} BPM, beat {T:.4f} s, grid t0 {t0:.3f} s; librosa beats {len(bt)}, first {bt[:4]}")
res = bt - (t0 + np.round((bt - t0) / T) * T); print(f"grid residual: median |{np.median(np.abs(res)) * 1000:.0f} ms|, max {np.abs(res).max() * 1000:.0f} ms")
print("vocal segments:", merged)
print("vocal onsets:", [round(float(x), 2) for x in on_t])
bd = np.convolve(bdb, np.ones(5) / 5, "same"); ref = np.median(bd[(tb > 8) & (tb < 56)])
drops = []; on = None
for i in range(len(tb)):
    low = bd[i] < ref - 12 and 4 < tb[i] < 60
    if low and on is None: on = tb[i]
    if not low and on is not None:
        if tb[i] - on > 0.25: drops.append((round(float(on), 2), round(float(tb[i]), 2)))
        on = None
print("bass dropouts (>12 dB below median):", drops)
