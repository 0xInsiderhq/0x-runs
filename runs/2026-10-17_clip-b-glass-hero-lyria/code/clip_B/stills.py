"""clip_B stage 1: three final-quality hero stills in the real stunt_v2 scene (night airfield, ground fog, red markers, the loop).
S3: medium 3/4, hero beside the car, head turned to the loop, loop in the fog behind. S5: cabin through the windshield, 3/4 front.
S14: dissolving into coral-amber particles, the rest of the body still glass.
usage: blender -b --python stills.py -- [which: S3,S5,S14] [samples] [preview]   (preview: every candidate camera, 270x480 PNG)"""
import bpy, sys, os, math, time, json
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
C = os.path.dirname(os.path.abspath(__file__)); V2 = os.path.join(C, "..", "stunt_v2"); MD = os.path.join(C, "hero_mesh")
sys.path.insert(0, C)
import hero as H, cabin as CAB
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
WHICH = (args[0] if args else "S3,S5,S14").split(","); SAMPLES = int(args[1]) if len(args) > 1 else 256
PREVIEW = len(args) > 2 and args[2].startswith("preview"); PCT = int(args[2][7:] or 25) if PREVIEW else 100
ONLY = args[3].split(",") if len(args) > 3 else None          # preview: only these candidates
ENV = {k: float(os.environ[k]) for k in ("CLIP_GLOW", "CLIP_ROUGH", "CLIP_COAT", "CLIP_RIM", "CLIP_VOLE", "CLIP_VOLD", "CLIP_ORBIT") if k in os.environ}
FRAMES = os.environ.get("CLIP_FRAMES", "").split(",") if os.environ.get("CLIP_FRAMES") else None
SCALE = 0.97                      # hero height 1.73 m: 7 cm roof clearance in the car with any head turn
LOOP_C = Vector((26.0, 62.0, 9.0))  # centre of the loop (both halves)
bpy.ops.wm.open_mainfile(filepath=os.path.join(V2, "stunt.blend"))
sc = bpy.context.scene; sc.frame_set(1)
for m in sc.timeline_markers: m.camera = None                                      # stunt shot markers would override sc.camera
pr = bpy.context.preferences.addons["cycles"].preferences; pr.compute_device_type = "OPTIX"; pr.get_devices()
for d in pr.devices: d.use = d.type == "OPTIX"
sc.cycles.device = "GPU"; sc.cycles.samples = SAMPLES; sc.cycles.adaptive_threshold = 0.015
sc.cycles.transmission_bounces = 12; sc.cycles.volume_bounces = 2; sc.cycles.transparent_max_bounces = 16; sc.cycles.max_bounces = 16
sc.cycles.caustics_reflective = sc.cycles.caustics_refractive = False
print("LIGHTPATHS", dict(max=sc.cycles.max_bounces, diffuse=sc.cycles.diffuse_bounces, glossy=sc.cycles.glossy_bounces, transmission=sc.cycles.transmission_bounces,
      volume=sc.cycles.volume_bounces, transparent=sc.cycles.transparent_max_bounces, caustics=(sc.cycles.caustics_reflective, sc.cycles.caustics_refractive),
      samples=SAMPLES, adaptive=sc.cycles.adaptive_threshold, denoiser=sc.cycles.denoiser), flush=True)
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1080, 1920, PCT
sc.render.use_motion_blur = False
coll = bpy.data.collections.new("ClipHero"); sc.collection.children.link(coll)
body = bpy.data.objects["Body"]; rig = body.parent; car_M = rig.matrix_world.copy()
def W(p): return car_M @ Vector(p)
def flat(v): v = Vector((v.x, v.y, 0)); return v.normalized()
def rotz(v, deg): return Matrix.Rotation(math.radians(deg), 3, "Z") @ v
# ---- standing hero beside the driver's door: hips turned toward the camera side, chest + head turned to the loop ----
stand = H.build_hero(coll, MD, "final", "HeroStand", SCALE)
hs = W((1.50, 0.3, 0.0)); hs.z = 0.0                                              # beside the right door: the car behind the hero, the loop above its nose
u = flat(LOOP_C - hs)                                                              # towards the loop
S3_CAM = W((2.6, -2.4, 1.30))                                                    # S3 camera: behind-right of the hero, looking across the car to the loop
c3 = flat(S3_CAM - hs)
CAM3_DELTA = -12.0
f_h = max((rotz(u, a) for a in (75, -75)), key=lambda f: f.dot(c3))               # hips: profile to the S3 camera
turn = math.degrees(math.atan2(f_h.cross(u).z, f_h.dot(u)))                        # f_h -> u, CCW positive = hero's left
stand["root"].rotation_euler = (0, 0, math.atan2(f_h.x, -f_h.y))                   # local -Y (the hero's front) -> f_h
H.pose_standing(stand["root"], torso_yaw=math.radians(turn * 0.3), head_yaw=math.radians(turn * 0.7))
stand["root"].location = (hs.x, hs.y, 0); bpy.context.view_layer.update(); stand["root"].location.z = -H.lowest_z(stand) * SCALE
# ---- seated hero in the cabin: sports-car seat ----
seat = H.build_hero(coll, MD, "final", "HeroSeat", SCALE)
Mb = rig.matrix_world.inverted() @ body.matrix_world
wv = [Mb @ body.data.vertices[i].co for p in body.data.polygons if p.material_index == 1 for i in p.vertices]
Y_HIP = 0.5 * (min(v.y for v in wv) + max(v.y for v in wv)) - 0.16; Z_C = 0.135
sr = seat["root"]; sr.parent = rig; sr.rotation_euler = (0, 0, math.pi); sr.location = (0, Y_HIP, Z_C)
H.pose_seated(sr, "fit"); bpy.context.view_layer.update()
Mr = rig.matrix_world.inverted() @ sr.matrix_world
hips_r = Mr @ sr.pose.bones["hips"].head; knee_r = Mr @ (0.5 * (sr.pose.bones["shin.L"].head + sr.pose.bones["shin.R"].head))
CAB.build_cabin(coll, dict(hips=hips_r, knee=knee_r, z_c=Z_C, recline=H.SEATED["fit"]["recline"], scale=SCALE))
# ---- rim light: area light behind the hero (opposite the camera), lights only the hero's glass ----
def rim_for(hero, cam_loc, side=1.0, energy=60.0):
    tgt = hero["root"].matrix_world @ hero["root"].pose.bones["chest"].head
    back = flat(tgt - cam_loc); p = tgt + back * 2.2 + rotz(back, 90 * side) * 1.2 + Vector((0, 0, 1.3))
    ld = bpy.data.lights.new("Rim_" + hero["root"].name, "AREA"); ld.energy = energy; ld.size = 1.5; ld.color = (0.80, 0.87, 1.0)
    lo = bpy.data.objects.new(ld.name, ld); coll.objects.link(lo); lo.location = p
    lo.rotation_mode = "QUATERNION"; lo.rotation_quaternion = (tgt - p).to_track_quat("-Z", "Y")
    rc = bpy.data.collections.get(ld.name + "_recv") or bpy.data.collections.new(ld.name + "_recv")
    if hero["shell"].name not in rc.objects: rc.objects.link(hero["shell"])
    lo.light_linking.receiver_collection = rc; rc.collection_objects[list(rc.objects).index(hero["shell"])].light_linking.link_state = "INCLUDE"
    return lo
