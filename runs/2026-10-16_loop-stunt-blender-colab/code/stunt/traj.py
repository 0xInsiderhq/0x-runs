"""traj.py: timeline, car motion, thruster pulses, handheld cameras.
Pure python (no bpy). Used by the Blender build script and by the audio synth."""
import math, random

FPS, FRAMES, G = 24, 360, 9.81
SUB = 40                      # simulation substeps per frame
DT = 1.0 / (FPS * SUB)

# ---------------- layout (world metres, runway along +Y) ----------------
Y_LOOP = 62.0                 # loop entry (bottom of ascending half)
R = 9.0                       # loop riding-surface radius
X_DESC = 6.0                  # lateral offset of the descending half
TH_DESC0 = math.radians(196)  # descending half starts here (gap at the top)
H_CG = 0.48
WHEEL_R = 0.35
AXLE_F, AXLE_R = 1.20, -1.40
TRACK_F, TRACK_R = 0.83, 0.82
T_IDLE, ACC, V_LOOP, A_DRIVE = 1.5, 6.0, 22.5, 0.8
# run-up: diagonal away from the start camera, then an arc back onto the loop line -> the loop is seen at an angle
PSI0, L1, L2 = math.radians(38), 22.0, 30.0
K_ARC = PSI0 / L2
_X1, _Y1 = L1 * math.sin(PSI0), L1 * math.cos(PSI0)
X_LOOP = _X1 + (1 - math.cos(PSI0)) / K_ARC
_Y2 = _Y1 + math.sin(PSI0) / K_ARC
S_LOOP = L1 + L2 + (Y_LOOP - _Y2)
RUNWAY_CX = 12.0
def runup(s):
    """(x, y), heading psi (0 = +Y, + = towards +X), curvature at path length s"""
    if s <= L1: return (s * math.sin(PSI0), s * math.cos(PSI0)), PSI0, 0.0
    if s <= L1 + L2:
        u = s - L1; psi = PSI0 - K_ARC * u
        return (_X1 + (math.cos(psi) - math.cos(PSI0)) / K_ARC, _Y1 + (math.sin(PSI0) - math.sin(psi)) / K_ARC), psi, K_ARC
    return (X_LOOP, _Y2 + (s - L1 - L2)), 0.0, 0.0
CAM_A = (-5.0, -5.5, 1.38)
CAM_B = (15.0, 1.5, 0.78)

# thruster nozzles (car space: X right, Y forward, Z up) and jet directions
NOZZLES = {"LF": (-0.93, 0.62, 0.24), "LR": (-0.93, -0.92, 0.24),
           "RF": (0.93, 0.62, 0.24), "RR": (0.93, -0.92, 0.24)}
def _jdir(side, up):
    sx = -1.0 if side == "L" else 1.0
    v = (0.45 * sx, 0.0, 1.0 if up else -1.0); n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v)
JETS = {}
for k, p in NOZZLES.items():
    JETS[k + "_up"] = (p, _jdir(k[0], True))
    JETS[k + "_dn"] = (p, _jdir(k[0], False))
F_JET, F_RETRO, Z_RETRO = 4.0, 7.2, 6.2
PULSES = [  # (tau start after leaving the top, duration, jets, thrust per jet)
    (0.16, 0.20, ["LF_up", "LR_up", "RF_dn", "RR_dn"], F_JET),   # start the roll
    (0.56, 0.13, ["LR_up", "RF_dn"], 3.0),                       # trim
    (0.95, 0.20, ["RF_up", "RR_up", "LF_dn", "LR_dn"], F_JET),   # stop the roll
    (1.36, 0.13, ["LF_dn", "RF_dn", "LR_dn", "RR_dn"], 3.5),     # settle
]
ROLL_UP, ROLL_DN = (0.16, 0.36), (0.95, 1.15)

# ---------------- small vector helpers ----------------
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def length(a): return math.sqrt(dot(a, a))
def norm(a):
    l = length(a); return (a[0] / l, a[1] / l, a[2] / l) if l > 1e-12 else (0.0, 0.0, 0.0)
def rot(v, axis, ang):
    k = norm(axis); c, s = math.cos(ang), math.sin(ang)
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)))
def sstep(e0, e1, x):
    if e1 == e0: return 1.0 if x >= e1 else 0.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)
