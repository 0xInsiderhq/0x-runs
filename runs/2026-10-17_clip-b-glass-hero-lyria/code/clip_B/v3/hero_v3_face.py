# clip_B hero v3 face, "sleeping statue" (ref. Brancusi's Sleeping Muse): the first MPFB v3 head as generated (no smoothing filter),
# eyes closed by the MPFB eyelid bones (the lids slide over the eyeball dome and meet in one soft line), lips kept but sculpted down to a
# low relief with plain corners, nose and ears native MPFB with only the nostrils and the small ear folds softened.
# Every change is a soft-falloff sculpt of the surface itself: no extra objects, no booleans, no flat facets.
# usage: blender -b --python hero_v3_face.py  ->  v3/hero_v3_face.blend (HeroV3 + HeroV3.rig), v3/hero_v3_face.json
import bpy, bmesh, json, math, numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree
bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.targetservice import TargetService
V3 = "/content/drive/MyDrive/renders/clip_B/v3"
src = open(f"{V3}/hero_v3_form.py").read()
exec(src[src.find("MACRO"):src.find("bo = HumanService")])                      # the same macro + targets as the first v3 head
TARGETS = [(n, w) for n, w in TARGETS if "eye-push" not in n]                    # the eyeball volume has to read under the closed lids
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
bo = HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True, feet_on_ground=True, scale=0.1, macro_detail_dict=MACRO)
bad = []
for nm, w in TARGETS:
    try: TargetService.set_target_value(bo, nm, w)
    except Exception as e: bad.append((nm, str(e)[:60]))
print("TARGETS applied", len(TARGETS) - len(bad), "failed", bad, flush=True)
rig = HumanService.add_builtin_rig(bo, "default", import_weights=True)
TargetService.bake_targets(bo)
me = bo.data; M = bo.matrix_world; Mi = M.inverted(); R3 = M.to_3x3()
def gmask(name, thr=0.5):
    g = bo.vertex_groups.get(name)
    return set(v.index for v in me.vertices if g and any(e.group == g.index and e.weight > thr for e in v.groups))
keep = gmask("body"); bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keep], context="VERTS"); bm.to_mesh(me); bm.free(); me.update()
for mod in [m for m in bo.modifiers if m.type == "MASK"]: bo.modifiers.remove(mod)
EC0 = [rig.matrix_world @ b.head_local for b in rig.data.bones if b.name in ("eye.L", "eye.R")]
co = np.array([M @ v.co for v in me.vertices])
def pick(cond, key):
    ix = np.where(cond)[0]; return co[ix[np.argmin(key(co[ix]))]]
def landmarks():
    lip = pick((np.abs(co[:, 0]) < 0.004) & (co[:, 2] > 1.525) & (co[:, 2] < 1.565) & (co[:, 1] < -0.10), lambda q: q[:, 1])
    tip = pick((np.abs(co[:, 0]) < 0.004) & (co[:, 2] > 1.555) & (co[:, 2] < 1.60) & (co[:, 1] < -0.10), lambda q: q[:, 1])
    ears = []
    for sg in (1, -1):
        sel = (np.abs(co[:, 2] - EC0[0][2]) < 0.04) & (co[:, 1] > EC0[0][1] + 0.03) & (sg * co[:, 0] > 0) & (co[:, 2] > 1.5)
        p = pick(sel, lambda q: -sg * q[:, 0]); ears.append(p - np.array([sg * 0.007, 0, 0]))
    return lip, tip, ears
lip, tip, ears = landmarks()
# the inner pockets of the MPFB head (eye sockets, the mouth bag, nostril and ear-canal pits) go: faces looking at a pocket centre;
# the eye and lip margins become open edges that are sewn below, the pits are closed and softened (one clean shell under glass)
V_ = lambda a_: Vector([float(x) for x in a_])
POCKETS = [("eye", c, 0.022) for c in EC0] + [("mouth", V_(lip + [0, 0.030, -0.003]), 0.040)] + \
          [("nostril", V_(tip + [sg * 0.007, 0.014, -0.006]), 0.013) for sg in (1, -1)] + [("ear", V_(e + [-np.sign(e[0]) * 0.012, 0.004, -0.007]), 0.013) for e in ears]
