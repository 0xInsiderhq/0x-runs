"""clip_B hero shape: ONE smooth sculpture in a rest A-pose (signed distance field: tapered capsules + ellipsoids joined by
smooth unions, no joints / segments / gaps), meshed by marching cubes. Poses are made later in Blender with an armature on this
single mesh (hero.py); the bones are written next to the mesh.
Neutral build: ~7.5 heads tall, shoulders ~2 head widths, no pronounced chest, modest hips; full limbs; simplified hands with a
separate thumb; short feet with volume; normal neck; smooth faceless oval head with a light hint of a jaw.
Runs in the Colab kernel (numpy/torch + scikit-image), not in Blender.
usage: python3 hero_shape.py OUTDIR NAME   -> OUTDIR/NAME_shell.npz, NAME_core.npz (verts, faces, bones json)
hero space: metres, feet at z=0, facing -Y, +X = hero's left."""
import sys, os, json, math, time
import numpy as np
try:
    import torch; xp = torch; DEV = "cuda" if torch.cuda.is_available() else "cpu"
except Exception:
    torch = None; xp = np; DEV = None

CORE_K = 0.85        # inner emissive copy: every radius and blend x 0.85, same skeleton
VOXEL = 0.0045
H = 1.78             # height; head = H / 7.5 = 0.237

def nv(*a): return np.array(a if len(a) == 3 else a[0], dtype=np.float64)
def unit(v): v = nv(v); return v / np.linalg.norm(v)
def frame(x_hint, z):                      # columns: local x, y, z (z along the part)
    z = unit(z); x = nv(x_hint); x = unit(x - x.dot(z) * z); y = np.cross(z, x); return np.stack([x, y, z], 1)
def cols(a, b, c): return np.stack([unit(a), unit(b), unit(c)], 1)

# ---------------- rest skeleton (A-pose: arms 30 deg out, legs slightly apart) ----------------
ARM_A = math.radians(30)
def rest_joints():
    J = dict(hips=(0, 0.0, 0.930), spine=(0, 0.0, 1.050), chest=(0, 0.0, 1.220), neck=(0, 0.008, 1.400), head=(0, 0.0, 1.570), head_t=(0, 0.0, 1.750))
    for s, sx in (("L", 1), ("R", -1)):
        sh = nv(0.126 * sx, 0.0, 1.430); d = nv(math.sin(ARM_A) * sx, 0.0, -math.cos(ARM_A))
        J["clav" + s] = (0.020 * sx, 0.010, 1.385); J["sh" + s] = sh
        J["el" + s] = sh + d * 0.285; J["wr" + s] = J["el" + s] + d * 0.255; J["hand_t" + s] = J["wr" + s] + d * 0.170
        J["hip" + s] = (0.078 * sx, 0.0, 0.905); J["knee" + s] = (0.105 * sx, -0.005, 0.490)
        J["ankle" + s] = (0.115 * sx, 0.015, 0.080); J["ball" + s] = (0.118 * sx, -0.105, 0.028)
    return {k: nv(v) for k, v in J.items()}

def bones(J):
    """name, head, tail, parent, connected (Blender armature, hero space)"""
    B = [("hips", J["hips"], J["spine"], None, False), ("spine", J["spine"], J["chest"], "hips", True),
         ("chest", J["chest"], J["neck"], "spine", True), ("neck", J["neck"], J["head"], "chest", True), ("head", J["head"], J["head_t"], "neck", True)]
    for s in "LR":
        B += [("shoulder." + s, J["clav" + s], J["sh" + s], "chest", False), ("upperarm." + s, J["sh" + s], J["el" + s], "shoulder." + s, True),
              ("forearm." + s, J["el" + s], J["wr" + s], "upperarm." + s, True), ("hand." + s, J["wr" + s], J["hand_t" + s], "forearm." + s, True),
              ("thigh." + s, J["hip" + s], J["knee" + s], "hips", False), ("shin." + s, J["knee" + s], J["ankle" + s], "thigh." + s, True),
              ("foot." + s, J["ankle" + s], J["ball" + s], "shin." + s, True)]
    return [dict(name=n, head=[float(x) for x in h], tail=[float(x) for x in t], parent=p, connect=c) for n, h, t, p, c in B]