def cam(name, loc, aim, lens, fstop=2.8):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.sensor_width = 36; cd.sensor_fit = "AUTO"; cd.dof.use_dof = True
    ob = bpy.data.objects.new(name, cd); sc.collection.objects.link(ob); ob.location = loc
    ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y")
    cd.dof.focus_distance = (Vector(aim) - Vector(loc)).length; cd.dof.aperture_fstop = fstop; return ob
chest_s = stand["root"].matrix_world @ stand["root"].pose.bones["chest"].head
def place_stand(pos_rig, face_dir=None, look_loop=True, cam_world=None):
    """standing hero at a car-local spot; hips profile to the camera and head to the loop, or a given facing with a straight head"""
    p = W(pos_rig); p.z = 0.0; uu = flat(LOOP_C - p)
    f = face_dir if face_dir is not None else max((rotz(uu, a) for a in (75, -75)), key=lambda q: q.dot(flat(cam_world - p)))
    t = math.degrees(math.atan2(f.cross(uu).z, f.dot(uu))) if look_loop else 0.0
    r = stand["root"]; r.location = (0, 0, 0); r.rotation_euler = (0, 0, math.atan2(f.x, -f.y))
    H.pose_standing(r, torso_yaw=math.radians(t * 0.3), head_yaw=math.radians(t * 0.7)); r.location = (p.x, p.y, 0); bpy.context.view_layer.update()
    r.location.z = -H.lowest_z(stand) * SCALE; bpy.context.view_layer.update(); return p, uu, f
