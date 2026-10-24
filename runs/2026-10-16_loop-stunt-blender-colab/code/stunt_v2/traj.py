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
T_IDLE, ACC, V_LOOP, A_DRIVE = 0.6, 15.0, 22.5, 0.8     # v2.3: 0.6 s standing, ~1.3 g launch; loop entry speed unchanged
K_TAPER, S0 = 0.60, 3.4                                  # traction fades with speed; start 4.2 m along the bend
# v2.2 run-up: the car launches through a bend (curvature easing to zero) right past camera A, then runs straight onto the loop
X_LOOP = 23.13357018387007          # loop line kept from v2 (loop, lights and camera B are built around it)
PSI0, L_ARC, L_ST = math.radians(36.0), 20.0, 18.6
RUNWAY_CX = 12.0
_PDS = 0.01
def _build_path():
    k0 = 2 * PSI0 / L_ARC; x = y = 0.0; psi = PSI0; s = 0.0; pts = [(0.0, 0.0, PSI0, k0)]
    while s < L_ARC - 1e-9:
        k = k0 * (1 - (s + _PDS / 2) / L_ARC); pm = psi - k * _PDS / 2
        x += math.sin(pm) * _PDS; y += math.cos(pm) * _PDS; psi -= k * _PDS; s += _PDS
        pts.append((x, y, psi, k0 * max(0.0, 1 - s / L_ARC)))
    ox, oy = X_LOOP - x, Y_LOOP - L_ST - y
    return [(px + ox, py + oy, ps, kk) for (px, py, ps, kk) in pts]
_PATH = _build_path()
S_LOOP = L_ARC + L_ST
def runup(s):
    """(x, y), heading psi (0 = +Y, + = towards +X), curvature at path length s"""
    if s <= L_ARC:
        i = min(len(_PATH) - 2, int(s / _PDS)); u = s / _PDS - i; a, b = _PATH[i], _PATH[i + 1]
        return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u), a[2] + (b[2] - a[2]) * u, a[3] + (b[3] - a[3]) * u
    return (X_LOOP, Y_LOOP - L_ST + (s - L_ARC)), 0.0, 0.0
START = runup(S0)[0]
S_PASS, D_PASS, H_A0 = 8.2, 2.10, 0.50          # camera A: on the inside of the bend, the car's flank passes ~1.25 m from the lens
def _cam_a0():
    (x, y), psi, _ = runup(S_PASS)
    return (x - math.cos(psi) * D_PASS, y + math.sin(psi) * D_PASS, H_A0)
