"""Procedural sound design synced to traj.py.  python3 audio.py out.wav"""
import sys, os
import numpy as np
from scipy import signal
from scipy.io import wavfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traj as T

SR = 48000; DUR = T.FRAMES / T.FPS; N = int(SR * DUR); t = np.arange(N) / SR
rng = np.random.default_rng(11)
S, ev, FR, CAMS = T.build_all()
ts = np.array([s["t"] for s in S])
def ctl(vals): return np.interp(t, ts, np.asarray(vals, dtype=float))
speed = ctl([s["speed"] for s in S])
cg = np.stack([ctl([s["cg"][i] for s in S]) for i in range(3)], 1)
phase = np.array([s["phase"] for s in S]); ph = lambda name: ctl((phase == name).astype(float))
on_ground, on_loop, in_flight, sliding, idle = ph("run"), ph("loop"), ph("flight"), ph("slide"), ph("idle")
jet_tot = ctl([sum(s["jets"].values()) for s in S])

# active camera position / right vector per audio sample
tf = np.array([c["t"] for c in CAMS]); cut_t = ev["t_cut"]
def qrot(q, v):
    w, x, y, z = q; u = np.array([x, y, z]); return v + 2 * np.cross(u, np.cross(u, v) + w * v)
cp, cr = [], []
for c in CAMS:
    d = c["A"] if c["t"] < cut_t else c["B"]
    cp.append(d["loc"]); cr.append(qrot(d["quat"], np.array([1.0, 0, 0])))
cp, cr = np.array(cp), np.array(cr)
cam_pos = np.stack([np.interp(t, tf, cp[:, i]) for i in range(3)], 1)
cam_right = np.stack([np.interp(t, tf, cr[:, i]) for i in range(3)], 1)
rel = cg - cam_pos; dist = np.linalg.norm(rel, axis=1) + 1e-3
pan = np.clip(np.sum(rel * cam_right, 1) / dist * 1.6, -1, 1)
dop = np.clip(1.0 / (1.0 + signal.savgol_filter(np.gradient(dist, 1 / SR), 4801, 2) / 343.0), 0.9, 1.1)

def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)
def lp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "lowpass", fs=SR, output="sos"), x)
def hp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "highpass", fs=SR, output="sos"), x)
def unit(x): return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)
def osc(freq): return np.sin(2 * np.pi * np.cumsum(freq) / SR)
def env_at(t0, att, dec):
    e = np.zeros(N); m = t >= t0; x = t[m] - t0
    e[m] = np.minimum(1, x / max(att, 1e-4)) * np.exp(-x / dec); return e
def white(): return rng.standard_normal(N)
def brown(): return unit(hp(np.cumsum(white()), 20, 2))
def band(lo, hi, order=2): return unit(bp(white(), lo, hi, order))

# ---------------- car-borne sources (spatialised) ----------------
acc = np.gradient(speed, 1 / SR)
throttle = np.clip(acc / T.ACC, 0, 1) * on_ground + 0.45 * on_loop
f_motor = (130 + 34 * speed) * dop
whine = 0.35 * osc(f_motor) + 0.12 * osc(2.6 * f_motor) + 0.05 * osc(4.2 * f_motor + 9 * np.sin(2 * np.pi * 3 * t))
motor = whine * (0.08 + 0.5 * throttle) * np.clip(speed / 3 + idle * 0.25, 0, 1) * (1 - 0.7 * sliding)
fl_motor = 0.16 * osc((900 + 300 * np.exp(-np.maximum(t - ev["t_top"], 0) / 0.6)) * dop) * in_flight
road = band(180, 1400) * (speed / 22) ** 1.5 * (on_ground + 0.2 * sliding) * 0.30
deck = (band(110, 170, 3) * 0.25 + band(290, 360, 3) * 0.18) * on_loop * (speed / 22)
seams = np.zeros(N); pos_s = np.cumsum(speed * on_loop) / SR
for h in np.where(np.diff(np.floor(pos_s / 2.2)) > 0)[0]: seams += 0.35 * env_at(t[h], 0.001, 0.035) * np.sin(2 * np.pi * 230 * t)
wind = unit(hp(white(), 900)) * (speed / 22) ** 2 * 0.10
detach = 0.8 * env_at(ev["t_top"], 0.002, 0.18) * np.sin(2 * np.pi * 75 * t) + 0.25 * env_at(ev["t_top"], 0.001, 0.4) * band(400, 2500)
jets = unit(hp(lp(white(), 9000), 1800)) * jet_tot * 0.30 + band(300, 2000) * jet_tot * 0.12
for (p0, dur, names, F) in ev["pulses"]:
    jets += 0.5 * env_at(p0, 0.001, 0.03) * (0.5 * white() + np.sin(2 * np.pi * 95 * t))
