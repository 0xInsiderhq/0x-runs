# clip_B hero v3: signed distance grid of the MPFB head with closed eye slits / mouth / nostrils (8 mm morphological closing),
# the base for the planar (Asaro-like) head. -> v3/head_anat_sdf.npz (grid, origin, step)
import bpy, bmesh, json, numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
V3 = "/content/drive/MyDrive/renders/clip_B/v3"
bpy.ops.wm.open_mainfile(filepath=f"{V3}/hero_v3_form.blend")
info = json.load(open(f"{V3}/hero_v3_form.json")); J = {k: np.array(v) for k, v in info["joints"].items()}
src = bpy.data.objects["HeroV3"]; sc = bpy.context.scene
for m in src.modifiers: m.show_viewport = m.show_render = m.type != "ARMATURE"
me = bpy.data.meshes.new_from_object(src.evaluated_get(bpy.context.evaluated_depsgraph_get()))
head = bpy.data.objects.new("HeadPiece", me); sc.collection.objects.link(head); head.matrix_world = src.matrix_world.copy()
zc = J["neck"][2] - 0.03
bm = bmesh.new(); bm.from_mesh(head.data); Mw = head.matrix_world
bmesh.ops.delete(bm, geom=[v for v in bm.verts if (Mw @ v.co).z < zc], context="VERTS")
bm.edges.ensure_lookup_table(); bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0); bm.to_mesh(head.data); bm.free()
def apply_all(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
for kind, val in (("rm", 0.0025), ("dp", 0.008), ("rm", 0.0025), ("dp", -0.008), ("rm", 0.0025)):
    if kind == "rm": m = head.modifiers.new("rm", "REMESH"); m.mode = "VOXEL"; m.voxel_size = val; m.adaptivity = 0.0
    else: m = head.modifiers.new("dp", "DISPLACE"); m.direction = "NORMAL"; m.mid_level = 0.0; m.strength = val
    apply_all(head)
bmh = bmesh.new(); bmh.from_mesh(head.data); bmh.transform(head.matrix_world); bvh = BVHTree.FromBMesh(bmh)
h = 0.00125; o = np.array([-0.095, -0.20, zc + 0.005]); n = np.array([152, 224, int((1.735 - o[2]) / h)])
G = np.zeros(n, np.float32)
for i in range(n[0]):
    x = o[0] + i * h
    for j in range(n[1]):
        y = o[1] + j * h
        for k in range(n[2]):
            p = Vector((x, y, o[2] + k * h)); loc, nor, idx, dist = bvh.find_nearest(p)
            G[i, j, k] = dist if (p - loc).dot(nor) > 0 else -dist
    if i % 30 == 0: print("row", i, flush=True)
np.savez_compressed(f"{V3}/head_anat_sdf.npz", G=G, o=o, h=h); print("SDF_DONE", G.shape, float(G.min()), float(G.max()), flush=True)