CAM_A = _cam_a0()
CAM_B = (15.0, 1.5, 0.78)
OLD_STOP = (20.6286, 14.1946)       # v1/v2 stop point: the final framing, wet patch and final light are kept relative to it
SLIDE_K, SLIDE_P = 0.106, 1.0       # v2.2: harder stop (~1.55 s, ~0.95 g)

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
    i = 0; s = S0; v = 0.0; spin = 0.0
    def rec(t, pos, X, Y, Z, **kw):
        d = dict(t=t, pos=pos, X=X, Y=Y, Z=Z, cg=add(pos, mul(Z, H_CG)), spin=spin, speed=kw.pop("speed", 0.0),
                 dz=0.0, pitch=0.0, roll=0.0, steer=0.0, droop=0.0, phase="", jets={}, dist=1e9)
        d.update(kw); S.append(d)
    # idle + run-up
    while True:
        t = i * DT
        a = 0.0
        if t >= T_IDLE and v < V_LOOP:
            a = ACC * sstep(0, 0.15, t - T_IDLE) * max(0.0, 1 - K_TAPER * (v / V_LOOP) ** 2)
        (px, py), psi, kap = runup(s)
        rec(t, (px, py, 0.0), (math.cos(psi), -math.sin(psi), 0.0), (math.sin(psi), math.cos(psi), 0.0), (0, 0, 1), speed=v,
            dist=s, phase="run" if t >= T_IDLE else "idle", dz=-0.028 * a / ACC, pitch=math.radians(2.8) * a / ACC,
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
    ev["t_launch"] = T_IDLE; tr = ev.get("t_retro", t_top + 1.5)
    ev["vpulses"] = [(t_top + 0.16, 0.20, ["LF_up", "LR_up"], "roll start: left pair"),
                     (t_top + 0.58, 0.15, ["LF_dn", "RF_dn"], "pitch trim: front pair"),
                     (t_top + 0.95, 0.20, ["RF_up", "RR_up"], "roll stop: right pair"),
                     (t_top + 1.36, 0.16, ["LR_dn", "RR_dn"], "attitude: rear pair"),
                     (tr + 0.00, 0.25, ["LF_dn", "RF_dn", "LR_dn", "RR_dn"], "retro burst 1: all four down"),
                     (tr + 0.33, 0.20, ["LF_dn", "RF_dn", "LR_dn", "RR_dn"], "retro burst 2: all four down")]
    ev["t_land"] = i * DT; ev["v_land"] = vel
    # slide
    vh = (vel[0], vel[1], 0.0); v0 = length(vh); d = norm(vh)
    fh = norm((Y[0], Y[1], 0.0))
    psi0 = math.atan2(cross(d, fh)[2], dot(d, fh))
    perp = cross((0, 0, 1), d)
    T_S = SLIDE_K * v0
    p0 = (cg[0], cg[1], 0.0); tau = 0.0; next_trail = 0.0
    ev["v0_slide"] = v0; ev["T_S"] = T_S
    while True:
        t = i * DT; u = min(1.0, tau / T_S)
        sd = v0 * T_S * (1 - (1 - u) ** (SLIDE_P + 1)) / (SLIDE_P + 1)
        sp = v0 * (1 - u) ** SLIDE_P
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

CAM_BS = (17.0, 47.0, 1.2)      # v2.1: position at the cut, clear view of the loop entry
CAM_B0 = (14.5, 46.0, 1.2)      # v2: operator on a camera car beside the loop
CAM_B1 = (15.0, 1.5, 0.78)      # ends exactly where the v1 final shot was framed
A_TARGET, A_MAXF, RUN_D = 0.125, 70.0, 4.5     # v2.2 camera A: car >= ~10% of frame height after the pass, zoom 24-28 -> <= 68 mm
B_CRASH, B_SETTLE_W, B_END_W, B_CREEP = 0.30, 0.24, 0.43, 0.8
B_MID_W = 0.36
B_ORBIT, B_ORBIT_IN, B_FIN_W = 18.0, 4.0, 0.45       # v2.5 final: orbit (deg), drive-in (m), car width at 15 s (bbox)
B_BRAKE_T, B_DRIVE_IN, B_SLIDE_W = 1.0, 4.5, 0.27         # v2.3: camera car brakes with the slide, then drives in 4 m
B_TARGET = 0.32                 # operator keeps the car at ~32% of frame height (zoom limited to 35..85 mm)
BOX = [(x, y, z) for x in (-0.98, 0.98) for y in (-2.15, 2.15) for z in (0.12, 1.10)]

def quat_mat(q):
    w, x, y, z = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
            (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
            (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)))

def bbox_frac(s, cam_loc, cam_quat, lens, sensor=36.0, aspect=1080 / 1350):
    """projected car bounding box: (height as a fraction of frame height, fully inside frame)"""
    Rm = quat_mat(cam_quat); pts = []
    for (bx, by, bz) in BOX:
        d = sub(add(add(add(s["pos"], mul(s["X"], bx)), mul(s["Y"], by)), mul(s["Z"], bz)), cam_loc)
        cx = Rm[0][0] * d[0] + Rm[1][0] * d[1] + Rm[2][0] * d[2]
        cy = Rm[0][1] * d[0] + Rm[1][1] * d[1] + Rm[2][1] * d[2]
        cz = Rm[0][2] * d[0] + Rm[1][2] * d[1] + Rm[2][2] * d[2]
        if cz > -0.1: return 0.0, False
        pts.append((lens * cx / -cz, lens * cy / -cz))
    hh = sensor / 2; hw = hh * aspect; xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (max(ys) - min(ys)) / sensor, (min(xs) > -hw and max(xs) < hw and min(ys) > -hh and max(ys) < hh)

