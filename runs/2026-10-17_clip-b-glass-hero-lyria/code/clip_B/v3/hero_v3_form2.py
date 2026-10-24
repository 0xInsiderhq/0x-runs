# clip_B hero v3 form, pass 2 ("blurred marble statue"): the anatomy of the MPFB head stays (brow ridges, nose bridge as a soft ridge,
# cheekbones, jaw, chin, ears in a simplified soft form); only the eyes, the mouth and the nostrils are closed: a morphologically closed copy
# of the head (remesh -> inflate 8 mm -> remesh -> deflate) is intersected with small spheres there and united with the body,
# one seamless voxel remesh, soft local smoothing, MPFB rig weights transferred from the source basemesh.
# usage: blender -b --python hero_v3_form2.py  ->  v3/hero_v3.blend (HeroV3 sculpt bound to HeroV3.rig)
import bpy, bmesh, json, numpy as np
from mathutils import Vector, Matrix
V3 = "/content/drive/MyDrive/renders/clip_B/v3"
bpy.ops.wm.open_mainfile(filepath=f"{V3}/hero_v3_form.blend")
info = json.load(open(f"{V3}/hero_v3_form.json")); J = {k: np.array(v) for k, v in info["joints"].items()}; ST = info["stats"]
src = bpy.data.objects["HeroV3"]; rig = bpy.data.objects["HeroV3.rig"]; sc = bpy.context.scene
for m in src.modifiers: m.show_viewport = m.show_render = m.type != "ARMATURE"
def copy_of(name, ob):
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o); o.matrix_world = ob.matrix_world.copy(); return o
def apply_all(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
def remesh(o, vs):
    m = o.modifiers.new("rm", "REMESH"); m.mode = "VOXEL"; m.voxel_size = vs; m.adaptivity = 0.0; m.use_smooth_shade = True
def inflate(o, d):
    m = o.modifiers.new("dp", "DISPLACE"); m.direction = "NORMAL"; m.mid_level = 0.0; m.strength = d
# ---- morphologically closed head (only used locally) ----
head = copy_of("HeadPiece", src); zc = J["neck"][2] + 0.015
bm = bmesh.new(); bm.from_mesh(head.data); Mw = head.matrix_world
bmesh.ops.delete(bm, geom=[v for v in bm.verts if (Mw @ v.co).z < zc], context="VERTS")
bm.edges.ensure_lookup_table(); bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
bm.to_mesh(head.data); bm.free()
for step in (lambda: remesh(head, 0.0025), lambda: inflate(head, 0.008), lambda: remesh(head, 0.0025), lambda: inflate(head, -0.008), lambda: remesh(head, 0.0025)):
    step(); apply_all(head)
# ---- fill solids: closed head inside small ellipsoids at the eyes, the mouth and the nostrils ----
eyeL = J["l-eye"] + [0, -0.012, -0.002]; eyeR = J["r-eye"] + [0, -0.012, -0.002]; lips = np.array(ST["lips"]) + [0, 0.004, 0.0]
nost = np.array(ST["nose"]) + [0, 0.008, -0.012]
FILL = [("eyeL", eyeL, (0.019, 0.016, 0.013)), ("eyeR", eyeR, (0.019, 0.016, 0.013)), ("mouth", lips, (0.028, 0.02, 0.016)), ("nostrils", nost, (0.016, 0.012, 0.009))]
fills = []
for nm, c, r in FILL:
    sm = bpy.data.meshes.new("fill_" + nm); bs = bmesh.new(); bmesh.ops.create_uvsphere(bs, u_segments=32, v_segments=16, radius=1.0)
    for v in bs.verts: v.co = Vector((v.co.x * r[0], v.co.y * r[1], v.co.z * r[2])) + Vector(c)
    bs.to_mesh(sm); bs.free(); so = bpy.data.objects.new("fill_" + nm, sm); sc.collection.objects.link(so)
    bo_ = so.modifiers.new("ix", "BOOLEAN"); bo_.operation = "INTERSECT"; bo_.object = head; bo_.solver = "EXACT"; apply_all(so)
    fills.append(so); print("fill", nm, len(so.data.vertices), flush=True)
head.hide_render = True
# ---- body (original anatomy) + fills -> one seamless surface ----
body = copy_of("BodyAll", src)
bpy.ops.object.select_all(action="DESELECT"); body.select_set(True)
for so in fills: so.select_set(True)
bpy.context.view_layer.objects.active = body; bpy.ops.object.join()
remesh(body, 0.0035); apply_all(body)
bpy.data.objects.remove(head)
me = body.data; Mw = body.matrix_world; Mi = Mw.inverted(); n = len(me.vertices)
P = np.array([Mw @ v.co for v in me.vertices]); co = P.copy()
nb = [[] for _ in range(n)]
for e in me.edges: a, b = e.vertices; nb[a].append(b); nb[b].append(a)
deg = np.array([max(1, len(x)) for x in nb], np.float64)
rows = np.repeat(np.arange(n), [len(x) for x in nb]); cols = np.concatenate([np.array(x, int) for x in nb])
def lap(Q):
    acc = np.zeros_like(Q); np.add.at(acc, rows, Q[cols]); return acc / deg[:, None] - Q
def blob(c, r):
    d = np.linalg.norm(co - np.array(c), axis=1); x = np.clip(1 - d / r, 0, 1); return x * x * (3 - 2 * x)
W = np.maximum.reduce([0.45 * blob(eyeL, 0.024), 0.45 * blob(eyeR, 0.024), 0.5 * blob(lips, 0.03), 0.35 * blob(nost, 0.016),
                       0.8 * blob(ST["ears"][0], 0.035), 0.8 * blob(ST["ears"][1], 0.035)])
for it in range(14): P += 0.5 * W[:, None] * lap(P)                                     # blend the fills; ears: folds soft, outline kept
headr = np.clip((P[:, 2] - (J["neck"][2] + 0.02)) / 0.03, 0, 1)                        # the head a touch more blurred than the body
hand = ((np.abs(P[:, 0]) > 0.62) & (P[:, 2] < 1.05)) | (P[:, 2] < 0.09)
Wg = np.where(hand, 0.25, 0.8 + 0.2 * headr)
for it in range(6): P += 0.5 * Wg[:, None] * lap(P); P += -0.53 * Wg[:, None] * lap(P)   # Taubin: voxel ripples and small details go, the form stays
for i, v in enumerate(me.vertices): v.co = Mi @ Vector(P[i])
me.update()
for p in me.polygons: p.use_smooth = True
# ---- MPFB rig weights from the source basemesh ----
dt = body.modifiers.new("dt", "DATA_TRANSFER"); dt.object = src; dt.use_vert_data = True; dt.data_types_verts = {"VGROUP_WEIGHTS"}
dt.vert_mapping = "POLYINTERP_NEAREST"; dt.layers_vgroup_select_src = "ALL"; dt.layers_vgroup_select_dst = "NAME"
bpy.context.view_layer.objects.active = body; bpy.ops.object.datalayout_transfer(modifier="dt"); apply_all(body)
keepg = set(b.name for b in rig.data.bones)
for g in list(body.vertex_groups):
    if g.name not in keepg: body.vertex_groups.remove(g)
am = body.modifiers.new("Armature", "ARMATURE"); am.object = rig; am.use_deform_preserve_volume = True; body.parent = rig; body.matrix_parent_inverse = rig.matrix_world.inverted()
bpy.data.objects.remove(src); body.name = "HeroV3"; me.name = "HeroV3"
print("STATS2", dict(verts=n, polys=len(me.polygons), groups=len(body.vertex_groups)), flush=True)
bpy.ops.wm.save_as_mainfile(filepath=f"{V3}/hero_v3.blend"); print("FORM2_DONE", flush=True)
