"""v2.2 sound design on the OUTPUT timeline (speed ramp + slow-mo). Music-free SFX.
Writes sfx.wav (48 kHz stereo, 24-bit, -16 LUFS, true peak <= -1.5 dBTP) and events.txt."""
import sys, os, math
import numpy as np
from scipy import signal
import soundfile as sf, pyloudnorm as pyln
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import traj as T

SR = 48000; DUR = T.FRAMES / T.FPS; N = int(round(SR * DUR)); tau = np.arange(N) / SR
rng = np.random.default_rng(21)
S, ev, FR, C = T.build_all()
t = np.interp(tau, np.array(ev["_tau"]), np.array(ev["_ts"]))           # story time of every output sample
spd = np.interp(tau, tau[::48], np.array([T.speed_at(x, ev) for x in t[::48]]))
pitch = np.minimum(spd, 1.0) ** 0.55                                       # slow-mo: lower and longer
dts = spd / SR                                                             # story seconds per output sample
Ts = np.array([s["t"] for s in S])
def ctl(vals): return np.interp(t, Ts, np.asarray(vals, dtype=float))
OT = lambda x: T.out_time(ev, x)                                           # story -> output seconds
speed = ctl([s["speed"] for s in S])
phase = np.array([s["phase"] for s in S]); ph = lambda name: ctl((phase == name).astype(float))
on_ground, on_loop, in_flight, sliding, idle = ph("run"), ph("loop"), ph("flight"), ph("slide"), ph("idle")
jet_tot = ctl([sum(T.vjet(ev, n, s["t"]) for n in T.JETS) for s in S])

# ---- car position in the active camera (pan by screen x, distance) ----
xs, ds = [], []
for c in C:
    cam = c["A"] if c["frame"] < ev["cut_frame"] else c["B"]; cg = FR[c["frame"] - 1]["cg"]
    Rm = T.quat_mat(cam["quat"]); d = np.array(cg) - np.array(cam["loc"])
    cx = sum(Rm[i][0] * d[i] for i in range(3)); cz = sum(Rm[i][2] * d[i] for i in range(3))
    xs.append(np.clip(cam["lens"] * cx / max(1e-3, -cz) / (18.0 * 1080 / 1350), -1.5, 1.5)); ds.append(np.linalg.norm(d))
sides = []
for c in C:
    cam = c["A"] if c["frame"] < ev["cut_frame"] else c["B"]; Xc = FR[c["frame"] - 1]["X"]; Rm = T.quat_mat(cam["quat"])
    sides.append(sum(Rm[i][0] * Xc[i] for i in range(3)))            # +1: car's right side is screen-right
tf = (np.arange(T.FRAMES) + 0.5) / T.FPS
pan = np.clip(np.interp(tau, tf, signal.savgol_filter(np.array(xs), 9, 2)), -1, 1) * 0.85
dist = np.interp(tau, tf, np.array(ds))
vrad = signal.savgol_filter(np.gradient(dist, 1 / SR) / np.maximum(spd, 1e-3), 4801, 2)        # story-time radial speed
t_cut_o = T.out_time(ev, ev["t_cut"]); exag = np.where(tau < t_cut_o, 2.6, 1.0)
dop = np.clip(1.0 / (1.0 + exag * vrad / 343.0), 0.88, 1.12)

def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)
def lp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "lowpass", fs=SR, output="sos"), x)
def hp(x, fc, order=2): return signal.sosfilt(signal.butter(order, fc, "highpass", fs=SR, output="sos"), x)
def unit(x): return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)
def osc(freq): return np.sin(2 * np.pi * np.cumsum(freq) / SR)
def env_at(t0, att, dec):
    e = np.zeros(N); m = tau >= t0; x = tau[m] - t0
    e[m] = np.minimum(1, x / max(att, 1e-4)) * np.exp(-x / dec); return e