def bbox_wfrac(s, cam_loc, cam_quat, lens, sensor=36.0, aspect=1080 / 1350):
    Rm = quat_mat(cam_quat); xs = []
    for (bx, by, bz) in BOX:
        d = sub(add(add(add(s["pos"], mul(s["X"], bx)), mul(s["Y"], by)), mul(s["Z"], bz)), cam_loc)
        cx = Rm[0][0] * d[0] + Rm[1][0] * d[1] + Rm[2][0] * d[2]; cz = Rm[0][2] * d[0] + Rm[1][2] * d[1] + Rm[2][2] * d[2]
        if cz > -0.1: return 0.0
        xs.append(lens * cx / -cz)
    return (max(xs) - min(xs)) / (sensor * aspect)

def _follow1(vals, w, z, init=None):
    """critically-damped follow of a scalar track (operator reaction)"""
    out, p, v = [], (vals[0] if init is None else init), 0.0
    for x in vals:
        a = (x - p) * w * w - v * 2 * z * w; v += a * DT; p += v * DT; out.append(p)
    return out

def _unwrap(a):
    out = [a[0]]
    for x in a[1:]:
        d = x - out[-1]; d -= 2 * math.pi * round(d / (2 * math.pi)); out.append(out[-1] + d)
    return out

def _dirv(yaw, pitch): return (math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch))

