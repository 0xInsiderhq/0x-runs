"""v2.2 checks on the real geometry/cameras (Blender projection of the car body bounding box)."""
import bpy, sys, os
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import traj as T
S, ev, F, C = T.build_all()
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)), "stunt.blend"))
sc = bpy.context.scene; body = bpy.data.objects["Body"]
ff = lambda t: T.first_frame_at(ev, t)
f_pass, cut, ftop, fland, fstop = ff(ev["t_pass"]), ev["cut_frame"], ff(ev["t_top"]), ff(ev["t_land"]), ff(ev["t_stop"])
info = {}
for f in range(1, T.FRAMES + 1):
    sc.frame_set(f); cam = sc.camera
    pts = [world_to_camera_view(sc, cam, body.matrix_world @ Vector(c)) for c in body.bound_box]
    ys = [p.y for p in pts]; xs = [p.x for p in pts]
    inside = min(xs) >= 0 and max(xs) <= 1 and min(ys) >= 0 and max(ys) <= 1 and min(p.z for p in pts) > 0
    info[f] = dict(h=max(ys) - min(ys), w=max(xs) - min(xs), lo=min(ys), hi=max(ys), inside=inside, cam=cam.name, lens=cam.data.lens)
def mn(fr):
    f = min(fr, key=lambda f: info[f]["h"]); return f"{info[f]['h'] * 100:.1f}% of frame height @ frame {f} ({info[f]['cam']}, {info[f]['lens']:.0f} mm)"
i1 = info[1]
print(f"frame 1: car {i1['w'] * 100:.0f}% of frame width, {i1['h'] * 100:.0f}% height, lens {i1['lens']:.1f} mm, car spans {i1['lo'] * 100:.0f}-{i1['hi'] * 100:.0f}% of height")
a_rng = [f for f in range(f_pass + 11, cut)]
print("MIN shot A after the pass-by (pass+11 .. cut):", mn(a_rng), "| lens at the cut", f"{info[cut - 1]['lens']:.0f} mm")
print("first frame after the cut:", cut, f"{info[cut]['h'] * 100:.1f}%")
print("MIN loop (cut -> top):", mn(range(cut, ftop)))
print("MIN flight (top -> landing):", mn(range(ftop, fland)))
print("car not fully in frame (cut -> landing):", [f for f in range(cut, fland) if not info[f]["inside"]])
print("car not fully in frame (shot A after pass+11):", [f for f in a_rng if not info[f]["inside"]])
low = [f for f in range(f_pass + 11, T.FRAMES + 1) if info[f]["inside"] and info[f]["lo"] < 0.10]
print("car dips into the bottom 10% (after the pass-by):", low[:30], len(low))
print(f"final push-in: frame {fstop} {info[fstop]['w'] * 100:.0f}% -> frame 360 {info[360]['w'] * 100:.0f}% of frame width ({info[fstop]['lens']:.0f} -> {info[360]['lens']:.0f} mm)")
grow = [info[f]["w"] for f in range(fstop, T.FRAMES + 1)]
print("final: car width never shrinks after the stop:", all(b >= a - 0.004 for a, b in zip(grow, grow[1:])))
bright = [o for o in bpy.data.objects if o.name in ("LoopLED", "FloodHeads", "MarkerDomes", "HangarWindows", "Beacon", "FlightLampHeads")]
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
print("first 2 s: car top edge max", f"{max(info[f]['hi'] for f in range(1, 49)) * 100:.0f}% of frame height")