def white(): return rng.standard_normal(N)
def band(lo, hi, order=2): return unit(bp(white(), lo, hi, order))
def tv_band(x, lo, hi, order=2, blk=480):
    """band-pass whose cutoffs follow arrays lo/hi (time-varying, state kept across blocks)"""
    out = np.zeros_like(x); zi = None
    for i in range(0, len(x), blk):
        l = float(np.clip(lo[i], 20, SR / 2.4)); h = float(np.clip(hi[i], l * 1.3, SR / 2.1))
        sos = signal.butter(order, [l, h], "bandpass", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        out[i:i + blk], zi = signal.sosfilt(sos, x[i:i + blk], zi=zi)
    return out

# ---------------- car-borne sources ----------------
acc = np.gradient(speed, 1 / SR) / np.maximum(spd, 1e-3)                  # story-time acceleration
throttle = np.clip(acc / T.ACC, 0, 1) * on_ground + 0.45 * on_loop
f_motor = (130 + 34 * speed) * dop * pitch
whine = 0.35 * osc(f_motor) + 0.12 * osc(2.6 * f_motor) + 0.05 * osc(4.2 * f_motor + 9 * np.sin(2 * np.pi * 3 * t))
motor = whine * (0.08 + 0.5 * throttle) * np.clip(speed / 3 + idle * 0.25, 0, 1) * (1 - 0.7 * sliding)
fl_motor = 0.16 * osc((900 + 300 * np.exp(-np.maximum(t - ev["t_top"], 0) / 0.6)) * dop * pitch) * in_flight
def pair(fn):                                                        # independent L/R realisations -> diffuse, decorrelated
    return np.stack([fn(), fn()])
road = pair(lambda: band(180, 1400)) * (speed / 22) ** 1.5 * (on_ground + 0.2 * sliding) * 0.30
deck = pair(lambda: band(110, 170, 3) * 0.25 + band(290, 360, 3) * 0.18) * on_loop * (speed / 22)
seams = np.zeros(N); pos_s = np.cumsum(speed * on_loop * dts)
for h in np.where(np.diff(np.floor(pos_s / 2.2)) > 0)[0]: seams += 0.35 * env_at(tau[h], 0.001, 0.035) * np.sin(2 * np.pi * 230 * tau)
wind = pair(lambda: unit(tv_band(white(), 900 * pitch, 9000 * pitch))) * (speed / 22) ** 2 * 0.10
wind_slow = pair(lambda: unit(tv_band(white(), 90 * pitch + 30, 600 * pitch + 80))) * np.clip(1 - pitch, 0, 1) * (speed / 22) * 0.22   # stretched, low rush
tt = OT(ev["t_top"])
detach = 0.8 * env_at(tt, 0.002, 0.30) * np.sin(2 * np.pi * 52 * tau) + 0.25 * env_at(tt, 0.001, 0.6) * band(300, 1800)
jL = ctl([sum(T.vjet(ev, n, s_["t"]) for n in T.JETS if n[0] == "L") for s_ in S]); jR = jet_tot - jL
def jet_noise(): return unit(tv_band(white(), 1600 * pitch, 9000 * pitch)) * 0.32 + unit(tv_band(white(), 250 * pitch, 1800 * pitch)) * 0.14
jets_side = np.stack([jet_noise() * jL, jet_noise() * jR])          # car-left / car-right nozzles
jets = np.zeros(N)
pulse_on = []
for (t0, dur, names, label) in ev["vpulses"]:
    to = OT(t0); pulse_on.append((to, label, names, dur))
    if "exhale" in label:
        jets += 0.30 * env_at(to, 0.012, 0.30) * band(1800, 9000) + 0.12 * env_at(to, 0.004, 0.08) * np.sin(2 * np.pi * 70 * tau)
        continue
    jets += 0.55 * env_at(to, 0.001, 0.035 / max(0.35, T.speed_at(t0, ev))) * (0.5 * white() + np.sin(2 * np.pi * 95 * np.minimum(spd, 1) ** 0.55 * tau))
tl = OT(ev["t_land"])
t_rt0, t_rt1 = OT(ev["t_top"] + T.SM[2]), OT(ev["t_top"] + T.SM[3])
whoosh = 0.5 * np.clip((tau - t_rt0) / (t_rt1 - t_rt0), 0, 1) ** 2.5 * (tau < t_rt1) * band(400, 5000) + 0.25 * env_at(t_rt1, 0.002, 0.18) * band(200, 2500)   # time snaps back
land = (0.9 * env_at(tl, 0.002, 0.45) * np.sin(2 * np.pi * np.cumsum(32 + 45 * np.exp(-np.maximum(tau - tl, 0) / 0.07)) / SR)
        + 0.55 * env_at(tl, 0.0007, 0.20) * unit(lp(white(), 3500))
        + 0.30 * env_at(tl + 0.05, 0.002, 0.12) * np.sin(2 * np.pi * 180 * tau) * np.sin(2 * np.pi * 7 * tau)
        + 0.15 * env_at(tl + 0.02, 0.01, 0.6) * band(1500, 6000))
slip = sliding * np.clip(speed / 14, 0, 1)
sq_f = 900 + np.clip(np.cumsum(rng.standard_normal(N)) / np.sqrt(SR) * 120, -150, 150)
squeal = (0.20 * osc(sq_f) + 0.08 * osc(1.93 * sq_f)) * slip
squeal_n = pair(lambda: band(700, 1600, 3)) * 0.25 * slip
scrape = pair(lambda: band(120, 700)) * slip * 0.25
tsp = OT(ev["t_stop"])
settle = 0.12 * env_at(tsp, 0.01, 0.25) * band(80, 400)
ticks = np.zeros(N)
for k in range(10):
    ticks += 0.05 * env_at(tsp + 0.4 + rng.uniform(0, DUR - tsp - 0.6), 0.0005, 0.012) * np.sin(2 * np.pi * rng.uniform(2500, 4200) * tau)
wind_down = 0.10 * osc(1400 * np.exp(-np.maximum(tau - tl, 0) / 1.2) + 200) * env_at(tl, 0.05, 1.6)
tla, tpa = OT(ev["t_launch"]), OT(ev["t_pass"])
chirp = 0.22 * env_at(tla, 0.004, 0.32) * (osc(1800 + 500 * np.exp(-np.maximum(tau - tla, 0) / 0.2)) * 0.5 + band(1200, 4200))
passby = 0.75 * np.exp(-((tau - tpa) / 0.13) ** 2) * band(250, 7000) + 0.45 * np.exp(-((tau - tpa - 0.05) / 0.09) ** 2) * band(60, 400)
car = motor + fl_motor + seams + detach + jets + land + squeal + settle + ticks + wind_down + chirp + passby                    # point-like, panned
diffuse = road + deck + wind + wind_slow + squeal_n + scrape                                                 # decorrelated L/R

# ---------------- spatialise by the car's place in the frame ----------------
gain = (1.0 + dist / 12.0) ** -0.8 * (1.0 + 1.2 * np.exp(-dist / 3.0))     # v2.2: the close pass-by is loud
out_c = np.zeros(N); blk = 480; zi = None
for i in range(0, N, blk):
    sos = signal.butter(1, float(np.clip(16000 / (1 + dist[i] / 30), 1500, 16000)), "lowpass", fs=SR, output="sos")
    if zi is None: zi = signal.sosfilt_zi(sos) * car[0]
    out_c[i:i + blk], zi = signal.sosfilt(sos, car[i:i + blk], zi=zi)
out_c *= gain
side = np.interp(tau, tf, np.array(sides))
def panned(x, p): return x * np.cos((np.clip(p, -1, 1) + 1) * np.pi / 4), x * np.sin((np.clip(p, -1, 1) + 1) * np.pi / 4)
L, R = panned(out_c, pan)
for k, sgn in ((0, -1.0), (1, 1.0)):                                  # nozzles: left group / right group of the car
    l, r_ = panned(jets_side[k] * gain, pan + 0.6 * sgn * side); L += l; R += r_
w = 0.75                                                              # diffuse bed: wide but still following the car
dL = diffuse[0] * gain; dR = diffuse[1] * gain
pl, pr = np.cos((pan * 0.6 + 1) * np.pi / 4), np.sin((pan * 0.6 + 1) * np.pi / 4)
L += (w * dL + (1 - w) * 0.5 * (dL + dR)) * pl * 1.41; R += (w * dR + (1 - w) * 0.5 * (dL + dR)) * pr * 1.41
hit = whoosh + 0.0                                                         # the snap-back whoosh sits centre-wide
L += hit * 0.8; R += hit * 0.8

# ---------------- crowd: wide, decorrelated; hushes in slow-mo, cheers on touchdown ----------------
def crowd_layer(n_voices, lo, hi, am_lo, am_hi, seed):
    r = np.random.default_rng(seed); outL = np.zeros(N); outR = np.zeros(N)
    for v in range(n_voices):
        fc = r.uniform(lo, hi); x = bp(r.standard_normal(N), fc / 1.6, fc * 1.6)
        am = 0.5 + 0.5 * np.sin(2 * np.pi * r.uniform(am_lo, am_hi) * tau + r.uniform(0, 6.28)) * (0.6 + 0.4 * np.sin(2 * np.pi * r.uniform(0.1, 0.4) * tau))
        p = r.uniform(-1, 1); outL += x * am * np.cos((p + 1) * np.pi / 4); outR += x * am * np.sin((p + 1) * np.pi / 4)
    return unit(outL), unit(outR)
mL, mR = crowd_layer(28, 250, 2200, 0.6, 3.0, 5)
cL, cR = crowd_layer(36, 450, 3400, 2.0, 6.0, 9)
claps = np.zeros((2, N)); r2 = np.random.default_rng(13)
for ch in range(2):
    for k in np.sort(r2.uniform(tl + 0.4, DUR, 140)):
        claps[ch] += env_at(k, 0.0004, 0.012) * r2.uniform(0.3, 1.0)
    claps[ch] = hp(claps[ch] * r2.standard_normal(N), 1500)
slow_w = np.clip((1 - spd) / (1 - T.SLOW), 0, 1)
murmur_env = (0.6 + 0.4 * np.clip((tau - 2.5) / 2.0, 0, 1)) * (1 - 0.8 * slow_w) * (1 - np.clip((tau - tl) / 0.3, 0, 1) * 0.5)
cheer_env = np.clip((tau - tl - 0.12) / 0.7, 0, 1) ** 1.5 * (1 - 0.2 * np.clip((tau - tl - 1.2) / 1.0, 0, 1)) + 0.45 * np.clip((tau - tsp - 0.5) / 2.5, 0, 1)
whis = np.zeros((2, N)); r3 = np.random.default_rng(17)
for k in range(9):
    t0w = r3.uniform(tl + 0.6, DUR - 0.6); f0w = r3.uniform(1900, 2900); ch = k % 2
    fw = f0w * (1 + 0.18 * np.clip((tau - t0w) / 0.35, 0, 1)) + 40 * np.sin(2 * np.pi * 6 * tau)
    whis[ch] += 0.05 * env_at(t0w, 0.04, 0.28) * osc(fw)
CL = 0.030 * mL * murmur_env + 0.110 * cL * cheer_env + 0.08 * claps[0] * cheer_env + whis[0] * cheer_env
CR = 0.030 * mR * murmur_env + 0.110 * cR * cheer_env + 0.08 * claps[1] * cheer_env + whis[1] * cheer_env

# ---------------- ambience + decorrelated reverb ----------------
gust = 0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * tau + 1.0)
ambL = 0.018 * unit(lp(np.cumsum(white()), 300)) * 0 + 0.010 * band(80, 300) + 0.006 * band(600, 3000) * gust
ambR = 0.010 * band(80, 300) + 0.006 * band(600, 3000) * (1 - 0.5 * gust)
def ir(seed, rt60=1.3):
    r = np.random.default_rng(seed); n = int(SR * rt60); x = r.standard_normal(n) * np.exp(-6.9 * np.arange(n) / n)
    x[: int(0.022 * SR)] = 0; return lp(x, 6000) / np.sqrt(np.sum(x ** 2))