def cameras(S, ev):
    n = len(S); T = [s["t"] for s in S]; cg = [s["cg"] for s in S]
    t_cut = ev["t_loop"] - 0.04; ev["t_cut"] = t_cut          # cut on the motion as the car hits the loop
    nA = [Noise(s) for s in range(10, 20)]; nB = [Noise(s) for s in range(30, 40)]
    # ---------- camera A (v2.2): crouched at the bend, the car blasts past the lens, whip-pan ~160 deg, a few running steps, zoom in ----------
    runk = [k for k in range(n) if S[k]["phase"] == "run"]
    kp = min(runk, key=lambda k: math.hypot(cg[k][0] - CAM_A[0], cg[k][1] - CAM_A[1])); t_pass = T[kp]; ev["t_pass"] = t_pass
    ev["pass_dist"] = math.hypot(cg[kp][0] - CAM_A[0], cg[kp][1] - CAM_A[1])
    hd = S[kp]["Y"]; run_dir = norm((hd[0], hd[1], 0.0)); right = norm(cross(run_dir, (0.0, 0.0, 1.0)))
    posA, rsA = [], []
    for k in range(n):
        t = T[k]
        crab = 0.35 * sstep(0.0, t_pass - 0.4, t)                       # slow side-step while waiting: highlights slide over the paint
        g = sstep(t_pass + 0.05, t_pass + 1.9, t)                         # runs after the car
        rs = min(1.0, max(0.0, (sstep(t_pass + 0.05, t_pass + 1.9, t + 0.01) - sstep(t_pass + 0.05, t_pass + 1.9, t - 0.01)) / 0.02 * 1.85 / 1.5))
        up = sstep(t_pass - 0.12, t_pass + 0.55, t)                       # stands up during the whip
        ph = math.pi * 2.7 * t
        z = H_A0 + (1.38 - H_A0) * up + 0.032 * rs * (2 * abs(math.sin(ph)) - 1)
        p = add(add(CAM_A, mul(right, -crab + 0.025 * rs * math.sin(ph))), mul(run_dir, RUN_D * g))
        posA.append((p[0] + 0.02 * nA[0].fbm(0.35 * t), p[1] + 0.02 * nA[1].fbm(0.3 * t), z + 0.012 * nA[2].fbm(0.5 * t)))
        rsA.append(rs)
    vel = [sub(cg[min(n - 1, k + 1)], cg[max(0, k - 1)]) for k in range(n)]
    tgt = [add(add(cg[k], (0.0, 0.0, 0.18)), mul(vel[k], 0.06 / (2 * DT) * sstep(t_pass, t_pass + 0.6, T[k]))) for k in range(n)]
    yd = _unwrap([math.atan2(tgt[k][0] - posA[k][0], tgt[k][1] - posA[k][1]) for k in range(n)])
    pd = [math.atan2(tgt[k][2] - posA[k][2], math.hypot(tgt[k][0] - posA[k][0], tgt[k][1] - posA[k][1])) for k in range(n)]
    yawA = _follow1(yd, 10.0, 0.75); pitA = _follow1(pd, 8.0, 0.8)
    ev["whip_deg"] = math.degrees(abs(yawA[min(n - 1, kidx(t_cut))] - yawA[0]))
    aimA = [add(posA[k], _dirv(yawA[k], pitA[k])) for k in range(n)]
    q0 = _orient(posA[0], aimA[0], 0, 0, 0); wf0 = bbox_wfrac(S[0], posA[0], q0, 1.0)
    fA0 = min(28.0, max(18.0, 0.42 / wf0)); ev["fA0"] = fA0                 # v2.3: the car waits close: ~42% of the width needs ~19 mm
    fsz = []
    for k in range(n):
        q = _orient(posA[k], aimA[k], 0, 0, 0); fh, _ = bbox_frac(S[k], posA[k], q, 1.0)
        fsz.append(min(A_MAXF, max(fA0, A_TARGET / fh)) if fh > 0 else A_MAXF)
    fszl = _lag(fsz, 0.2)
    lensA = [fA0 + (fszl[k] - fA0) * sstep(t_pass + 0.3, t_pass + 1.1, T[k]) for k in range(n)]
    dA = [length(sub(cg[k], posA[k])) for k in range(n)]
    focA = _lag([dA[k] * (1 + 0.03 * nA[3](0.8 * T[k])) for k in range(n)], 0.15)
    # ---------- camera B: handheld from a camera car; loop entry -> flight -> final ----------
    kc = min(range(n), key=lambda k: abs(T[k] - t_cut))
    t_l, t_s = ev["t_land"], ev["t_stop"]; t_mv0 = ev["t_top"] - 0.3
    BM = (22.2, 25.0, 2.2)
    vel = [sstep(t_mv0, t_mv0 + 0.6, t) * (1 - sstep(t_l, t_s + 0.2, t)) for t in T]      # v2.2: stands still by the time the car stops
    acc_d = [0.0]
    for k in range(1, n): acc_d.append(acc_d[-1] + vel[k] * DT)
    tot = acc_d[-1] if acc_d[-1] > 0 else 1.0
    stop = ev["stop_pos"]; creep_dir = norm((stop[0] - CAM_B1[0], stop[1] - CAM_B1[1], 0.0))
    posB, mvB = [], []
    k_td = min(n - 1, kidx(t_l)); P_td = V_td = None
    for k in range(n):
        t = T[k]; g = min(1.0, acc_d[k] / tot) if t <= t_l else min(1.0, acc_d[k_td] / tot); mv = vel[k] if t <= t_l else 0.0
        tl = t - (t_l + 0.05); kick = -0.07 * math.exp(-tl / 0.25) if tl > 0 else 0.0     # the operator flinches at the impact
        CC = [2 * BM[i] - 0.5 * (CAM_B0[i] + CAM_B1[i]) for i in range(3)]
        pre = sstep(t_cut, ev["t_top"] - 0.45, t); B0d = [CAM_BS[i] + (CAM_B0[i] - CAM_BS[i]) * pre for i in range(3)]
        P = [(1 - g) ** 2 * B0d[i] + 2 * (1 - g) * g * CC[i] + g * g * CAM_B1[i] for i in range(3)]
        if k == k_td:
            P_td = list(P); gp = min(1.0, acc_d[k_td - 24] / tot)
            Pp = [(1 - gp) ** 2 * B0d[i] + 2 * (1 - gp) * gp * CC[i] + gp * gp * CAM_B1[i] for i in range(3)]
            V_td = [(P[i] - Pp[i]) / (24 * DT) for i in range(3)]
        if t > t_l and P_td is not None:                                    # v2.3: brake to a stop next to the sliding car
            sp = math.hypot(V_td[0], V_td[1]); dh = (V_td[0] / sp, V_td[1] / sp)
            u = min(1.0, (t - t_l) / B_BRAKE_T); trav = sp * B_BRAKE_T * (1 - (1 - u) ** 2) / 2
            P = [P_td[0] + dh[0] * trav, P_td[1] + dh[1] * trav, P_td[2]]
            mv = 1 - u
        zl = sstep(t_l + 0.35, t_s + 0.6, t)
        P[2] = P[2] * (1 - zl) + CAM_B1[2] * zl if g > 0.5 else P[2]
        if t > t_l and P_td is not None:                                    # then a slow drive-in towards the stopped car
            if "B_stopP" not in ev:
                sp = math.hypot(V_td[0], V_td[1]); dh = (V_td[0] / sp, V_td[1] / sp)
                ev["B_stopP"] = (P_td[0] + dh[0] * sp * B_BRAKE_T / 2, P_td[1] + dh[1] * sp * B_BRAKE_T / 2)
                creep_dir = norm((stop[0] - ev["B_stopP"][0], stop[1] - ev["B_stopP"][1], 0.0))
            cr = B_DRIVE_IN * sstep(t_l + 1.1, ev["t_end"] - 0.15, t); mv = max(mv, 0.3 * sstep(t_l + 1.1, t_l + 1.6, t) * (1 - sstep(ev["t_end"] - 0.6, ev["t_end"] - 0.15, t)))
        else:
            cr = 0.0
        mvB.append(mv)
        posB.append((P[0] + cr * creep_dir[0] + 0.02 * nB[0].fbm(0.4 * t) + 0.012 * mv * nB[9](9.0 * t),
                     P[1] + cr * creep_dir[1] + 0.02 * nB[1].fbm(0.33 * t),
                     P[2] + 0.015 * nB[2].fbm(0.45 * t) + 0.012 * mv * nB[9](11.0 * t + 5.0) + kick))
    # v2.5 final (from 9.5 s on screen): one continuous slow orbit around the stopped car + drive-in, light handheld
    k95 = min(n - 1, kidx(ev["frame_t"][int(round(9.5 * FPS))])); t95 = T[k95]; ev["t95"] = t95
    cx, cy = stop[0], stop[1]; p95 = posB[k95]; m95 = mvB[k95]
    p95c = (p95[0] - 0.02 * nB[0].fbm(0.4 * t95) - 0.012 * m95 * nB[9](9.0 * t95), p95[1] - 0.02 * nB[1].fbm(0.33 * t95),
            p95[2] - 0.015 * nB[2].fbm(0.45 * t95) - 0.012 * m95 * nB[9](11.0 * t95 + 5.0))
    r0 = math.hypot(p95c[0] - cx, p95c[1] - cy); a0 = math.atan2(p95c[0] - cx, p95c[1] - cy)
    fin_s = lambda t: (lambda u: 1.5 * u * u - 0.5 * u ** 3)(min(1.0, max(0.0, (t - t95) / max(1e-6, ev["t_end"] - t95))))   # eases in, still moving at the end
    for k in range(k95 + 1, n):
        t = T[k]; sm = fin_s(t); mv = m95 + (0.35 - m95) * min(1.0, (t - t95) / 0.5)
        a = a0 + math.radians(B_ORBIT) * sm; r = r0 - B_ORBIT_IN * sm
        posB[k] = (cx + r * math.sin(a) + 0.02 * nB[0].fbm(0.4 * t) + 0.012 * mv * nB[9](9.0 * t),
                   cy + r * math.cos(a) + 0.02 * nB[1].fbm(0.33 * t),
                   p95c[2] + 0.015 * nB[2].fbm(0.45 * t) + 0.012 * mv * nB[9](11.0 * t + 5.0) + 0.008 * math.sin(2 * math.pi * 1.7 * t))
        mvB[k] = mv
    lcB = (X_LOOP + X_DESC / 2, Y_LOOP, 6.0)
    LD = int(0.12 / DT)
    tgtB = [add(add(cg[min(n - 1, k + LD)] if T[k] < t_l else c, (0.0, 0.0, 0.2)),
                mul(sub(lcB, c), 0.22 * sstep(t_l + 0.5, t_s + 0.3, T[k]))) for k, c in enumerate(cg)]      # v2.3: the loop and beams stay above the car to the end
    aimB = _follow(tgtB[kc:], 9.0, 0.8, init=tgtB[kc]); aimB = [aimB[0]] * kc + aimB
    f_track, f_post = [], []
    tw0 = lambda t: (B_SLIDE_W + 0.02 * sstep(t_l + 0.45, t_s, t) + (B_MID_W - B_SLIDE_W - 0.02) * sstep(t_l + 0.9, t_l + 1.4, t)
                    + (B_END_W - B_MID_W) * sstep(t_l + 1.4, ev["t_end"] - 0.2, t))      # v2.4: never small after the landing
    tw = lambda t: tw0(t) if t <= t95 else tw0(t95) + (B_FIN_W - tw0(t95)) * fin_s(t)      # v2.5: grows with the orbit to ~45% at 15 s
    for k in range(n):
        q0 = _orient(posB[k], aimB[k], 0, 0, 0); fh, _ = bbox_frac(S[k], posB[k], q0, 1.0); fw = bbox_wfrac(S[k], posB[k], q0, 1.0)
        f_track.append(min(85.0, max(35.0, min(0.32 / fh, 0.74 / fw))) if fh > 0 and fw > 0 else 85.0)
        f_post.append(min(60.0, max(20.0, tw(T[k]) / fw)) if fw > 0 else 36.0)
    f_post = _lag(f_post, 0.08)
    q0 = _orient(posB[kc], aimB[kc], 0, 0, 0); fh0, _ = bbox_frac(S[kc], posB[kc], q0, 1.0)
    f_entry = min(85.0, max(35.0, 0.125 / fh0)) if fh0 > 0 else 60.0           # >= 12% of frame height right after the cut
    ks = min(n - 1, kidx(t_s + 0.15)); qs = _orient(posB[ks], aimB[ks], 0, 0, 0)
    f_settle = min(70.0, max(26.0, B_SETTLE_W / bbox_wfrac(S[ks], posB[ks], qs, 1.0)))    # just stopped: ~24% of frame width
    ke = min(n - 1, kidx(ev["t_end"])); qe = _orient(posB[ke], aimB[ke], 0, 0, 0)
    f_end = min(85.0, max(24.0, B_END_W / bbox_wfrac(S[ke], posB[ke], qe, 1.0)))      # end of the drive-in: ~39% of frame width
    ev["f_entry"], ev["f_settle"], ev["f_end"] = f_entry, f_settle, f_end
    sched = []
    for k in range(n):
        t = T[k]
        f = f_entry + (f_track[k] - f_entry) * sstep(t_cut, t_cut + 0.6, t)
        f = f + (f_post[k] - f) * sstep(t_l, t_l + 0.45, t)                # v2.3: widens on the impact, then the car only grows: ~30% -> ~39% (no wide shot)
        sched.append(f)
    lensB = _lag(sched[kc:], 0.3); lensB = [lensB[0]] * kc + lensB
    dB = [length(sub(cg[k], posB[k])) for k in range(n)]
    miss = lambda t: 1 + 0.08 * sstep(t_l + 0.05, t_l + 0.1, t) * (1 - sstep(t_l + 0.35, t_l + 0.65, t))
    focB = _lag([dB[k] * (1 + 0.03 * nB[3](0.9 * T[k])) * miss(T[k]) for k in range(n)], 0.3)
    fdet = first_frame_at(ev, ev["t_top"]); ev["crash_frame"] = fdet
    out = []
    for f in range(1, FRAMES + 1):
        k = min(n - 1, kidx(ev["frame_t"][f - 1])); t = T[k]
        tl = t - (t_l + 0.05)
        jolt = math.exp(-tl / 0.28) * math.sin(2 * math.pi * 6.5 * tl) if tl > 0 else 0.0
        jerk = math.exp(-tl / 0.07) * min(1.0, tl / 0.012) if tl > 0 else 0.0
        rs = rsA[k]; tj = t - T_IDLE
        jl = math.exp(-tj / 0.22) * math.sin(2 * math.pi * 8 * tj) if tj > 0 else 0.0            # v2.4: the launch boom shakes camera A
        ya = math.radians(0.45 * nA[4].fbm(0.6 * t) + 0.08 * nA[5](5.0 * t) + 0.5 * rs * nA[5](3.0 * t + 4.0) + 0.5 * jl)
        pa = math.radians(0.35 * nA[6].fbm(0.55 * t) + 0.08 * nA[7](6.0 * t) + 0.4 * rs * nA[7](3.4 * t + 2.0) + 0.9 * jl)
        ra = math.radians(0.6 * nA[8](0.3 * t) + 1.3 * rs * math.sin(math.pi * 2.7 * t))
        yb = math.radians(0.5 * nB[4].fbm(0.6 * t) + 0.1 * nB[5](5.5 * t) + 1.5 * jolt + 0.25 * mvB[k] * nB[9](6.0 * t + 2.0))
        pb = math.radians(0.4 * nB[6].fbm(0.5 * t) + 0.1 * nB[7](6.5 * t) + 2.4 * jolt - 1.6 * jerk + 0.25 * mvB[k] * nB[9](7.0 * t + 9.0))
        rb = math.radians(0.7 * nB[8](0.28 * t) + 1.0 * jolt)
        crash = 1.0 + B_CRASH * sstep(fdet - 1, fdet + 4, f) * (1 - sstep(fdet + 10, fdet + 36, f))     # snap zoom on the detach (~0.2 s)
        A = dict(loc=posA[k], quat=_orient(posA[k], aimA[k], ya, pa, ra), lens=lensA[k], focus=focA[k], fstop=2.8)
        B = dict(loc=posB[k], quat=_orient(posB[k], aimB[k], yb, pb, rb), lens=min(95.0, lensB[k] * crash), focus=focB[k], fstop=3.5)
        for C in (A, B): C["frac"], C["inside"] = bbox_frac(S[k], C["loc"], C["quat"], C["lens"])
        A["wfrac"] = bbox_wfrac(S[k], A["loc"], A["quat"], A["lens"]); B["wfrac"] = bbox_wfrac(S[k], B["loc"], B["quat"], B["lens"])
        out.append(dict(frame=f, t=t, A=A, B=B))
    for key in ("A", "B"):
        prev = None
        for o in out:
            q = o[key]["quat"]
            if prev and sum(a * b for a, b in zip(q, prev)) < 0: q = tuple(-c for c in q); o[key]["quat"] = q
            prev = q
    ev["cut_frame"] = first_frame_at(ev, t_cut)
    return out

