# clip_B hero v3 form: MPFB (CC0) base figure -> faceless glass-mannequin sculpture (soft planes of forehead, nose bridge, cheekbones, jaw;
# no eyes, mouth, ears detail), thinner neck, shoulders wider than the pelvis; MPFB default rig + weights kept (topology unchanged).
# usage: blender -b --python hero_v3_form.py   ->  v3/hero_v3_form.blend (objects HeroV3 + HeroV3.rig), v3/hero_v3_form.json (stats)
import bpy, bmesh, os, json, math
import numpy as np
from mathutils import Vector
bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.targetservice import TargetService
V3 = "/content/drive/MyDrive/renders/clip_B/v3"
for ob in list(bpy.data.objects): bpy.data.objects.remove(ob)
MACRO = {"gender": 0.62, "age": 0.5, "muscle": 0.6, "weight": 0.42, "height": 0.55, "proportions": 1.0, "cupsize": 0.3, "firmness": 0.5,
         "race": {"african": 0.333, "asian": 0.333, "caucasian": 0.334}}
TARGETS = [("measure-neck-circ-decr", 0.6), ("neck-scale-horiz-decr", 0.3), ("measure-shoulder-dist-incr", 0.4), ("torso-vshape-incr", 0.35),
           ("measure-hips-circ-decr", 0.15), ("head-oval", 0.6),
           ("l-ear-flap-decr", 0.3), ("r-ear-flap-decr", 0.3),      # ears simplified, kept
           ("nose-flaring-decr", 1.0), ("nose-nostrils-width-decr", 0.8), ("nose-point-width-decr", 0.4),                    # nostrils soft, the bridge stays
           ("mouth-lowerlip-volume-decr", 1.0), ("mouth-upperlip-volume-decr", 1.0),                                          # lips flatten before the closing
           ("l-cheek-bones-incr", 0.55), ("r-cheek-bones-incr", 0.55), ("eyebrows-trans-forward", 0.5), ("l-eye-push1-in", 0.5), ("r-eye-push1-in", 0.5), ("l-eye-push2-in", 0.4), ("r-eye-push2-in", 0.4), ("chin-bones-incr", 0.3), ("chin-prominent-incr", 0.2)]  # bone structure
bo = HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True, feet_on_ground=True, scale=0.1, macro_detail_dict=MACRO)
bad = []
for nm, w in TARGETS:
    try: TargetService.set_target_value(bo, nm, w)
    except Exception as e: bad.append((nm, str(e)[:60]))
print("TARGETS applied", len(TARGETS) - len(bad), "failed", bad, flush=True)
rig = HumanService.add_builtin_rig(bo, "default", import_weights=True)
TargetService.bake_targets(bo)
me = bo.data; M = bo.matrix_world
co = np.array([M @ v.co for v in me.vertices])
def gidx(name):
    g = bo.vertex_groups.get(name)
    return [v.index for v in me.vertices if g and any(e.group == g.index and e.weight > 0.5 for e in v.groups)]
def centroid(name):
    ix = gidx(name); return co[ix].mean(axis=0) if ix else None
J = {k: centroid("joint-" + k) for k in ("l-eye", "r-eye", "mouth", "neck", "head", "head-2", "jaw")}
print("JOINTS", {k: (None if v is None else [round(x, 3) for x in v]) for k, v in J.items()}, flush=True)
# delete the helper geometry (everything outside the 'body' group); rig weights stay on the remaining vertices
keep = set(gidx("body")); bmh = bmesh.new(); bmh.from_mesh(me); bmh.verts.ensure_lookup_table()
bmesh.ops.delete(bmh, geom=[v for v in bmh.verts if v.index not in keep], context="VERTS")
# close the eye openings (and any other small hole) with faces only: no new vertices, the weights stay valid
bmh.edges.ensure_lookup_table(); bnd = [e for e in bmh.edges if e.is_boundary]
holes = bmesh.ops.holes_fill(bmh, edges=bnd, sides=64); bmesh.ops.triangulate(bmh, faces=holes["faces"])
print("holes filled:", len(holes["faces"]), flush=True)
bmh.to_mesh(me); bmh.free(); me.update()
for mod in [m for m in bo.modifiers if m.type == "MASK"]: bo.modifiers.remove(mod)
co = np.array([M @ v.co for v in me.vertices]); n = len(co)
nb = [[] for _ in range(n)]
for e in me.edges: a, b = e.vertices; nb[a].append(b); nb[b].append(a)
deg = np.array([max(1, len(x)) for x in nb], np.float64)
rows = np.repeat(np.arange(n), [len(x) for x in nb]); cols = np.concatenate([np.array(x, int) for x in nb])
def lap(P):
    acc = np.zeros_like(P); np.add.at(acc, rows, P[cols]); return acc / deg[:, None] - P