bm = bmesh.new(); bm.from_mesh(me); kill = []; kc = {}
for f in bm.faces:
    cc = M @ f.calc_center_median(); nn = (R3 @ f.normal).normalized()
    for nm_, c, r in POCKETS:
        d = cc - c
        if d.length < r and nn.dot(d.normalized()) < -0.2: kill.append(f); kc[nm_] = kc.get(nm_, 0) + 1; break
bmesh.ops.delete(bm, geom=kill, context="FACES"); bm.to_mesh(me); bm.free(); me.update(); print("pocket faces removed", kc, flush=True)
n = len(me.vertices); co = np.array([M @ v.co for v in me.vertices])
def weights(name):
    g = bo.vertex_groups.get(name); w = np.zeros(n)
    if g is None: return w
    for v in me.vertices:
        for e in v.groups:
            if e.group == g.index: w[v.index] = e.weight
    return w
def boundary_loops():
    adj = {}; bm = bmesh.new(); bm.from_mesh(me)
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts[0].index, e.verts[1].index; adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    bm.free(); loops, seen = [], set()
    for s in adj:
        if s in seen: continue
        st, comp = [s], []
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x); comp.append(x); st += adj[x]
        loops.append(comp)
    return loops
loops = boundary_loops()
print("BOUNDARY loops", [(len(l), [round(float(x), 3) for x in co[l].mean(0)]) for l in loops], flush=True)
B = {b.name: b for b in rig.data.bones}; RW = rig.matrix_world
stats = {}
def rot_x(P, c, a):
    # rotate points about the axis through c along world X; a > 0 lifts the front (-y) upward
    y = -(P[:, 1] - c[1]); z = P[:, 2] - c[2]; ca, sa = np.cos(a), np.sin(a)
    Q = P.copy(); Q[:, 1] = c[1] - (y * ca - z * sa); Q[:, 2] = c[2] + (y * sa + z * ca); return Q
def zip_rows(U, D):
    # two margin rows meet halfway (each vertex to the midpoint with its nearest on the other row); returns the gaps before
    def tree(ix):
        t = KDTree(len(ix))
        for k, i in enumerate(ix): t.insert(co[i], k)
        t.balance(); return t
    kU, kD = tree(U), tree(D); gaps = [kD.find(co[i])[2] for i in U]
    tgt_ = {i: 0.5 * (co[i] + co[D[kD.find(co[i])[1]]]) for i in U}
    tgt_.update({j: 0.5 * (co[j] + co[U[kU.find(co[j])[1]]]) for j in D})
    for i, p in tgt_.items(): co[i] = p
    return gaps
seam = []
for side in ("L", "R"):
    c = np.array(RW @ B["eye." + side].head_local); wu, wl = weights("orbicularis03." + side), weights("orbicularis04." + side)
    lp = sorted([l for l in loops if np.linalg.norm(co[l].mean(0) - c) < 0.035], key=len, reverse=True)
    if not lp: print("EYE", side, "no boundary loop near", c, flush=True); continue
    L = np.array(lp[0]); phi = np.arctan2(co[L, 2] - c[2], -(co[L, 1] - c[1])); mid = np.abs(co[L, 0] - c[0]) < 0.007
    up = L[(wu[L] > wl[L]) & mid]; lo = L[(wl[L] >= wu[L]) & mid]
    pu = float(np.arctan2(co[up, 2] - c[2], -(co[up, 1] - c[1])).mean()); pl = float(np.arctan2(co[lo, 2] - c[2], -(co[lo, 1] - c[1])).mean())
    tgt = pl + 0.25 * (pu - pl); du = (tgt - pu) / max(0.3, float(wu[up].mean())); dl = (tgt - pl) / max(0.3, float(wl[lo].mean()))
    for w, d in ((wu, du), (wl, dl)):                                          # each vertex turns by weight x angle (no chord shrink)
        sel = w > 1e-4; co[sel] = rot_x(co[sel], c, w[sel] * d)
    gaps = zip_rows(L[wu[L] > wl[L]], L[wl[L] >= wu[L]])
    stats["eye_" + side] = dict(open_deg=round(math.degrees(pu - pl), 1), upper_turn=round(math.degrees(du), 1), lower_turn=round(math.degrees(dl), 1),
                                gap_mm_max=round(1000 * max(gaps), 2), gap_mm_mean=round(1000 * float(np.mean(gaps)), 2), loop=len(L))
    seam += list(L)