def size_report(ev, C):
    """car bbox height in frame (active camera) from loop entry to landing"""
    act = lambda c: c["A"] if c["frame"] < ev["cut_frame"] else c["B"]
    rows = [(c["frame"], c["t"], act(c)["frac"], act(c)["inside"], act(c)["lens"]) for c in C if ev["t_loop"] <= c["t"] <= ev["t_land"]]
    loop = [r for r in rows if r[1] < ev["t_top"]]; fl = [r for r in rows if r[1] >= ev["t_top"]]
    mn = lambda rs: min(rs, key=lambda r: r[2])
    return dict(all=mn(rows), loop=mn(loop), flight=mn(fl), out_of_frame=[r[0] for r in rows if not r[3]])


# ---------------- v2.1: output timeline (speed ramp + slow-mo), exactly 360 frames ----------------
SLOW, FAST = 0.5, 1.0                # v2.2: ~2.3 s of slow-mo on the flip, everything else in real time
SM = (0.03, 0.15, 1.10, 1.60)        # ramp down from (t_top - 0.03) over 0.15 s; back to real time over t_top + 0.75 .. 1.20
FRAME_T = None
EV = None
def speed_at(t, ev):
    """playback speed as a function of story time: 1 = real time"""
    tt = ev["t_top"]
    w = sstep(tt - SM[0], tt - SM[0] + SM[1], t) * (1 - sstep(tt + SM[2], tt + SM[3], t))
    return 1.0 - (1.0 - SLOW) * w

