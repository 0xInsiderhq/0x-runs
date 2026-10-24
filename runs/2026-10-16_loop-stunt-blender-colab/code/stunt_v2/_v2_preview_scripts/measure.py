"""Projected bounding box of the car body in the active camera, loop entry -> landing (real geometry, real cameras)."""
import bpy, sys, os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traj as T
S, ev, F, C = T.build_all()
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "stunt.blend"))
sc = bpy.context.scene; body = bpy.data.objects["Body"]
f0, f1, ftop = int(round(ev["t_loop"] * T.FPS)) + 1, int(round(ev["t_land"] * T.FPS)) + 1, int(round(ev["t_top"] * T.FPS)) + 1
rows = []
for f in range(f0, f1 + 1):
    sc.frame_set(f); cam = sc.camera
    pts = [world_to_camera_view(sc, cam, body.matrix_world @ Vector(c)) for c in body.bound_box]
    ys = [p.y for p in pts]; xs = [p.x for p in pts]
    inside = min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1 and min(p.z for p in pts) > 0
    rows.append((f, max(ys) - min(ys), inside, cam.name, cam.data.lens))
mn = lambda rs: min(rs, key=lambda r: r[1])
for label, rs in (("loop entry -> landing", rows), ("loop (entry -> top)", [r for r in rows if r[0] < ftop]), ("flight (top -> landing)", [r for r in rows if r[0] >= ftop])):
    r = mn(rs); print(f"MIN {label}: {r[1] * 100:.1f}% of frame height @ frame {r[0]} ({r[3]}, {r[4]:.0f} mm)")
print("cut frame:", ev["cut_frame"], "| frames with the car not fully in frame:", [r[0] for r in rows if not r[2]])
print("per frame:", " ".join(f"{r[0]}:{r[1] * 100:.0f}" for r in rows[::4]))