mc = lip + np.array([0, 0.010, -0.002]); lpm = sorted([l for l in loops if np.linalg.norm(co[l].mean(0) - mc) < 0.03], key=len, reverse=True)
if lpm:                                                                         # the closed mouth: the lip margins sewn into one line
    L = np.array(lpm[0]); zmid = np.array([co[L[np.abs(co[L, 0] - co[i, 0]) < 0.004], 2].mean() for i in L])
    gaps = zip_rows(L[co[L, 2] > zmid], L[co[L, 2] <= zmid]); seam += list(L)
    stats["mouth"] = dict(gap_mm_max=round(1000 * max(gaps), 2), gap_mm_mean=round(1000 * float(np.mean(gaps)), 2), loop=len(L))
print("SEAMS", stats, flush=True)
for i, v in enumerate(me.vertices): v.co = Mi @ Vector(co[i])
bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
sv = [bm.verts[i] for i in seam]; nv0 = len(bm.verts); seam_pos = co[seam].copy() if seam else np.zeros((1, 3)) + 9.0
bmesh.ops.remove_doubles(bm, verts=sv, dist=0.0006)                             # sew the met margins
bm.edges.ensure_lookup_table()
hf = bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0); bmesh.ops.triangulate(bm, faces=hf["faces"])
bm.to_mesh(me); bm.free(); me.update(); print("sewn", nv0 - len(me.vertices), "verts, residual holes filled", len(hf["faces"]), flush=True)
n = len(me.vertices); co = np.array([M @ v.co for v in me.vertices])
# ---- soft-falloff sculpt ----
nb = [[] for _ in range(n)]
for e in me.edges: a, b = e.vertices; nb[a].append(b); nb[b].append(a)
deg = np.array([max(1, len(x)) for x in nb], float); rows = np.repeat(np.arange(n), [len(x) for x in nb]); cols = np.concatenate([np.array(x, int) for x in nb])
def lap(Q):
    acc = np.zeros_like(Q); np.add.at(acc, rows, Q[cols]); return acc / deg[:, None] - Q
def relaxed(P, it, taubin=True):
    Q = P.copy()
    for _ in range(it):
        Q += 0.5 * lap(Q)
        if taubin: Q += -0.53 * lap(Q)
    return Q
def blob(c, r):
    d = np.linalg.norm((co - np.array(c)) / np.array(r), axis=1); x = np.clip(1 - d, 0, 1); return x * x * (3 - 2 * x)