send = out_c * 0.5 + hit * 0.4 + (jets_side[0] + jets_side[1]) * gain * 0.4
L += 0.30 * signal.fftconvolve(send, ir(101))[:N]; R += 0.30 * signal.fftconvolve(send, ir(202))[:N]
L += CL + ambL; R += CR + ambR
fade = np.clip(tau / 0.3, 0, 1) * np.clip((DUR - tau) / 0.5, 0, 1)
st = np.stack([L, R], 1) * fade[:, None]

# ---------------- loudness -16 LUFS, true peak <= -1.5 dBTP ----------------
meter = pyln.Meter(SR)
def true_peak_db(x):
    up = signal.resample_poly(x, 4, 1, axis=0); return 20 * np.log10(np.max(np.abs(up)) + 1e-12)
def limit(x, ceiling_db=-1.8):
    c = 10 ** (ceiling_db / 20); up = np.abs(signal.resample_poly(x, 4, 1, axis=0)).max(axis=1)
    pk = up.reshape(-1, 4).max(axis=1)[:len(x)]
    look = int(0.0015 * SR); pk = np.maximum.reduce([np.roll(pk, -k) for k in range(look)])
    g = np.minimum(1.0, c / np.maximum(pk, 1e-9))
    rel = np.exp(-1 / (0.08 * SR)); gs = np.empty_like(g); cur = 1.0
    for i in range(len(g)):
        cur = g[i] if g[i] < cur else g[i] + (cur - g[i]) * rel; gs[i] = cur
    return x * gs[:, None]