# ---------------- SDF primitives on a grid ----------------
class Field:
    def __init__(self, X, Y, Z): self.X, self.Y, self.Z = X, Y, Z
    def ell(self, c, F, r):                                         # ellipsoid (approximate distance), F columns = local axes
        dx, dy, dz = self.X - float(c[0]), self.Y - float(c[1]), self.Z - float(c[2])
        p = [dx * float(F[0, i]) + dy * float(F[1, i]) + dz * float(F[2, i]) for i in range(3)]
        k0 = xp.sqrt(sum((p[i] / r[i]) ** 2 for i in range(3)))
        k1 = xp.sqrt(sum((p[i] / (r[i] * r[i])) ** 2 for i in range(3))) + 1e-9
        return k0 * (k0 - 1.0) / k1
    def cone(self, a, b, r1, r2):                                   # round cone = tapered capsule (exact, Quilez)
        a, b = nv(a), nv(b); ba = b - a; l2 = float(ba.dot(ba)); rr = r1 - r2; a2 = l2 - rr * rr; il2 = 1.0 / l2
        pax, pay, paz = self.X - float(a[0]), self.Y - float(a[1]), self.Z - float(a[2])
        y = pax * float(ba[0]) + pay * float(ba[1]) + paz * float(ba[2]); z = y - l2
        qx, qy, qz = pax * l2 - y * float(ba[0]), pay * l2 - y * float(ba[1]), paz * l2 - y * float(ba[2])
        x2 = qx * qx + qy * qy + qz * qz; y2 = y * y * l2; z2 = z * z * l2; k = math.copysign(1.0, rr) * rr * rr * x2 if rr != 0 else 0.0 * x2
        d = (xp.sqrt(x2 * a2 * il2) + y * rr) * il2 - r1
        d = xp.where(xp.sign(y) * a2 * y2 < k, xp.sqrt(x2 + y2) * il2 - r1, d)
        d = xp.where(xp.sign(z) * a2 * z2 > k, xp.sqrt(x2 + z2) * il2 - r2, d)
        return d
def smin(a, b, k):
    h = xp.clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0) if xp is torch else np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)

def hand_sdf(G, J, side, s=1.0):
    """simplified hand with a separate thumb + a short wrist stub (slightly inside the forearm, so a union with the body has no coplanar faces)"""
    def E(c, F, r): return G.ell(c, F, [x * s for x in r])
    def Cn(a, b, r1, r2): return G.cone(a, b, r1 * s, r2 * s)
    sx = 1 if side == "L" else -1; wr, ht, el = J["wr" + side], J["hand_t" + side], J["el" + side]
    hdv = unit(ht - wr); n = unit(nv(-math.cos(ARM_A) * sx, 0, -math.sin(ARM_A))); t = nv(0, -1, 0); F = cols(n, t, hdv)
    hand = E(wr + hdv * 0.045, F, (0.019, 0.039, 0.050))                                   # palm
    hand = smin(hand, E(wr + hdv * 0.112 + n * 0.006, F, (0.0165, 0.035, 0.052)), 0.02 * s)  # fingers together, slightly curled
    hand = smin(hand, Cn(wr + hdv * 0.022 + t * 0.026 + n * 0.008, wr + hdv * 0.074 + t * 0.043 + n * 0.017, 0.0160, 0.0125), 0.007 * s)  # thumb
    return smin(Cn(wr + unit(el - wr) * 0.065, wr, 0.0262, 0.0252), hand, 0.02 * s)