def mat_to_quat(X, Y, Z):
    m00, m01, m02 = X[0], Y[0], Z[0]; m10, m11, m12 = X[1], Y[1], Z[1]; m20, m21, m22 = X[2], Y[2], Z[2]
    tr = m00 + m11 + m22
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2; return (0.25 * s, (m21 - m12) / s, (m02 - m20) / s, (m10 - m01) / s)
    if m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2; return ((m21 - m12) / s, 0.25 * s, (m01 + m10) / s, (m02 + m20) / s)
    if m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2; return ((m02 - m20) / s, (m01 + m10) / s, 0.25 * s, (m12 + m21) / s)
    s = math.sqrt(1.0 + m22 - m00 - m11) * 2; return ((m10 - m01) / s, (m02 + m20) / s, (m12 + m21) / s, 0.25 * s)

class Noise:
    """1D gradient noise, roughly in [-1, 1]."""
    def __init__(self, seed):
        r = random.Random(seed); self.g = [r.uniform(-1, 1) for _ in range(1024)]
    def __call__(self, x):
        i = math.floor(x); f = x - i; g0 = self.g[i % 1024]; g1 = self.g[(i + 1) % 1024]
        u = f * f * f * (f * (f * 6 - 15) + 10); return 2.0 * (g0 * f * (1 - u) + g1 * (f - 1) * u)
    def fbm(self, x, octaves=3):
        a, s, tot = 1.0, 0.0, 0.0
        for o in range(octaves):
            s += a * self(x * (2 ** o) + 17.3 * o); tot += a; a *= 0.5
        return s / tot

def env(tau, t0, dur, rise=0.03, fall=0.06):
    return sstep(t0, t0 + rise, tau) * (1.0 - sstep(t0 + dur - fall, t0 + dur, tau))

def jet_world(name, X, Y, Z):
    p, d = JETS[name]
    return add(add(mul(X, d[0]), mul(Y, d[1])), mul(Z, d[2]))

