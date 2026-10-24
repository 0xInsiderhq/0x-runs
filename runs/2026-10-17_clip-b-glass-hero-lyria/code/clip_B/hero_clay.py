"""clay sheet of the hero: one mesh posed by the armature. usage: blender -b --python hero_clay.py -- OUTDIR MESHDIR MESHNAME
renders: standing front / profile / 3-4 and seated (as asked, 'req') + seated (car fit, 'fit') 3-4 and profile, prints measurements"""
import bpy, sys, os, math
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hero as H
OUT, MD, MN = sys.argv[sys.argv.index("--") + 1:][:3]; os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading; sh.light = "STUDIO"; sh.color_type = "MATERIAL"; sh.show_cavity = False; sh.show_specular_highlight = True
w = bpy.data.worlds.new("W"); w.color = (0.10, 0.10, 0.11); sc.world = w
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 540, 960, 100
coll = bpy.data.collections.new("H"); sc.collection.children.link(coll)
def mat(n, c):
    m = bpy.data.materials.new(n); m.diffuse_color = (*c, 1); return m
clay, seat_m, floor_m = mat("Clay", (0.80, 0.76, 0.70)), mat("Seat", (0.22, 0.22, 0.24)), mat("Floor", (0.16, 0.16, 0.17))
h = H.build_hero(coll, MD, MN, "Clay", 1.0, clay=clay); arm, shell = h["root"], h["shell"]
bm = bpy.data.meshes.new("Floor"); bm.from_pydata([(-3, -3, 0), (3, -3, 0), (3, 3, 0), (-3, 3, 0)], [], [(0, 1, 2, 3)]); fl = bpy.data.objects.new("Floor", bm); coll.objects.link(fl); fl.data.materials.append(floor_m)
def verts():
    dg = bpy.context.evaluated_depsgraph_get(); ev = shell.evaluated_get(dg); me = ev.to_mesh(); M = shell.matrix_world
    P = [M @ v.co for v in me.vertices]; ev.to_mesh_clear(); return P
# rest-pose measurements (one mesh, before posing)
P = verts(); zt = max(p.z for p in P)
print(f"REST height {zt:.3f}  head 0.238 -> {zt / 0.238:.2f} heads", flush=True)
def cam(name, loc, aim, ortho=None, lens=50):
    cd = bpy.data.cameras.new(name)
    if ortho: cd.type = "ORTHO"; cd.ortho_scale = ortho
    else: cd.lens = lens
    ob = bpy.data.objects.new(name, cd); sc.collection.objects.link(ob); ob.location = loc
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y"); return ob
def shot(name, c):
    sc.camera = c; sc.render.filepath = os.path.join(OUT, name + ".png"); bpy.ops.render.render(write_still=True)
# standing contrapposto, feet on the ground
H.pose_standing(arm); arm.location = (0, 0, 0); bpy.context.view_layer.update(); arm.location.z = -H.lowest_z(h); bpy.context.view_layer.update()
P = verts(); hw = max(abs(p.x) for p in P if 1.60 < p.z < 1.72) * 2
def span(z0, z1, xmax=9.0):
    xs = [p.x for p in P if z0 < p.z < z1 and abs(p.x) < xmax]; return max(xs) - min(xs)
hw = span(1.62, 1.70); sw = span(1.38, 1.44); wa = span(1.08, 1.12, 0.15); hp = span(0.86, 0.94, 0.19)
print(f"STAND height {max(p.z for p in P):.3f}  head width {hw:.3f}  shoulders (deltoids) {sw:.3f} = {sw / hw:.2f} head widths  waist {wa:.3f}  hips {hp:.3f}  shoulders/hips {sw / hp:.2f}", flush=True)
shot("1_front", cam("front", (0, -6, 0.92), (0, 0, 0.92), 2.05)); shot("2_profile", cam("side", (6, 0, 0.92), (0, 0, 0.92), 2.05))
shot("3_q34", cam("q34", (2.7, -3.5, 1.25), (0, 0, 0.90), lens=50))
# seated: cushion top = the root height; seat = cushion + backrest along the back
seat_obs = []
def seat(z_c, recline, depth=0.48):
    for o in seat_obs: bpy.data.objects.remove(o)
    seat_obs.clear()
    def box(n, c, s, R=Matrix.Identity(3)):
        me = bpy.data.meshes.new(n); vs = [R @ Vector((x * s[0] / 2, y * s[1] / 2, z * s[2] / 2)) + Vector(c) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        me.from_pydata(vs, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]); ob = bpy.data.objects.new(n, me); coll.objects.link(ob); ob.data.materials.append(seat_m); seat_obs.append(ob)
    box("Cushion", (0, 0.02, z_c / 2), (0.50, depth, z_c))
    R = Matrix.Rotation(-math.radians(recline), 3, "X"); hb = arm.pose.bones["hips"].head
    off = (0.15 + 0.11 * math.sin(math.radians(recline))) / math.cos(math.radians(recline))      # front face of the backrest touches the back
    box("Backrest", Vector((0, hb.y + off, z_c)) + R @ Vector((0, 0, 0.36)), (0.50, 0.10, 0.74), R)
for var in ("req", "fit"):
    arm.location = (0, 0, 0); H.pose_seated(arm, var); bpy.context.view_layer.update()
    low = H.lowest_z(h); z_c = max(0.12, -low) if var == "req" else 0.03       # req: feet on the floor; fit: car seat 3 cm above the floor
    arm.location.z = z_c; bpy.context.view_layer.update(); seat(z_c, H.SEATED[var]["recline"])
    P = verts(); top = max(p.z for p in P)
    print(f"SEATED {var}: cushion {z_c:.3f}  head top {top:.3f} (= {top - z_c:.3f} above the cushion)  lowest {min(p.z for p in P):.3f}", flush=True)
    shot(f"4_seat_{var}_q34", cam("s34" + var, (2.3, -2.6, 1.15), (0, -0.25, 0.55), lens=50)); shot(f"5_seat_{var}_profile", cam("ss" + var, (5, -0.25, 0.65), (0, -0.25, 0.65), 1.75))
# hand close-up (standing pose, right hand): simplified, separate thumb
H.pose_standing(arm); arm.location = (0, 0, 0); bpy.context.view_layer.update(); arm.location.z = -H.lowest_z(h); bpy.context.view_layer.update()
for o in seat_obs: o.hide_render = True
hw_ = arm.pose.bones["hand.R"]; hc = arm.matrix_world @ ((hw_.head + hw_.tail) / 2)
shot("6_hand", cam("hand", hc + Vector((-0.36, -0.46, 0.06)).normalized() * 0.95, hc, lens=85))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "clay.blend"))
print("CLAY_DONE", flush=True)
