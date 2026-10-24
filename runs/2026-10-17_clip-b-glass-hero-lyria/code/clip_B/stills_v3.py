"""clip_B hero v3 stills: frames of S3 / S5 / S9 in their clip scenes (the clip_draft.py set-up and per-frame plan) with the old hero or the v3
hero at the same spot: the standing one where the old one stands (head to the car), the seated one hip-aligned in the cabin (head to the wheel
in S5, up to the ground in S9); a cold white-blue rim from behind on v3 (1.5x the old rim). Final settings: 64 spp, adaptive 0.02, OIDN,
volume step 1.0, 1080x1920. A 1-spp warm-up first, then the timed render.
usage: blender -b --python stills_v3.py -- <frames: 170,372,605> <old|v3> [pct=100] [spp=64]  ->  v3/stills/<S>_<who>_f####.png, v3/stills/times.json"""
import os, sys, time, json, math
C = "/content/drive/MyDrive/renders/clip_B"; sys.path.insert(0, C)
a_ = sys.argv[sys.argv.index("--") + 1:]; FR = [int(x) for x in a_[0].split(",")]; WHO = a_[1]
PCT_ = int(a_[2]) if len(a_) > 2 else 100; SPP_ = int(a_[3]) if len(a_) > 3 else 64
OUT3 = os.path.join(C, "v3", "stills"); os.makedirs(OUT3, exist_ok=True)
os.environ.update(DRAFT_OUT=os.path.join(OUT3, "_unused"), DRAFT_STEP="1.0", DRAFT_ADAPT="0.02")
sys.argv = [sys.argv[0], "--", "0", str(SPP_), str(PCT_)]
__file__ = os.path.join(C, "clip_draft.py")
_src = open(__file__).read(); exec(compile(_src[:_src.index("# ---- render loop ----")], __file__, "exec"))
import hero_v3 as H3
from mathutils import Vector, Matrix
S3SC = 1.73 / 1.719                                    # the v3 figure at the old hero's height (1.73 m)
stand3 = H3.build_hero(coll, "HeroStandV3", S3SC); seat3 = H3.build_hero(coll, "HeroSeatV3", S3SC)
sr = seat["root"]; r3 = seat3["root"]; r3.parent = rig; r3.rotation_euler = (0, 0, math.pi); r3.location = sr.location.copy()
RZ = Matrix.Rotation(math.pi, 3, "Z")
def seat3_pose(look_world):
    for k in range(2):                                 # pass 1: hips onto the old hero's hips; pass 2: the look with the final placement
        vl.update(); posed = H3.pose_seated_from(r3, sr, r3.matrix_world.inverted() @ look_world)
        hip3 = 0.5 * (posed["upperleg01.L"].translation + posed["upperleg01.R"].translation)
        hipo = 0.5 * (sr.pose.bones["thigh.L"].head + sr.pose.bones["thigh.R"].head)
        r3.location = sr.location + RZ @ (hipo * SCALE - hip3 * S3SC)
    vl.update()
def stand3_place(look_world):
    o = stand["root"]; r = stand3["root"]; r.location = (o.location.x, o.location.y, 0.0); r.rotation_euler = o.rotation_euler.copy(); vl.update()
    H3.pose_standing(r, r.matrix_world.inverted() @ look_world, "L"); vl.update()
    r.location.z = -H3.lowest_z(stand3) * S3SC; vl.update()
def rim3_make(h, energy):
    ld = bpy.data.lights.new("Rim3_" + h["root"].name, "AREA"); ld.energy = energy; ld.size = 1.5; ld.color = H3.RIM_COL
    lo = bpy.data.objects.new(ld.name, ld); coll.objects.link(lo); lo.rotation_mode = "QUATERNION"; lo.visible_camera = False
    rc = bpy.data.collections.new(ld.name + "_recv"); rc.objects.link(h["shell"])
    lo.light_linking.receiver_collection = rc; rc.collection_objects[0].light_linking.link_state = "INCLUDE"; return lo
RIM3 = {"stand": rim3_make(stand3, 180.0), "seat": rim3_make(seat3, 72.0)}
# in the cabin the outside rim is blocked by the roof: a cold rim behind-above the seat and a faint cold fill from the dash, on the v3 glass only
CAB3 = {"rim": rim3_make(seat3, 14.0), "fill": rim3_make(seat3, 4.0)}; CAB3["rim"].data.size = 0.3; CAB3["fill"].data.size = 0.5
for lo in CAB3.values(): lo.parent = rig
def cab3_update():
    Minv = rig.matrix_world.inverted(); c = Minv @ seat3["core_ref"].matrix_world.translation
    for k, off, aim in (("rim", Vector((0.30, -0.45, 0.30)), Vector((0, 0, 0.12))), ("fill", Vector((-0.15, 0.55, -0.05)), Vector((0, 0.30, -0.30)))):
        p_ = c + off; p_.z = min(p_.z, 0.98); lo = CAB3[k]; lo.location = p_; lo.rotation_quaternion = ((c + aim) - p_).to_track_quat("-Z", "Y")
