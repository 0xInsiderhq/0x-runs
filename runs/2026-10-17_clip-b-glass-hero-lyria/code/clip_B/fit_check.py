"""does the seated hero fit the stunt car? usage: blender -b --python fit_check.py -- MESHDIR MESHNAME [IMGDIR]
poses the hero in the car (rig space, facing +Y = forward), raycasts against the body + glass: roof clearance over the head,
cushion/floor/feet, share of the body outside the car shell (a point is inside when rays in all 6 axis directions hit the car)"""
import bpy, sys, os, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hero as H
A = sys.argv[sys.argv.index("--") + 1:]; MD, MN = A[:2]; IMG = A[2] if len(A) > 2 else None
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "stunt_v2", "stunt.blend"))
sc = bpy.context.scene; sc.frame_set(1)
body, glass = bpy.data.objects["Body"], bpy.data.objects["Glass"]; rig = body.parent; Mi = rig.matrix_world.inverted()
dg = bpy.context.evaluated_depsgraph_get(); V, F = [], []
for ob in (body, glass):
    ev = ob.evaluated_get(dg); me = ev.to_mesh(); M = Mi @ ob.matrix_world; o = len(V)
    V += [M @ v.co for v in me.vertices]; F += [[o + i for i in p.vertices] for p in me.polygons]; ev.to_mesh_clear()
bvh = BVHTree.FromPolygons(V, F)
wv = [Mi @ body.matrix_world @ body.data.vertices[i].co for p in body.data.polygons if p.material_index == 1 for i in p.vertices]
yc = 0.5 * (min(v.y for v in wv) + max(v.y for v in wv)); Y_HIP = yc - 0.16
def floor_at(x, y):                                     # inner floor = first hit going down from 0.5 m
    h = bvh.ray_cast(Vector((x, y, 0.5)), Vector((0, 0, -1)), 2.0); return h[0].z if h[0] else None
print(f"cabin: window y {min(v.y for v in wv):.3f}..{max(v.y for v in wv):.3f}, hip y {Y_HIP:.3f}, inner floor under the hip {floor_at(0, Y_HIP)}, at the feet {floor_at(0, Y_HIP + 0.7)}", flush=True)
coll = bpy.data.collections.new("Fit"); sc.collection.children.link(coll)
clay = bpy.data.materials.new("Clay")
h = H.build_hero(coll, MD, MN, "FitHero", 1.0, clay=clay); arm, shell = h["root"], h["shell"]
arm.parent = rig; arm.rotation_euler = (0, 0, math.pi)
DIRS = [Vector(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
SCALE = 0.97; arm.scale = (SCALE,) * 3
CASES = [("req", None, 0, 0), ("req", 0.15, 0, 0)] + [("fit", 0.135, y, p) for y, p in ((0, 0), (-50, 0), (50, 0), (0, 12), (-45, 10), (45, 10))]
for var, z_c, hy, hpch in CASES:
    arm.location = (0, Y_HIP, 0); H.pose_seated(arm, var, math.radians(hy), math.radians(hpch)); bpy.context.view_layer.update()
    low = H.lowest_z(h) * SCALE; fz = floor_at(0, Y_HIP + 0.4) or 0.14
    if z_c is None: z_c = fz - low                      # feet resting on the inner floor
    arm.location = (0, Y_HIP, z_c); bpy.context.view_layer.update()
    ev = shell.evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh(); M = Mi @ shell.matrix_world
    P = [M @ v.co for v in me.vertices]; ev.to_mesh_clear()
    top = max(P, key=lambda p: p.z); hit = bvh.ray_cast(top + Vector((0, 0, 0.001)), Vector((0, 0, 1)), 2.0)
    roof = None
    for p in sorted(P, key=lambda p: -p.z)[:400]:       # roof clearance over the whole head top
        r = bvh.ray_cast(p, Vector((0, 0, 1)), 2.0)
        if r[0] is not None: roof = min(roof, r[0].z - p.z) if roof is not None else r[0].z - p.z
    S = P[::40]; out = [p for p in S if not all(bvh.ray_cast(p, d, 4.0)[0] is not None for d in DIRS)]
    zs = sorted(p.z for p in out)
    print(f"FIT {var} head yaw {hy} pitch {hpch} cushion {z_c:.3f}: head top z {top.z:.3f} at y {top.y:.3f}, roof clearance {roof if roof is None else round(roof, 3)}; "
          f"lowest z {min(p.z for p in P):.3f} (inner floor {fz:.3f}, ground 0); outside the car shell {len(out)}/{len(S)} = {100 * len(out) / len(S):.1f}%"
          + (f", outside z range {zs[0]:.2f}..{zs[-1]:.2f}" if out else ""), flush=True)
    if IMG and hy == 0 and hpch == 0:                         # x-ray side view: the hero inside the car body
        os.makedirs(IMG, exist_ok=True); sc.render.engine = "BLENDER_WORKBENCH"; shd = sc.display.shading
        shd.light = "STUDIO"; shd.color_type = "MATERIAL"; shd.show_xray = True; shd.xray_alpha = 0.45; shd.show_cavity = False
        clay.diffuse_color = (1.0, 0.55, 0.30, 1)
        keep = {body, glass, shell} | {o for o in bpy.data.objects if o.parent == rig and o.type == "MESH"}
        for o in bpy.data.objects:
            if o.type in ("MESH", "CURVE", "VOLUME"): o.hide_render = o not in keep
        if "FitCam" not in bpy.data.objects:
            cd = bpy.data.cameras.new("FitCam"); cd.type = "ORTHO"; cd.ortho_scale = 4.7; cam = bpy.data.objects.new("FitCam", cd); sc.collection.objects.link(cam)
            cam.parent = rig; cam.location = (-7, 0.1, 0.62); cam.rotation_euler = (math.pi / 2, 0, -math.pi / 2)
        sc.camera = bpy.data.objects["FitCam"]; sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1000, 420, 100
        sc.render.image_settings.file_format = "PNG"; sc.render.filepath = os.path.join(IMG, f"fit_{var}_{z_c:.2f}.png"); sc.render.use_compositing = False
        bpy.ops.render.render(write_still=True); sc.render.engine = "CYCLES"
print("FIT_DONE", flush=True)
