"""Build the car alone in a studio and render 4 check views (3/4 front, side, 3/4 rear, top)."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh, math
from mathutils import Vector
import common as C, materials as M, car as CAR, car_body as CB

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SAMPLES = int(args[0]) if args else 128
RES = (int(args[1]), int(args[2])) if len(args) > 2 else (1600, 1000)
OUT = os.path.join(C.STUNT, "views"); os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C.setup_cycles(sc, SAMPLES)
sc.render.resolution_x, sc.render.resolution_y = RES
t0 = time.time()
car = CAR.build_car(sc.collection)
print(f"CAR_BUILD_SEC={time.time() - t0:.1f}", flush=True)
# studio: dark world, semi-gloss floor, strip softboxes and a row of small lights to read the clear coat
w = bpy.data.worlds.new("Studio"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.013, 0.015, 1)
bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=30)
m, nt = M.new("StudioFloor")
if nt:
    n = M.noise(nt, M.coords(nt), 2.0, 6.0, 0.6)
    col = M.mix(nt, n.outputs["Fac"], (0.035, 0.035, 0.037, 1), (0.06, 0.06, 0.062, 1))
    M.out(nt, M.principled(nt, Base_Color=col, Roughness=0.32).outputs[0])
CB_floor = bpy.data.meshes.new("Floor"); bm.to_mesh(CB_floor); bm.free(); CB_floor.materials.append(m)
fl = bpy.data.objects.new("Floor", CB_floor); sc.collection.objects.link(fl)
strip = M.emission("Softbox", (1.0, 0.98, 0.95), 9.0)
bulb = M.emission("Bulb", (1.0, 0.75, 0.45), 60.0)
bm = bmesh.new()
for x, z, rx in ((-1.4, 3.4, 18), (0.0, 3.6, 0), (1.4, 3.4, -18)):
    v = CB.box(bm, (x, 0, z), (0.28, 5.5, 0.02))
    for vv in v: vv.co = Vector((x + (vv.co.x - x) * math.cos(math.radians(rx)), vv.co.y, z + (vv.co.x - x) * math.sin(math.radians(rx)) + (vv.co.z - z)))
me = bpy.data.meshes.new("Softboxes"); bm.to_mesh(me); bm.free(); me.materials.append(strip)
sb = bpy.data.objects.new("Softboxes", me); sc.collection.objects.link(sb); sb.visible_camera = False
bm = bmesh.new()
for k in range(14):
    for (cx, cy) in ((-7.5, -6 + k), (7.5, -6 + k)):
        s = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.05)
        for v in s["verts"]: v.co += Vector((cx, cy, 1.4))
me = bpy.data.meshes.new("Bulbs"); bm.to_mesh(me); bm.free(); me.materials.append(bulb)
bo = bpy.data.objects.new("Bulbs", me); sc.collection.objects.link(bo)
C.area(sc, "Key", (-3.5, 3.0, 4.5), (0, 0, 0.5), 700, 3.0)
C.area(sc, "Rim", (3.5, -4.5, 2.5), (0, 0, 0.6), 600, 2.5, (0.85, 0.9, 1.0))
C.area(sc, "Fill", (5.0, 3.5, 1.5), (0, 0, 0.5), 200, 3.0)
C.area(sc, "Low", (0.0, 6.0, 0.4), (0, 0, 0.3), 150, 2.0)
cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam
cd.sensor_width = 36; cd.clip_end = 200
VIEWS = {
    "1_front34": ((-4.6, 5.6, 1.45), (0, 0.15, 0.5), 50),
    "2_side":    ((-8.6, 0.0, 0.70), (0, 0.0, 0.55), 50),
    "3_rear34":  ((4.8, -5.6, 1.55), (0, -0.2, 0.5), 50),
    "4_top":     ((0.0, 0.0, 11.0), None, 50),
}
for name, (loc, tgt, lens) in VIEWS.items():
    cam.location = loc; cd.lens = lens
    if tgt is None:
        cam.rotation_mode = "XYZ"; cam.rotation_euler = (0.0, 0.0, math.radians(90))
    else:
        C.look_at(cam, tgt)
    sc.render.filepath = os.path.join(OUT, name + ".png")
    t1 = time.time(); bpy.ops.render.render(write_still=True)
    print(f"VIEW {name} {time.time() - t1:.1f}s", flush=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(C.STUNT, "car_views.blend"))
print("VIEWS_DONE", flush=True)