def remap(ev):
    ts, tau = [0.0], [0.0]; t = 0.0
    while tau[-1] < FRAMES / FPS + 0.2:
        tau.append(tau[-1] + DT / speed_at(t + DT / 2, ev)); t += DT; ts.append(t)
    out, j = [], 0
    for f in range(1, FRAMES + 1):
        target = (f - 1) / FPS
        while tau[j + 1] < target: j += 1
        u = (target - tau[j]) / (tau[j + 1] - tau[j]); out.append(ts[j] + u * (ts[j + 1] - ts[j]))
    ev["frame_t"], ev["_ts"], ev["_tau"], ev["t_end"] = out, ts, tau, out[-1]
    return out

def out_time(ev, t):
    ts, tau = ev["_ts"], ev["_tau"]; i = min(len(ts) - 2, max(0, int(t / DT)))
    return tau[i] + (tau[i + 1] - tau[i]) * (t - ts[i]) / (ts[i + 1] - ts[i])

def first_frame_at(ev, t):
    return next((f for f in range(1, FRAMES + 1) if ev["frame_t"][f - 1] >= t - 1e-9), FRAMES)

def kidx(t): return int(round(t / DT))

def vjet(ev, name, t):
    """visual jet power at story time t (0..1, retro bursts 1.3)"""
    p = 0.0
    for (t0, dur, names, label) in ev["vpulses"]:
        if name in names: p = max(p, env(t, t0, dur, 0.025, 0.08 if "exhale" in label else 0.05) * (1.3 if "retro" in label else 0.6 if "exhale" in label else 1.0))
    return p