# ---------------- car simulation ----------------
def simulate():
    S, ev = [], {"pulses": [], "trail": []}
    i = 0; s = 0.0; v = 0.0; spin = 0.0
    def rec(t, pos, X, Y, Z, **kw):
        d = dict(t=t, pos=pos, X=X, Y=Y, Z=Z, cg=add(pos, mul(Z, H_CG)), spin=spin, speed=kw.pop("speed", 0.0),
                 dz=0.0, pitch=0.0, roll=0.0, steer=0.0, droop=0.0, phase="", jets={})
        d.update(kw); S.append(d)
    # idle + run-up
    while True:
        t = i * DT
        a = 0.0
        if t >= T_IDLE and v < V_LOOP:
            a = ACC * sstep(0, 0.35, t - T_IDLE) * (1 - 0.3 * (v / V_LOOP) ** 2)
        (px, py), psi, kap = runup(s)
        rec(t, (px, py, 0.0), (math.cos(psi), -math.sin(psi), 0.0), (math.sin(psi), math.cos(psi), 0.0), (0, 0, 1), speed=v,
            phase="run" if t >= T_IDLE else "idle", dz=-0.012 * a / ACC, pitch=math.radians(1.3) * a / ACC,
            roll=math.radians(1.5) * min(1.0, v * v * kap / 5.0), steer=math.atan(2.6 * kap))
        v += a * DT; s += v * DT; spin -= v / WHEEL_R * DT; i += 1
        if s >= S_LOOP: break
    ev["t_loop"] = i * DT
    # loop (ascending half)
    th, v0, Rc = 0.0, v, R - H_CG
    while th < math.pi:
        t = i * DT
        v = math.sqrt(max(v0 * v0 - 2 * G * Rc * (1 - math.cos(th)) + 2 * A_DRIVE * R * th, 1.0))
        X = (1.0, 0.0, 0.0); Y = (0.0, math.cos(th), math.sin(th)); Z = (0.0, -math.sin(th), math.cos(th))
        n = v * v / (G * R) + math.cos(th)
        rec(t, (X_LOOP, Y_LOOP + R * math.sin(th), R * (1 - math.cos(th))), X, Y, Z, speed=v, phase="loop",
            dz=-0.015 * (n - 1))
        th += v / R * DT; spin -= v / WHEEL_R * DT; i += 1
    ev["t_top"] = i * DT; ev["v_top"] = v
    # flight
    t_top = ev["t_top"]
    cg = (X_LOOP, Y_LOOP, 2 * R - H_CG); vel = (0.0, -v, 0.0)
    shape = lambda tau: sstep(*ROLL_UP, tau) * (1 - sstep(*ROLL_DN, tau))
    integ, tau = 0.0, 0.0
    while tau < ROLL_DN[1] + 0.01:
        integ += shape(tau) * DT; tau += DT
    w_c = math.pi / integ
    pulses = [list(p) for p in PULSES]
    roll, tau, spin_rate, retro = 0.0, 0.0, -v / WHEEL_R, False
    while True:
        t = i * DT
        Y0, Z0, X0 = (0.0, -1.0, 0.0), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0)
        Z = rot(Z0, Y0, roll); X = rot(X0, Y0, roll); Y = Y0
        pw = math.radians(3.5) * math.sin(2 * math.pi * 0.6 * tau) * math.exp(-tau / 1.5)
        Y = rot(Y, X, pw); Z = rot(Z, X, pw)
        yaw = math.radians(3.0) * sstep(0.8, 2.0, tau)
        X, Y, Z = rot(X, (0, 0, 1), yaw), rot(Y, (0, 0, 1), yaw), rot(Z, (0, 0, 1), yaw)
        acc = (0.0, 0.0, -G); jets = {}
        for (t0, dur, names, F) in pulses:
            e = env(tau, t0, dur)
            if e > 0:
                for nme in names:
                    jets[nme] = max(jets.get(nme, 0.0), e * F / F_JET)
                    acc = add(acc, mul(jet_world(nme, X, Y, Z), -F * e))
        rolled = tau > ROLL_DN[1]
        if rolled and not retro and cg[2] < Z_RETRO:
            retro = True; ev["t_retro"] = t
            pulses.append((tau, 0.55, ["LF_dn", "RF_dn", "LR_dn", "RR_dn"], F_RETRO))
        if rolled and cg[2] <= H_CG:
            break
        rec(t, sub(cg, mul(Z, H_CG)), X, Y, Z, speed=length(vel), phase="flight", droop=-0.05, jets=jets,
            roll_angle=roll)
        vel = add(vel, mul(acc, DT)); cg = add(cg, mul(vel, DT))
        roll += w_c * shape(tau) * DT; spin += spin_rate * DT; spin_rate *= math.exp(-DT / 2.5)
        tau += DT; i += 1
    ev["pulses"] = [(t_top + p[0], p[1], p[2], p[3]) for p in pulses]
    ev["t_land"] = i * DT; ev["v_land"] = vel
    # slide
    vh = (vel[0], vel[1], 0.0); v0 = length(vh); d = norm(vh)
    fh = norm((Y[0], Y[1], 0.0))
    psi0 = math.atan2(cross(d, fh)[2], dot(d, fh))
    perp = cross((0, 0, 1), d)
    T_S = 1.2 * v0 / 7.0
    p0 = (cg[0], cg[1], 0.0); tau = 0.0; next_trail = 0.0
    ev["v0_slide"] = v0; ev["T_S"] = T_S
    while True:
        t = i * DT; u = min(1.0, tau / T_S)
        sd = v0 * T_S * (1 - (1 - u) ** 2.25) / 2.25
        sp = v0 * (1 - u) ** 1.25
        psi = psi0 + (math.radians(20) - psi0) * sstep(0, 0.55, u) - math.radians(6) * sstep(0.55, 1, u)
        Yh = rot(d, (0, 0, 1), psi); Z = (0.0, 0.0, 1.0); X = cross(Yh, Z)
        pos = add(add(p0, mul(d, sd)), mul(perp, -2.5 * sstep(0, 1, u)))
        decel = sstep(0, 0.1, tau) * (1 - sstep(0.85, 1, u))
        rec(t, pos, X, Yh, Z, speed=sp, phase="slide",
            dz=-0.11 * math.exp(-3.5 * tau) * math.sin(2 * math.pi * 1.6 * tau),
            pitch=-math.radians(2.2) * decel, roll=math.radians(1.8) * sstep(0, 0.3, u) * (1 - sstep(0.7, 1, u)),
            steer=-math.radians(10) * sstep(0.05, 0.35, u) * (1 - sstep(0.6, 1.0, u)))
        if tau >= next_trail and sp > 2.5:
            for side in (-1, 1):
                hub = add(add(pos, mul(X, side * TRACK_R)), mul(Yh, AXLE_R))
                ev["trail"].append((t, hub, sp))
            next_trail += 0.1
        spin += -(v0 / WHEEL_R) * math.exp(-tau / 0.12) * DT
        tau += DT; i += 1
        if u >= 1.0: break
    ev["t_stop"] = i * DT; ev["stop_pos"] = pos
    # rest
    while i * DT <= FRAMES / FPS + 0.5:
        t = i * DT; tr = t - ev["t_stop"]
        rec(t, pos, X, Yh, Z, speed=0.0, phase="rest",
            pitch=math.radians(1.6) * math.exp(-tr / 0.45) * math.cos(2 * math.pi * 1.2 * tr))
        i += 1
    return S, ev