def rim3_update(who, cam_loc):
    h = stand3 if who == "stand" else seat3; side = 1.0 if who == "stand" else -1.0; lo = RIM3[who]
    tgt = h["core_ref"].matrix_world.translation.copy(); back = flat(tgt - cam_loc); p = tgt + back * 2.2 + rotz(back, 90 * side) * 1.2 + Vector((0, 0, 1.3))
    lo.location = p; lo.rotation_quaternion = (tgt - p).to_track_quat("-Z", "Y")
def look_target(sid):
    if sid == "S5": return bbox_c("SteeringWheel", Matrix.Identity(4))
    if sid == "S9": c = rig.matrix_world.translation; return Vector((c.x, c.y + 3.0, 0.0))          # upside down: the ground is 'up' for him
    return bbox_c("Body", Matrix.Identity(4))                                                       # S3: the car
TF = os.path.join(OUT3, "times.json"); TIMES = json.load(open(TF)) if os.path.exists(TF) else {}
for f in FR:
    sid, s, (loc, aim, ln, fs, up), st = plan(f)
    for who, h, h3 in (("stand", stand, stand3), ("seat", seat, seat3)):
        on = st[who] is not None; g = glow(f, 1.15 if who == "stand" else 1.0)
        show(h, on and WHO == "old"); RIM[who].hide_render = not (on and WHO == "old")
        show(h3, on and WHO == "v3"); RIM3[who].hide_render = not (on and WHO == "v3")
        if on and WHO == "old": H.set_state(h, dissolve=st[who], glow=g)
        if on and WHO == "v3": H3.set_state(h3, dissolve=st[who], glow=g, t=f / 24.0, breath=0.5 + 0.5 * math.sin(2 * math.pi * f / (24 * 4.5)))
    if WHO == "v3":
        if st["stand"] is not None: stand3_place(look_target(sid))
        if st["seat"] is not None: seat3_pose(look_target(sid)); cab3_update()
    for lo in CAB3.values(): lo.hide_render = not (WHO == "v3" and st["seat"] is not None)
    markers(*st["mk"]); sc.view_settings.exposure = st["expo"]; WHEEL.rotation_euler = (W_TILT, st["wheel"], 0)
    tail_set(st["tail"]); wheel_spin(st["spin"]); smoke_set(f); jets_set(s); cores_set(st["core"], s)
    for lo, key in ((SWEEP, "sweep"), (CAR_RIM, "rim")):
        lo.hide_render = st[key] is None
        if st[key] is not None: lo.location = st[key][0]; lo.rotation_quaternion = look_rot(st[key][0], st[key][1], Vector((0, 0, 1)))
    sc.render.use_motion_blur = st["mb"] is not None
    if st["mb"] is not None: sc.render.motion_blur_shutter = st["mb"]
    follow(st["follow"])
    if st["follow"] is not None: cd.lens = ln; cd.dof.focus_object = AIMO; cd.dof.aperture_fstop = fs
    else: cd.dof.focus_object = None; set_cam(loc, aim, ln, fs, up if up is not None else Vector((0, 0, 1)))
    vl.update(); cam_now = camo.matrix_world.translation.copy()
    for who in ("stand", "seat"):
        if st[who] is not None: (rim_update if WHO == "old" else rim3_update)(who, cam_now)
    sparks_set(f, cam_now); vl.update()
    s0_ = sc.cycles.samples; sc.cycles.samples = 1; sc.render.filepath = "/tmp/warm_v3.png"; bpy.ops.render.render(write_still=True); sc.cycles.samples = s0_
    fp = os.path.join(OUT3, f"{sid}_{WHO}_f{f:04d}.png"); sc.render.filepath = fp; t1 = time.time(); bpy.ops.render.render(write_still=True); tr = time.time() - t1
    TIMES[f"{sid}_{WHO}_{PCT_}_{SPP_}"] = round(tr, 1); json.dump(TIMES, open(TF, "w"), indent=1)
    print(f"STILL {sid} f={f} {WHO} {PCT_}% {SPP_}spp render {tr:.1f}s -> {fp}", flush=True)
print("STILLS_DONE", flush=True)
