"""v2.1 checks on real geometry/cameras: car size in frame, car never in the bottom 10%, bright objects out of the top 20% in the first 2 s."""
import bpy, sys, os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traj as T
S, ev, F, C = T.build_all()
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "stunt.blend"))
sc = bpy.context.scene; body = bpy.data.objects["Body"]
ff = lambda t: T.first_frame_at(ev, t)
f0, ftop, f1 = ff(ev["t_loop"]), ff(ev["t_top"]), ff(ev["t_land"])
rows, low = [], []
for f in range(1, T.FRAMES + 1):
    sc.frame_set(f); cam = sc.camera
    pts = [world_to_camera_view(sc, cam, body.matrix_world @ Vector(c)) for c in body.bound_box]
    ys = [p.y for p in pts]; xs = [p.x for p in pts]
    inside = min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1 and min(p.z for p in pts) > 0
    if f0 <= f <= f1: rows.append((f, max(ys) - min(ys), inside, cam.name, cam.data.lens))
    if f > ev["cut_frame"] and min(ys) < 0.10 and max(ys) > 0.0: low.append(f)
mn = lambda rs: min(rs, key=lambda r: r[1])
for label, rs in (("loop entry -> landing", rows), ("loop (cut -> top)", [r for r in rows if r[0] < ftop]), ("flight (top -> landing)", [r for r in rows if r[0] >= ftop])):
    r = mn(rs); print(f"MIN {label}: {r[1] * 100:.1f}% of frame height @ frame {r[0]} ({r[3]}, {r[4]:.0f} mm)")
print("first frame after the cut:", ev["cut_frame"], f"{[r for r in rows if r[0] == ev['cut_frame']][0][1] * 100:.1f}%" if any(r[0] == ev["cut_frame"] for r in rows) else "")
print("car not fully in frame (entry->landing):", [r[0] for r in rows if not r[2]])
print("car dips into the bottom 10% (shot B):", low[:20], len(low))
bright = [o for o in bpy.data.objects if o.name in ("LoopLED", "FloodHeads", "MarkerDomes", "HangarWindows", "Beacon")]
worst = 0.0; who = None; viol = set()
for f in range(1, 49):
    sc.frame_set(f); cam = sc.camera; dg = bpy.context.evaluated_depsgraph_get()
    for o in bright:
        me = o.evaluated_get(dg).data
        for i in range(0, len(me.vertices), 7):
            p = world_to_camera_view(sc, cam, o.matrix_world @ me.vertices[i].co)
            if p.z > 0 and 0 <= p.x <= 1 and p.y > 0.8: viol.add(f)
            if p.z > 0 and 0 <= p.x <= 1 and p.y > worst: worst = p.y; who = (f, o.name)
print("first 2 s, frames with bright objects above 80%:", sorted(viol))
print(f"first 2 s: highest bright object at {worst * 100:.0f}% of frame height", who if worst else "")