# ---------------- handheld cameras ----------------
def _follow(targets, w, z, init=None):
    out, p, v = [], (init or targets[0]), (0.0, 0.0, 0.0)
    for tg in targets:
        a = sub(mul(sub(tg, p), w * w), mul(v, 2 * z * w))
        v = add(v, mul(a, DT)); p = add(p, mul(v, DT)); out.append(p)
    return out

def _lag(vals, tau):
    out, y = [], vals[0]
    k = 1 - math.exp(-DT / tau)
    for x in vals:
        y += (x - y) * k; out.append(y)
    return out

def _orient(pos, aim, yaw, pitch, rollv):
    f = norm(sub(aim, pos)); r = norm(cross(f, (0, 0, 1))); u = cross(r, f)
    f = rot(f, u, yaw); f = rot(f, r, pitch); r = norm(cross(f, (0, 0, 1))); u = cross(r, f)
    r = rot(r, f, rollv); u = rot(u, f, rollv)
    return mat_to_quat(r, u, mul(f, -1))

def cameras(S, ev):
    n = len(S); T = [s["t"] for s in S]; cg = [s["cg"] for s in S]
    t_cut = ev["t_top"] + 0.05; ev["t_cut"] = t_cut
    nA = [Noise(s) for s in range(10, 20)]; nB = [Noise(s) for s in range(30, 40)]
    # camera A: operator at the start line
    comp = []
    for k in range(n):
        t = T[k]; c = cg[k]
        zc = 0.45 + 6.5 * sstep(3.6, 6.2, t)
        wl = 0.3 * sstep(2.5, 4.5, t) * (1 - sstep(6.4, 7.2, t)); lc = (X_LOOP + X_DESC / 2, Y_LOOP)
        comp.append((c[0] + wl * (lc[0] - c[0]), c[1] + 0.8 * sstep(0, 1, t / 3) + wl * (lc[1] - c[1]), max(c[2] + 0.25, zc if c[2] < 6 else c[2] + 2.0)))
    aimA = _follow(comp, 7.0, 0.72)
    posA, lensA = [], []
    for k in range(n):
        t = T[k]
        posA.append((CAM_A[0] + 0.025 * nA[0].fbm(0.35 * t), CAM_A[1] + 0.02 * nA[1].fbm(0.3 * t),
                     CAM_A[2] + 0.018 * nA[2].fbm(0.5 * t) + 0.004 * math.sin(2 * math.pi * 0.25 * t)))
        z1 = sstep(2.8, 4.0, t); z2 = sstep(4.6, 6.2, t)
        over = 3.0 * math.exp(-((t - 6.25) / 0.25) ** 2)
        lensA.append(24 + 26 * z1 + 35 * z2 + over)
    dA = [length(sub(cg[k], posA[k])) for k in range(n)]
    hunt = lambda t: 1 + 0.12 * math.exp(-((t - 5.3) / 0.18) ** 2)
    focA = _lag([dA[k] * (1 + 0.035 * nA[3](0.8 * T[k])) * hunt(T[k]) for k in range(n)], 0.25)
    # camera B: second operator, kneeling right of the runway
    kc = min(range(n), key=lambda k: abs(T[k] - t_cut))
    lc = (X_LOOP + X_DESC / 2, Y_LOOP, 6.0)
    tgtB = [add(add(c, (0.0, 0.0, 0.2)), mul(sub(lc, c), 0.22 * sstep(ev['t_land'] + 0.5, ev['t_stop'] + 0.3, T[k]))) for k, c in enumerate(cg)]
    aimB = _follow(tgtB[kc:], 6.0, 0.75, init=tgtB[kc]); aimB = [aimB[0]] * kc + aimB
    t_land = ev["t_land"] + 0.08
    posB, lensB_raw = [], []
    for k in range(n):
        t = T[k]; tl = t - t_land
        kick = -0.04 * math.exp(-max(tl, 0) / 0.3) * (1 if tl > 0 else 0)
        posB.append((CAM_B[0] + 0.02 * nB[0].fbm(0.4 * t), CAM_B[1] + 0.02 * nB[1].fbm(0.33 * t),
                     CAM_B[2] + 0.015 * nB[2].fbm(0.45 * t) + kick))
        d = length(sub(cg[k], CAM_B))
        lensB_raw.append(45 + 20 * sstep(18, 60, d))
    lensB = _lag(lensB_raw[kc:], 0.6); lensB = [lensB[0]] * kc + lensB
    dB = [length(sub(cg[k], posB[k])) for k in range(n)]
    miss = lambda t: 1 + 0.08 * sstep(t_land, t_land + 0.05, t) * (1 - sstep(t_land + 0.3, t_land + 0.6, t))
    focB = _lag([dB[k] * (1 + 0.03 * nB[3](0.9 * T[k])) * miss(T[k]) for k in range(n)], 0.3)
    out = []
    for f in range(1, FRAMES + 1):
        k = (f - 1) * SUB; t = T[k]
        tl = t - t_land; fl = math.exp(-tl / 0.35) * math.sin(2 * math.pi * 7 * tl) if tl > 0 else 0.0
        ya = math.radians(0.45 * nA[4].fbm(0.6 * t) + 0.08 * nA[5](5.0 * t))
        pa = math.radians(0.35 * nA[6].fbm(0.55 * t) + 0.08 * nA[7](6.0 * t))
        ra = math.radians(0.6 * nA[8](0.3 * t))
        yb = math.radians(0.5 * nB[4].fbm(0.6 * t) + 0.1 * nB[5](5.5 * t) + 0.8 * fl)
        pb = math.radians(0.4 * nB[6].fbm(0.5 * t) + 0.1 * nB[7](6.5 * t) + 1.4 * fl)
        rb = math.radians(0.7 * nB[8](0.28 * t))
        out.append(dict(frame=f, t=t,
                        A=dict(loc=posA[k], quat=_orient(posA[k], aimA[k], ya, pa, ra), lens=lensA[k], focus=focA[k], fstop=2.8),
                        B=dict(loc=posB[k], quat=_orient(posB[k], aimB[k], yb, pb, rb), lens=lensB[k], focus=focB[k], fstop=3.5)))
    for key in ("A", "B"):
        prev = None
        for o in out:
            q = o[key]["quat"]
            if prev and sum(a * b for a, b in zip(q, prev)) < 0: q = tuple(-c for c in q); o[key]["quat"] = q
            prev = q
    ev["cut_frame"] = int(math.ceil(t_cut * FPS)) + 1
    return out

def frames(S):
    """Car samples at frame times (frame 1 = t 0)."""
    out = []
    for f in range(1, FRAMES + 1):
        s = dict(S[(f - 1) * SUB]); s["frame"] = f
        s["quat"] = mat_to_quat(s["X"], s["Y"], s["Z"]); out.append(s)
    prev = None
    for s in out:
        if prev and sum(a * b for a, b in zip(s["quat"], prev)) < 0: s["quat"] = tuple(-c for c in s["quat"])
        prev = s["quat"]
    return out

def build_all():
    S, ev = simulate(); cams = cameras(S, ev); return S, ev, frames(S), cams

if __name__ == "__main__":
    S, ev, F, C = build_all()
    for k in ("t_loop", "t_top", "v_top", "t_retro", "t_land", "v_land", "v0_slide", "T_S", "t_stop", "stop_pos", "t_cut", "cut_frame"):
        v = ev.get(k); print(f"{k:10s}", tuple(round(x, 2) for x in v) if isinstance(v, tuple) else (round(v, 3) if isinstance(v, float) else v))