def body_sdf(G, J, s=1.0, hands=True):
    """s scales every radius and blend (s = 0.85 -> the inner copy on the same skeleton)"""
    def E(c, F, r): return G.ell(c, F, [x * s for x in r])
    def Cn(a, b, r1, r2): return G.cone(a, b, r1 * s, r2 * s)
    def lerp(a, b, f): return a + (b - a) * f
    I = np.eye(3)
    # torso: ribcage + upper back, waist, pelvis, modest glutes -- one soft mass (no chest forms)
    d = E(nv(0, 0.010, 1.290), I, (0.122, 0.086, 0.165))
    d = smin(d, E(nv(0, 0.022, 1.372), I, (0.138, 0.072, 0.080)), 0.08 * s)
    d = smin(d, E(nv(0, 0.000, 1.100), I, (0.099, 0.078, 0.125)), 0.09 * s)
    d = smin(d, E(nv(0, 0.006, 0.955), I, (0.106, 0.082, 0.105)), 0.08 * s)
    for sx in (-1, 1): d = smin(d, E(nv(0.048 * sx, 0.040, 0.905), I, (0.052, 0.048, 0.066)), 0.05 * s)
    # neck (normal thickness) + faceless oval head with a light jaw
    d = smin(d, Cn(nv(0, 0.012, 1.395), nv(0, 0.0, 1.575), 0.058, 0.052), 0.07 * s)
    hd = smin(E(nv(0, 0.004, 1.675), I, (0.0825, 0.099, 0.105)), E(nv(0, -0.024, 1.598), I, (0.058, 0.068, 0.056)), 0.05 * s)
    d = smin(d, hd, 0.04 * s)
    for side, sx in (("L", 1), ("R", -1)):
        sh, el, wr, ht = J["sh" + side], J["el" + side], J["wr" + side], J["hand_t" + side]
        ad = unit(el - sh); lat = nv(sx, 0, 0)
        # shoulder cap (deltoid) melts into the torso; arm: full upper arm and forearm, simplified hand with a separate thumb
        d = smin(d, E(sh + ad * 0.010 + nv(0, 0, 0.004), frame(lat, ad), (0.044, 0.050, 0.062)), 0.07 * s)
        fe = wr if hands else wr + (el - wr) * (0.030 / 0.255)                                  # no hands: the forearm ends 3 cm before the wrist
        a = smin(Cn(sh, el, 0.048, 0.037), Cn(el, fe, 0.037, 0.027 if hands else 0.0282), 0.015 * s)
        a = smin(a, E(lerp(sh, el, 0.45), frame(lat, ad), (0.049, 0.051, 0.110)), 0.035 * s)
        a = smin(a, E(lerp(el, wr, 0.30), frame(lat, wr - el), (0.044, 0.038, 0.095)), 0.035 * s)
        hdv = unit(ht - wr); n = unit(nv(-math.cos(ARM_A) * sx, 0, -math.sin(ARM_A))); t = nv(0, -1, 0)   # palm faces the thigh, thumb forward
        F = cols(n, t, hdv)
        hand = E(wr + hdv * 0.045, F, (0.019, 0.039, 0.050))                                   # palm
        hand = smin(hand, E(wr + hdv * 0.112 + n * 0.006, F, (0.0165, 0.035, 0.052)), 0.02 * s)  # fingers together, slightly curled
        hand = smin(hand, Cn(wr + hdv * 0.022 + t * 0.026 + n * 0.008, wr + hdv * 0.074 + t * 0.043 + n * 0.017, 0.0160, 0.0125), 0.007 * s)  # thumb along the index side
        if hands: a = smin(a, hand, 0.02 * s)
        d = smin(d, a, 0.03 * s)
        # leg: full thigh and calf, short foot with volume (heel, instep, toe box)
        hp, kn, an, ba = J["hip" + side], J["knee" + side], J["ankle" + side], J["ball" + side]
        l = smin(Cn(hp, kn, 0.072, 0.051), Cn(kn, an, 0.050, 0.034), 0.015 * s)
        l = smin(l, E(lerp(hp, kn, 0.40), frame(lat, kn - hp), (0.060, 0.070, 0.200)), 0.05 * s)
        Fl = frame(lat, an - kn); l = smin(l, E(lerp(kn, an, 0.30) + Fl @ nv(0, 0.016, 0), Fl, (0.052, 0.056, 0.130)), 0.04 * s)
        f = smin(Cn(an + nv(0, 0.032, -0.048), an + nv(0, -0.100, -0.050), 0.033, 0.032), E(an + nv(0, -0.045, -0.025), I, (0.040, 0.075, 0.036)), 0.03 * s)
        f = smin(f, E(an + nv(0, -0.118, -0.055), I, (0.042, 0.040, 0.022)), 0.03 * s)
        l = smin(l, f, 0.03 * s)
        d = smin(d, l, 0.04 * s)
    d = smin(d, E(nv(0, 0.002, 0.885), I, (0.118, 0.080, 0.070)), 0.05 * s)   # mannequin-smooth pelvis and groin, no bulges
    return d