tl = ev["t_land"]
land = (0.7 * env_at(tl, 0.003, 0.45) * np.sin(2 * np.pi * np.cumsum(35 + 40 * np.exp(-np.maximum(t - tl, 0) / 0.08)) / SR)
        + 0.40 * env_at(tl, 0.001, 0.22) * unit(lp(white(), 2500))
        + 0.30 * env_at(tl + 0.06, 0.002, 0.12) * np.sin(2 * np.pi * 180 * t) * np.sin(2 * np.pi * 7 * t)
        + 0.15 * env_at(tl + 0.02, 0.01, 0.6) * band(1500, 6000))
slip = sliding * np.clip(speed / 14, 0, 1)
sq_f = 900 + np.clip(np.cumsum(rng.standard_normal(N)) / np.sqrt(SR) * 120, -150, 150)
squeal = (band(700, 1600, 3) * 0.25 + 0.20 * osc(sq_f) + 0.08 * osc(1.93 * sq_f)) * slip
scrape = band(120, 700) * slip * 0.25
ts_ = ev["t_stop"]
settle = 0.12 * env_at(ts_, 0.01, 0.25) * band(80, 400)
ticks = np.zeros(N)
for k in range(14):
    tt = ts_ + 0.6 + rng.uniform(0, DUR - ts_ - 0.8)
    ticks += 0.05 * env_at(tt, 0.0005, 0.012) * np.sin(2 * np.pi * rng.uniform(2500, 4200) * t)
wind_down = 0.10 * osc(1400 * np.exp(-np.maximum(t - tl, 0) / 1.2) + 200) * env_at(tl, 0.05, 1.6)
car_mono = motor + fl_motor + road + deck + seams + wind + detach + jets + land + squeal + scrape + settle + ticks + wind_down

# ---------------- spatialise: distance gain, air absorption, pan ----------------
gain = (1.0 + dist / 12.0) ** -0.8
out_c = np.zeros(N); blk = 480; zi = None
for i in range(0, N, blk):
    fc = float(np.clip(16000 / (1 + dist[i] / 30), 1500, 16000))
    sos = signal.butter(1, fc, "lowpass", fs=SR, output="sos")
    if zi is None: zi = signal.sosfilt_zi(sos) * car_mono[0]
    out_c[i:i + blk], zi = signal.sosfilt(sos, car_mono[i:i + blk], zi=zi)
out_c *= gain
L = out_c * np.cos((pan + 1) * np.pi / 4); R = out_c * np.sin((pan + 1) * np.pi / 4)

# ---------------- ambience + cinematic layer ----------------
gust = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + 1.0)
ambL = 0.025 * unit(lp(brown(), 300)) + 0.006 * np.sin(2 * np.pi * 47 * t) + 0.008 * band(600, 3000) * gust
ambR = 0.025 * unit(lp(brown(), 300)) + 0.006 * np.sin(2 * np.pi * 47 * t) + 0.008 * band(600, 3000) * (1 - 0.5 * gust)
riser_env = np.clip((t - 4.2) / (ev["t_top"] - 4.2), 0, 1) ** 2 * (t < ev["t_top"])
riser = (0.10 * osc(38 + 22 * riser_env) + 0.03 * band(300, 3000)) * riser_env
boom = 0.35 * env_at(tl, 0.004, 1.1) * np.sin(2 * np.pi * np.cumsum(28 + 30 * np.exp(-np.maximum(t - tl, 0) / 0.2)) / SR)
hush = 1 - 0.6 * (np.clip((t - ev["t_top"]) / 0.05, 0, 1) * np.clip((tl - 0.3 - t) / 0.3, 0, 1))
L = L * hush + ambL + riser + boom; R = R * hush + ambR + riser + boom
fade = np.clip(t / 0.4, 0, 1) * np.clip((DUR - t) / 0.6, 0, 1)
st = np.stack([L, R], 1) * fade[:, None]
st = np.tanh(st / (np.max(np.abs(st)) + 1e-9) * 2.0); st *= 0.89 / np.max(np.abs(st))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(T.__file__)), "stunt_audio.wav")
wavfile.write(out, SR, st.astype(np.float32))
print("AUDIO_DONE", out, f"{DUR:.2f}s", "peak", float(np.max(np.abs(st))))