st = st / np.max(np.abs(st)) * 0.5
for it in range(8):
    st *= 10 ** ((-16.0 - meter.integrated_loudness(st)) / 20)
    st = limit(st)
    if abs(meter.integrated_loudness(st) + 16.0) < 0.1: break
lufs, tp = meter.integrated_loudness(st), true_peak_db(st)
corr = np.corrcoef(st[:, 0], st[:, 1])[0, 1]
sf.write(os.path.join(HERE, "sfx.wav"), st.astype(np.float32), SR, subtype="PCM_24")
print(f"SFX_DONE {DUR:.3f}s  LUFS {lufs:.2f}  truePeak {tp:.2f} dBTP  sample peak {20*np.log10(np.abs(st).max()):.2f} dBFS  L/R correlation {corr:.2f}")

# ---------------- events.txt (video timeline) ----------------
def tc(sec):
    f = int(round(sec * T.FPS)); return f"{f // (T.FPS * 3600):02d}:{f // (T.FPS * 60) % 60:02d}:{f // T.FPS % 60:02d}:{f % T.FPS:02d}"
def row(name, story_t, extra=""):
    v = OT(story_t); return f"{tc(v)}  {v:7.3f}s  frame {T.first_frame_at(ev, story_t):3d}  {name}{('  ' + extra) if extra else ''}"