def mesh(J, s, voxel=VOXEL, part="full"):
    from skimage.measure import marching_cubes
    lo, hi = nv(-0.58, -0.26, -0.03), nv(0.58, 0.20, 1.81)
    if part.startswith("hand"):
        sd = part[-1]; pts = np.stack([J["wr" + sd], J["hand_t" + sd], J["wr" + sd] + unit(J["wr" + sd] - J["el" + sd]) * -0.07]); lo, hi = pts.min(0) - 0.06, pts.max(0) + 0.06
    n = np.ceil((hi - lo) / voxel).astype(int) + 1
    if torch is not None:
        ax = [torch.tensor(lo[i] + voxel * np.arange(n[i]), dtype=torch.float32, device=DEV) for i in range(3)]
        X, Y, Z = torch.meshgrid(*ax, indexing="ij"); G = Field(X, Y, Z)
        if part.startswith("hand"): d = hand_sdf(G, J, part[-1], s)
        else:
            d = body_sdf(G, J, s, hands=part != "body")
            if s < 1.0: d = torch.maximum(d, body_sdf(G, J, 1.0, hands=True) + 0.010)     # the inner copy stays >= 1 cm inside the shell
        d = d.cpu().numpy()
    else:
        ax = [(lo[i] + voxel * np.arange(n[i])).astype(np.float32) for i in range(3)]
        X, Y, Z = np.meshgrid(*ax, indexing="ij"); G = Field(X, Y, Z)
        d = hand_sdf(G, J, part[-1], s) if part.startswith("hand") else body_sdf(G, J, s, hands=part != "body")
    v, f, _, _ = marching_cubes(d, level=0.0, spacing=(voxel,) * 3)
    v = (v + lo).astype(np.float64)
    import scipy.sparse as sp
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); A = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(v), len(v))).tocsr()
    A = ((A + A.T) > 0).astype(np.float64); Lm = sp.diags(1.0 / np.maximum(np.asarray(A.sum(1)).ravel(), 1)) @ A
    for _ in range(12): v = v + 0.5 * (Lm @ v - v); v = v - 0.53 * (Lm @ v - v)                  # Taubin smoothing: no voxel steps, no shrinking
    v = v.astype(np.float32)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0: f = f[:, ::-1]      # outward normals
    # keep only the largest connected piece (one mesh, nothing floating)
    import scipy.sparse as sp, scipy.sparse.csgraph as cg
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); g = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(v), len(v)))
    nc, lab = cg.connected_components(g, directed=False); keep = lab == np.bincount(lab).argmax()
    fk = f[keep[f[:, 0]]]; remap = -np.ones(len(v), np.int64); remap[keep] = np.arange(keep.sum())
    return v[keep], remap[fk].astype(np.int32), nc

if __name__ == "__main__":
    out, name = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
    J = rest_joints(); B = json.dumps(bones(J)); jj = json.dumps({k: [float(x) for x in v] for k, v in J.items()})
    for part, s, vox, kind in (("shell", 1.0, VOXEL, "full"), ("core", CORE_K, VOXEL, "full"), ("body", 1.0, VOXEL, "body"), ("handL", 1.0, 0.004, "handL"), ("handR", 1.0, 0.004, "handR")):
        t0 = time.time(); v, f, nc = mesh(J, s, vox, kind)
        np.savez_compressed(os.path.join(out, f"{name}_{part}.npz"), verts=v, faces=f, bones=B, joints=jj)
        ext = v.max(0) - v.min(0)
        print(f"{name}_{part}: {len(v)} verts, {len(f)} tris, pieces {nc}, size x{ext[0]:.3f} y{ext[1]:.3f} z{ext[2]:.3f}, {time.time() - t0:.1f}s", flush=True)