_V1 = None
def _v1_equiv_times(S):
    """v1 run-up (wait 1.5 s, 6 m/s^2): time at which the v1 car had covered the same distance"""
    global _V1
    if _V1 is None:
        d, v, t, tab = 0.0, 0.0, 0.0, []
        while d < S_LOOP + 5:
            a = 6.0 * sstep(0, 0.35, t - 1.5) * (1 - 0.3 * (v / V_LOOP) ** 2) if t >= 1.5 and v < V_LOOP else 0.0
            tab.append((d, t)); v += a * DT; d += v * DT; t += DT
        _V1 = tab
    import bisect
    ds = [x[0] for x in _V1]; out = []
    for s in S:
        if s["dist"] <= 1e-4: out.append(1.5 * min(1.0, s["t"] / T_IDLE)); continue
        if s["dist"] > ds[-1]: out.append(_V1[-1][1] + (s["t"] - S[0]["t"])); continue
        i = max(1, bisect.bisect_left(ds, s["dist"])); out.append(_V1[i][1])
    return out

def frames(S, ev):
    """car state for each output frame (sampled at the remapped story time)"""
    out = []
    for f in range(1, FRAMES + 1):
        s = dict(S[min(len(S) - 1, kidx(ev["frame_t"][f - 1]))]); s["frame"] = f
        s["quat"] = mat_to_quat(s["X"], s["Y"], s["Z"]); out.append(s)
    prev = None
    for s in out:
        if prev and sum(a * b for a, b in zip(s["quat"], prev)) < 0: s["quat"] = tuple(-c for c in s["quat"])
        prev = s["quat"]
    return out

def build_all():
    global FRAME_T, EV
    S, ev = simulate(); remap(ev); FRAME_T = ev["frame_t"]; EV = ev
    ev["t_exhale"] = ev["t_end"] - 1.5                                   # v2.2: last short breath from the nozzles
    ev["vpulses"].append((ev["t_exhale"], 0.30, ["LF_up", "RF_up", "LR_up", "RR_up"], "final exhale: all four up"))
    cams = cameras(S, ev); return S, ev, frames(S, ev), cams

if __name__ == "__main__":
    S, ev, F, C = build_all()
    for k in ("t_pass", "pass_dist", "whip_deg", "t_loop", "t_top", "v_top", "t_retro", "t_land", "v_land", "v0_slide", "T_S", "t_stop", "stop_pos", "t_cut", "cut_frame", "crash_frame", "t_exhale", "fA0", "f_entry", "f_settle", "f_end", "t_end"):
        v = ev.get(k); print(f"{k:10s}", tuple(round(x, 2) for x in v) if isinstance(v, tuple) else (round(v, 3) if isinstance(v, float) else v))