if WHICH[0] in ("FINAL", "PRE3"):                        # the three stage-1 stills, each with its own set-up; PRE3 = 25 % / few samples check
    if WHICH[0] == "PRE3": sc.render.resolution_percentage = 25
    OUT = os.environ.get("CLIP_OUT", os.path.join(C, "stills_exr")); os.makedirs(OUT, exist_ok=True)
    ONLY3 = os.environ.get("CLIP_ONLY", "").split(",") if os.environ.get("CLIP_ONLY") else None
    def s3_setup(axis_deg, lens, cam_rig=(-1.6, -6.5, 1.35), pitch_deg=5.0):
        cl = W(cam_rig); place_stand((-2.16, -2.54, 0.0), cam_world=cl, look_loop=True)
        a = math.radians(axis_deg); p = math.radians(pitch_deg)
        aim = W((cam_rig[0] + math.sin(a) * 6, cam_rig[1] + math.cos(a) * 6, cam_rig[2] + math.tan(p) * 6)); return cl, aim, lens, 0.0, "stand"
    def s5_setup():
        return W((-1.15, 3.5, 1.55)), W((0.0, Y_HIP - 0.12, 0.70)), 46, 0.0, "seat"
    def s14_setup():
        p, uu, f = place_stand((-1.55, 0.2, 0.0), cam_world=W((-1.75, -2.6, 1.30)), look_loop=True)
        ch = stand["root"].matrix_world @ stand["root"].pose.bones["chest"].head
        return p + rotz(f, -30) * 3.4 + Vector((0, 0, 1.0)), ch + Vector((0, 0, 0.35)), 35, 0.38, "stand"
    SETS = {"S3": lambda: s3_setup(5, 28), "S3x": lambda: s3_setup(8, 28), "S3y": lambda: s3_setup(4, 24), "S3n": lambda: s3_setup(6, 26, cam_rig=(-1.75, -5.15, 1.05), pitch_deg=1.0), "S5": s5_setup, "S14": s14_setup}
    names = [n for n in (WHICH[1:] or ["S3", "S5", "S14"]) if not ONLY3 or n in ONLY3]
    for h in (stand, seat):
        ntc = h["core"].data.materials[0].node_tree
        if "CLIP_VOLE" in ENV: ntc.nodes["vol_e"].outputs[0].default_value = ENV["CLIP_VOLE"]
    times = {}; boxes = {}
    for n in names:
        loc, aim, lens, dis, who = SETS[n]()
        for h, nm in ((stand, "stand"), (seat, "seat")):
            on = nm == who
            for ob in [h["root"]] + list(h["root"].children_recursive): ob.hide_render = not on
            H.set_state(h, dissolve=dis if on else 0.0, glow=ENV.get("CLIP_GLOW", {"S3n": 1.5, "S3": 1.5}.get(n, 1.0)))
        for lo in [o for o in coll.objects if o.name.startswith("Rim_")]: bpy.data.objects.remove(lo)
        hero = stand if who == "stand" else seat
        rim_for(hero, loc, 1.0 if who == "stand" else -1.0, ENV.get("CLIP_RIM", 120.0) * (1.0 if who == "stand" else 0.4))
        cam_ob = cam("Cam_" + n, loc, aim, lens); sc.camera = cam_ob; bpy.context.view_layer.update()
        ch = hero["root"].matrix_world @ hero["root"].pose.bones["chest"].head; pc = world_to_camera_view(sc, cam_ob, ch); boxes[n] = [round(pc.x, 4), round(pc.y, 4)]
        sc.render.filepath = os.path.join(OUT, "still_" + n)
        t0 = time.time(); bpy.ops.render.render(write_still=True); times[n] = round(time.time() - t0, 1)
        print(f"FINAL {n}: {times[n]} s at {sc.render.resolution_x * sc.render.resolution_percentage // 100}x{sc.render.resolution_y * sc.render.resolution_percentage // 100} {SAMPLES} spp, chest at {boxes[n]}", flush=True)
    json.dump(dict(times=times, chest_uv=boxes), open(os.path.join(OUT, "stills_info.json"), "w"))
    if WHICH[0] == "FINAL": bpy.ops.wm.save_as_mainfile(filepath=os.path.join(C, "clip_stills.blend"))
    print("FINAL_DONE", flush=True); sys.exit(0)