a_s = ev["t_top"] - T.SM[0]; b_s = ev["t_top"] + T.SM[3]
lines = ["# stunt_v2 events (video timeline, 24 fps, 360 frames, 15.000 s). TC = HH:MM:SS:FF",
         row("launch", ev["t_launch"]), row("pass-by camera A (~1.3 m from the lens), whip-pan", ev["t_pass"]),
         row("cut (shot A -> shot B, loop entry)", ev["t_cut"]),
         row("slow-mo start (ramp down begins)", a_s), row("detach from the loop top + snap zoom", ev["t_top"]),
         row(f"slow-mo reaches {int(T.SLOW * 100)}%", a_s + T.SM[1]), row("slow-mo ramp back up begins", ev["t_top"] + T.SM[2])]
for (t0, dur, names, label) in ev["vpulses"]:
    lines.append(row(f"jet pulse: {label}", t0, f"nozzles {'+'.join(names)}, {dur:.2f}s story = {OT(t0 + dur) - OT(t0):.2f}s on screen"))
lines += [row("slow-mo ends (back to real time)", b_s), row("touchdown (camera B jolt)", ev["t_land"]), row("stop", ev["t_stop"]),
          row("push-in starts (car ~24% -> ~38% of frame width)", ev["t_stop"] + 0.25)]
lines = [lines[0]] + sorted(lines[1:], key=lambda l: float(l.split()[1].rstrip("s")))
lines += [
          f"{tc(15.0)}   15.000s  frame 360  end"]
open(os.path.join(HERE, "events.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
