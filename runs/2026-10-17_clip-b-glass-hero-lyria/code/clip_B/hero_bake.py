"""bake the final hero meshes ONCE: body remeshed at 8 mm + hands remeshed at 4 mm (so the thumb reads), boolean union,
one smoothing pass, every modifier applied. usage: blender -b --python hero_bake.py -- MESHDIR
reads rest_body / rest_handL / rest_handR / rest_core .npz (hero_shape.py), writes final_shell.npz, final_core.npz"""
import bpy, sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hero as H
MD = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
def obj(name, part):
    me, B = H.load_mesh(os.path.join(MD, f"rest_{part}.npz"), name); ob = bpy.data.objects.new(name, me); sc.collection.objects.link(ob); return ob, B
def bake(ob):
    dg = bpy.context.evaluated_depsgraph_get(); me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear(); old = ob.data; ob.data = me; bpy.data.meshes.remove(old); return ob
def remesh(ob, vox):
    m = ob.modifiers.new("remesh", "REMESH"); m.mode = "VOXEL"; m.voxel_size = vox; m.adaptivity = 0.0; m.use_smooth_shade = True; return bake(ob)
def smooth(ob, B=None):
    """the one smoothing pass: light volume-preserving Laplacian everywhere + stronger smoothing on the wrist seams (body/hand union)"""
    m = ob.modifiers.new("smooth", "LAPLACIANSMOOTH"); m.lambda_factor = 0.5; m.iterations = 1; m.use_volume_preserve = True; m.use_normalized = True
    if B:
        from mathutils import Vector
        vg = ob.vertex_groups.new(name="seam"); bones = {b["name"]: b for b in B}
        for s in "LR":
            fa = bones["forearm." + s]; w = Vector(fa["tail"]); ax = (w - Vector(fa["head"])).normalized()
            for v in ob.data.vertices:
                t = (v.co - w).dot(ax)
                if -0.075 < t < 0.012 and ((v.co - w) - ax * t).length < 0.05:
                    vg.add([v.index], max(0.0, 1.0 - abs(t + 0.03) / 0.045), "REPLACE")
        sm = ob.modifiers.new("seam", "SMOOTH"); sm.factor = 0.8; sm.iterations = 10; sm.vertex_group = "seam"
    bake(ob); ob.vertex_groups.clear(); return ob
def save(ob, path, B):
    me = ob.data; v = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", v)
    lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_start", ls); lt = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_total", lt)
    np.savez_compressed(path, verts=v.reshape(-1, 3), loops=lv, loop_start=ls, loop_total=lt, bones=json.dumps(B))
def islands(me):
    import collections
    par = list(range(len(me.vertices)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for e in me.edges:
        a, b = f(e.vertices[0]), f(e.vertices[1])
        if a != b: par[a] = b
    return len({f(i) for i in range(len(me.vertices))})
t0 = time.time()
body, B = obj("Body", "body"); remesh(body, 0.008); nb = len(body.data.polygons)
hands = []
for s in "LR":
    h, _ = obj("Hand" + s, "hand" + s); remesh(h, 0.004); hands.append(h)
for h in hands:
    b = body.modifiers.new("union_" + h.name, "BOOLEAN"); b.operation = "UNION"; b.solver = "EXACT"; b.object = h
bake(body); smooth(body, B)
for h in hands: bpy.data.objects.remove(h)
save(body, os.path.join(MD, "final_shell.npz"), B)
core, _ = obj("Core", "core"); remesh(core, 0.008); smooth(core); save(core, os.path.join(MD, "final_core.npz"), B)
print(f"BAKE shell {len(body.data.polygons)} polys (body alone {nb}), {len(body.data.vertices)} verts, islands {islands(body.data)}; "
      f"core {len(core.data.polygons)} polys, islands {islands(core.data)}; {time.time() - t0:.1f}s", flush=True)