def blob(c, r):
    d = np.linalg.norm(co - c, axis=1); x = np.clip(1 - d / r, 0, 1); return x * x * (3 - 2 * x)
eyeL, eyeR = J["l-eye"], J["r-eye"]                                                   # the MPFB mouth joint sits inside the head: take the lips themselves
lip_sel = np.where((np.abs(co[:, 0]) < 0.015) & (co[:, 2] > eyeL[2] - 0.09) & (co[:, 2] < eyeL[2] - 0.045))[0]; mouth = co[lip_sel[np.argmin(co[lip_sel, 1])]] + np.array([0, 0.006, 0.0])
mid = 0.5 * (0.5 * (eyeL + eyeR) + mouth)
cand = np.where((np.linalg.norm(co - mid, axis=1) < 0.06) & (np.abs(co[:, 0]) < 0.02))[0]; nose = co[cand[np.argmin(co[cand, 1])]]
ear = []
for sgn in (1, -1):
    sel = np.where((np.abs(co[:, 2] - eyeL[2]) < 0.04) & (co[:, 1] > eyeL[1] + 0.03) & (co[:, 2] > eyeL[2] - 0.06) & (sgn * co[:, 0] > 0))[0]
    p = co[sel[np.argmax(sgn * co[sel, 0])]]; ear.append(p - np.array([sgn * 0.012, 0, 0]))
W = np.maximum.reduce([0.5 * blob(eyeL, 0.024), 0.5 * blob(eyeR, 0.024), 0.6 * blob(mouth, 0.026)])      # light pre-smoothing only
P = co.copy()
for it in range(20): P += 0.5 * W[:, None] * lap(P)
fin = np.zeros(n)                                                                        # keep fingers and toes crisp in the global pass
for g in bo.vertex_groups:
    if g.name.startswith(("finger", "toe", "metacarpal")):
        for v in me.vertices:
            for e in v.groups:
                if e.group == g.index: fin[v.index] += e.weight
Wg = 1 - np.clip(fin, 0, 1)
for it in range(8):                                                                       # gentle Taubin pass: no bulges, no shrink
    P += 0.5 * Wg[:, None] * lap(P); P += -0.53 * Wg[:, None] * lap(P)
Mi = M.inverted()
for i, v in enumerate(me.vertices): v.co = Mi @ Vector(P[i])
me.update()
for p in me.polygons: p.use_smooth = True
z_top = P[:, 2].max(); z_chin = J["jaw"][2] - 0.012; H_ = z_top - P[:, 2].min()
stats = dict(height=round(float(H_), 3), head=round(float(z_top - z_chin), 3), heads=round(float(H_ / (z_top - z_chin)), 2), verts=n,
             shoulder_w=round(float(np.ptp(P[(np.abs(P[:, 2] - (J["neck"][2] - 0.08)) < 0.02), 0])), 3),
             hip_w=0.0, nose=[round(float(x), 3) for x in nose], lips=[round(float(x), 3) for x in mouth], ears=[[round(float(x), 3) for x in e] for e in ear])
print("STATS", stats, flush=True)
bo.name = "HeroV3"; me.name = "HeroV3"; rig.name = "HeroV3.rig"
json.dump(dict(stats=stats, joints={k: [float(x) for x in v] for k, v in J.items() if v is not None}, macro=MACRO, targets=TARGETS), open(f"{V3}/hero_v3_form.json", "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=f"{V3}/hero_v3_form.blend"); print("FORM_DONE", flush=True)