if WHICH[0] == "TURN":                                   # material test: hero close in the scene light, 4-step turnaround + glow-off control
    OUT = os.environ.get("CLIP_OUT", os.path.join(C, "test_glass")); os.makedirs(OUT, exist_ok=True); POS = (-2.16, -2.54, 0.0)
    for ob in [seat["root"]] + list(seat["root"].children_recursive): ob.hide_render = True
    for ob in [stand["root"]] + list(stand["root"].children_recursive): ob.hide_render = False
    p0, u0, _ = place_stand(POS, face_dir=Vector((0, 1, 0)), look_loop=False)
    camL = p0 - rotz(u0, ENV.get("CLIP_ORBIT", 0.0)) * 2.4 + Vector((0, 0, 1.35)); times = {}
    for h in (stand, seat):
        ntc = h["core"].data.materials[0].node_tree
        if "CLIP_VOLE" in ENV: ntc.nodes["vol_e"].outputs[0].default_value = ENV["CLIP_VOLE"]
        if "CLIP_VOLD" in ENV: ntc.nodes["vol_d"].outputs[0].default_value = ENV["CLIP_VOLD"]
    for name, spin, glow in (("turn_000", 0, 1.0), ("turn_090", 90, 1.0), ("turn_180", 180, 1.0), ("turn_270", 270, 1.0), ("control_noglow", 0, 0.0)):
        if FRAMES and name not in FRAMES: continue
        place_stand(POS, face_dir=rotz(flat(camL - p0), spin), look_loop=False)
        ch = stand["root"].matrix_world @ stand["root"].pose.bones["chest"].head
        cam_ob = cam("TurnCam_" + name, camL, ch + Vector((0, 0, 0.12)), 50)
        for lo in [o for o in coll.objects if o.name.startswith("Rim_")]: bpy.data.objects.remove(lo)
        rim_for(stand, camL, 1.0, ENV.get("CLIP_RIM", 120.0)); H.set_state(stand, dissolve=0.0, glow=glow)
        sc.camera = cam_ob; sc.render.filepath = os.path.join(OUT, name)
        t0 = time.time(); bpy.ops.render.render(write_still=True); times[name] = round(time.time() - t0, 1)
        print(f"TURN {name}: spin {spin}, glow {glow}, {times[name]} s at {sc.render.resolution_x}x{sc.render.resolution_y} {SAMPLES} spp", flush=True)
    json.dump(times, open(os.path.join(OUT, "times.json"), "w")); print("TURN_DONE", flush=True); sys.exit(0)
def s3r(loc, aim, lens): return W(loc), W(aim), lens
def s3(delta, dist, lens, h, blend, lift):
    c = hs + rotz(-u, delta) * dist + Vector((0, 0, h)); aim_dir = ((chest_s - c).normalized().lerp((LOOP_C - c).normalized(), blend)).normalized()
    return c, c + aim_dir * dist + Vector((0, 0, lift)), lens
def s14(side, dist, lens, h, lift):
    c = hs + rotz(f_h, 30 * side) * dist + Vector((0, 0, h)); return c, chest_s + Vector((0, 0, lift)), lens
def s5(loc, lens, aim=(0.0, -0.12, 0.70)):
    return W(loc), W((aim[0], Y_HIP + aim[1], aim[2])), lens
