"""form check for hero v2: workbench clay views + body measurements. usage: blender -b --python hero_form.py -- OUTDIR MESHDIR"""
import bpy, sys, os, math
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hero as H
OUT, MD = sys.argv[sys.argv.index("--") + 1:][:2]; os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.single_color = (0.78, 0.78, 0.8); sh.show_cavity = True
w = bpy.data.worlds.new("W"); w.color = (0.12, 0.12, 0.13); sc.world = w
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 360, 640, 100
coll = bpy.data.collections.new("H"); sc.collection.children.link(coll)
a = H.build_hero(coll, MD, "form_stand", "Stand", 1.0)
b = H.build_hero(coll, MD, "form_seat", "Seat", 1.0); b["root"].location = (1.2, 0, 0.45)
for h in (a, b):
    h["parts"].hide_render = True; h["core"].hide_render = True
dg = bpy.context.evaluated_depsgraph_get()
me = a["shell"].evaluated_get(dg).to_mesh(); P = [v.co.copy() for v in me.vertices]
print("STAND height %.3f  verts %d" % (max(p.z for p in P), len(P)))
for nm, z in (("shoulder(deltoid)", 1.41), ("chest", 1.30), ("waist", 1.10), ("hips", 0.93), ("thigh", 0.75), ("knee", 0.50), ("calf", 0.36), ("neck", 1.51), ("head", 1.68)):
    band = [p for p in P if abs(p.z - z) < 0.006]
    if band: print("  %-18s z=%.2f  width %.3f  depth %.3f" % (nm, z, max(p.x for p in band) - min(p.x for p in band), max(p.y for p in band) - min(p.y for p in band)))
def cam(name, loc, aim, ortho=None, lens=50):
    cd = bpy.data.cameras.new(name)
    if ortho: cd.type = "ORTHO"; cd.ortho_scale = ortho
    else: cd.lens = lens
    ob = bpy.data.objects.new(name, cd); sc.collection.objects.link(ob); ob.location = loc
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y"); return ob
views = {"front": cam("front", (0, -6, 0.95), (0, 0, 0.95), 2.0), "side": cam("side", (6, 0, 0.95), (0, 0, 0.95), 2.0),
         "q34": cam("q34", (2.6, -3.4, 1.3), (0, 0, 0.95), lens=50), "back34": cam("back34", (-2.4, 3.6, 1.3), (0, 0, 0.95), lens=50),
         "seat": cam("seat", (1.2 + 2.6, -2.2, 1.0), (1.2, -0.15, 0.85), lens=50)}
for n, c in views.items():
    for h in (a, b): h["shell"].hide_render = (n == "seat") == (h is a)
    sc.camera = c; sc.render.filepath = os.path.join(OUT, n + ".png"); bpy.ops.render.render(write_still=True)
print("FORM_DONE", flush=True)