nrm = np.array([R3 @ v.normal for v in me.vertices]); nrm /= np.linalg.norm(nrm, axis=1)[:, None] + 1e-9
front = np.clip((-nrm[:, 1] - 0.15) / 0.4, 0, 1)                                 # forward-facing skin only (not the mouth bag behind)
lip, tip, ears = landmarks(); ec = np.array([RW @ B["eye." + s].head_local for s in ("L", "R")])
stats.update(lip=[round(float(x), 4) for x in lip], nose_tip=[round(float(x), 4) for x in tip], ears=[[round(float(x), 4) for x in e] for e in ears])
base_lip, base_mid, base_fine = relaxed(co, 30, taubin=False), relaxed(co, 10), relaxed(co, 5)
W = {}
# flatten sculpt of the mouth: a smooth reference surface y = f(x, z) is fitted to the skin ring around the lips (philtrum, cheeks at the
# corners, chin), the depth of the lips is pulled 75 % of the way to it with a soft falloff: low relief, the crease filled to one soft line
rr_ = np.hypot(co[:, 0] / 1.15, co[:, 2] - lip[2])
ring = (rr_ > 0.027) & (rr_ < 0.043) & (co[:, 1] < lip[1] + 0.03) & (nrm[:, 1] < -0.4)
A_ = lambda q: np.c_[np.ones(len(q)), q[:, 0], q[:, 2] - lip[2], q[:, 0] ** 2, (q[:, 2] - lip[2]) ** 2, q[:, 0] * (q[:, 2] - lip[2])]
cf = np.linalg.lstsq(A_(co[ring]), co[ring, 1], rcond=None)[0]; fy = A_(co) @ cf
base_mouth = co.copy(); base_mouth[:, 1] = fy
Wm = blob(lip + [0, 0.006, -0.001], (0.034, 0.019, 0.023)) * (co[:, 1] < fy + 0.008)
W["lips"] = 0.75 * Wm
stats["mouth_ref"] = dict(ring=int(ring.sum()), lip_out_mm=round(1000 * float(fy[np.argmin(np.linalg.norm(co - lip, axis=1))] - lip[1]), 2))
W["corners"] = 0.95 * np.maximum(blob(lip + [0.024, 0.012, 0.0], (0.011, 0.012, 0.011)), blob(lip + [-0.024, 0.012, 0.0], (0.011, 0.012, 0.011)))
W["nostrils"] = 0.9 * np.maximum(blob(tip + [0.009, 0.009, -0.010], (0.013, 0.015, 0.011)), blob(tip + [-0.009, 0.009, -0.010], (0.013, 0.015, 0.011)))
W["ears"] = 0.6 * np.maximum(blob(ears[0], (0.013, 0.024, 0.032)), blob(ears[1], (0.013, 0.024, 0.032)))
kd = KDTree(len(seam_pos))
for k, p_ in enumerate(seam_pos): kd.insert(p_, k)
kd.balance(); dseam = np.array([kd.find(p)[2] if (np.min(np.linalg.norm(ec - p, axis=1)) < 0.04 or np.linalg.norm(lip - p) < 0.045) else 1.0 for p in co])   # lid and mouth lines
W["lid_line"] = 0.55 * np.clip(1 - dseam / 0.0035, 0, 1) ** 2
W["lid_fold"] = 0.3 * np.maximum(*[blob(e + [0, -0.010, 0.007], (0.018, 0.011, 0.009)) for e in ec])
new = co.copy()
for k, base in (("lips", base_mouth), ("corners", base_mouth), ("nostrils", base_lip), ("ears", base_mid), ("lid_line", base_fine), ("lid_fold", base_mid)):
    new += np.minimum(W[k], 1.0)[:, None] * (base - co)
    stats["moved_mm_" + k] = round(1000 * float(np.max(np.linalg.norm(np.minimum(W[k], 1.0)[:, None] * (base - co), axis=1))), 2)
co = new
for i, v in enumerate(me.vertices): v.co = Mi @ Vector(co[i])
me.update()
for p in me.polygons: p.use_smooth = True
zt = co[:, 2].max(); chin = pick((np.abs(co[:, 0]) < 0.01) & (co[:, 1] < -0.08) & (co[:, 2] < lip[2]) & (co[:, 2] > lip[2] - 0.08), lambda q: q[:, 2])
stats.update(height=round(float(zt - co[:, 2].min()), 3), head=round(float(zt - chin[2]), 3), heads=round(float((zt - co[:, 2].min()) / (zt - chin[2])), 2), verts=n)
print("STATS", stats, flush=True)
bo.name = "HeroV3"; me.name = "HeroV3"; rig.name = "HeroV3.rig"
json.dump(dict(stats=stats, macro=MACRO, targets=TARGETS), open(f"{V3}/hero_v3_face.json", "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=f"{V3}/hero_v3_face.blend"); print("FACE_DONE", flush=True)