CANDS = {"S3a": ("stand", 0.0) + s3(CAM3_DELTA, 3.6, 40, 1.30, 0.22, 0.25), "S3b": ("stand", 0.0) + s3(-20, 3.2, 35, 1.20, 0.30, 0.35),
         "S3c": ("stand", 0.0) + s3(-8, 4.6, 50, 1.40, 0.18, 0.20),
         "S5a": ("seat", 0.0) + s5((-1.6, 3.1, 1.40), 35), "S5b": ("seat", 0.0) + s5((-1.15, 3.5, 1.55), 40), "S5c": ("seat", 0.0) + s5((-2.1, 2.7, 1.30), 32),
         "S3j": ("stand", 0.0) + s3r((2.6, -2.4, 1.30), (1.31, 2.43, 2.30), 35), "S3k": ("stand", 0.0) + s3r((2.9, -2.0, 1.25), (1.35, 2.76, 2.25), 32),
         "S3l": ("stand", 0.0) + s3r((2.4, -2.9, 1.40), (1.28, 1.97, 2.40), 40),
         "S3g": ("stand", 0.0) + s3r((-1.75, -2.6, 1.30), (-2.15, 3.0, 2.15), 50), "S3h": ("stand", 0.0) + s3r((-2.05, -2.3, 1.25), (-2.30, 3.0, 2.30), 40),
         "S3i": ("stand", 0.0) + s3r((-1.50, -3.2, 1.40), (-2.30, 3.0, 2.35), 50),
         "S5f": ("seat", 0.0) + s5((-1.0, 1.9, 1.35), 35, (0.0, -0.05, 0.78)), "S5g": ("seat", 0.0) + s5((-1.4, 2.2, 1.45), 40, (0.0, -0.05, 0.78)),
         "S5h": ("seat", 0.0) + s5((-0.6, 2.4, 1.50), 35, (0.0, -0.05, 0.78)),
         "S3d": ("stand", 0.0) + s3(5, 2.6, 35, 1.25, 0.30, 0.35), "S3e": ("stand", 0.0) + s3(-5, 2.4, 40, 1.35, 0.25, 0.30), "S3f": ("stand", 0.0) + s3(12, 2.8, 35, 1.20, 0.35, 0.40),
         "S5d": ("seat", 0.0) + s5((-1.3, 2.6, 1.75), 35, (0.0, -0.05, 0.62)), "S5e": ("seat", 0.0) + s5((-0.9, 2.9, 1.65), 40, (0.0, -0.05, 0.62)),
         "S14a": ("stand", 0.62) + s14(1, 3.4, 35, 1.0, 0.35), "S14b": ("stand", 0.62) + s14(-1, 3.4, 35, 1.0, 0.35), "S14c": ("stand", 0.62) + s14(1, 4.2, 40, 0.8, 0.45)}
FINAL = {"S3": "S3g", "S5": "S5f", "S14": "S14b"}
if PREVIEW:
    jobs = [(n, n) for n in CANDS if not ONLY or n in ONLY]; OUT = "/content/prev"
    im = sc.render.image_settings; im.file_format = "PNG"; im.color_mode = "RGB"; im.color_depth = "8"; sc.render.use_compositing = False
else:
    jobs = [(f"still_{k}", FINAL[k]) for k in WHICH]; OUT = os.path.join(C, "stills_exr")
os.makedirs(OUT, exist_ok=True); boxes = {}
for out_name, cn in jobs:
    who, dis, loc, aim, lens = CANDS[cn]; cam_ob = cam("Cam_" + cn, loc, aim, lens)
    for h, nm in ((stand, "stand"), (seat, "seat")):
        on = nm == who
        for ob in [h["root"]] + list(h["root"].children_recursive): ob.hide_render = not on
        H.set_state(h, dissolve=dis if on else 0.0, glow=ENV.get("CLIP_GLOW", H.GLOW_NOM))
        p = h["shell"].data.materials[0].node_tree.nodes.get("Principled BSDF")
        if p is not None:
            if "CLIP_ROUGH" in ENV: p.inputs["Roughness"].default_value = ENV["CLIP_ROUGH"]
            if "CLIP_COAT" in ENV: p.inputs["Coat Weight"].default_value = ENV["CLIP_COAT"]
    for lo in [o for o in coll.objects if o.name.startswith("Rim_")]: bpy.data.objects.remove(lo)
    rim_for(stand if who == "stand" else seat, Vector(loc), 1.0 if who == "stand" else -1.0, ENV.get("CLIP_RIM", 120.0) * (1.0 if who == "stand" else 0.4))
    sc.camera = cam_ob; sc.render.filepath = os.path.join(OUT, out_name); bpy.context.view_layer.update()
    h = stand if who == "stand" else seat; ev = h["shell"].evaluated_get(bpy.context.evaluated_depsgraph_get()); me = ev.to_mesh()
    pts = [world_to_camera_view(sc, cam_ob, h["shell"].matrix_world @ v.co) for v in [me.vertices[i] for i in range(0, len(me.vertices), 25)]]; ev.to_mesh_clear()
    boxes[out_name] = [min(p.x for p in pts), min(p.y for p in pts), max(p.x for p in pts), max(p.y for p in pts)]
    t0 = time.time(); bpy.ops.render.render(write_still=True); print(f"STILL {out_name} ({cn}) rendered in {time.time() - t0:.0f}s, hero box {[round(x, 3) for x in boxes[out_name]]}", flush=True)
json.dump(boxes, open(os.path.join(OUT, "hero_boxes.json"), "w"))
if not PREVIEW: bpy.ops.wm.save_as_mainfile(filepath=os.path.join(C, "clip_stills.blend"))
print("STILLS_DONE", flush=True)
