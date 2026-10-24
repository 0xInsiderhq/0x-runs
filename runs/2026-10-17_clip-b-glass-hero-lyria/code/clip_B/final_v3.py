"""clip_B final, hero v3: S3, S5, S8b, S9 with the v3 hero exactly as on the approved stills (stills_v3.py set-up: the clip_draft plan,
v3 at the old hero's spot, cold rim 1.5x, in the cabin the cold rim + dash fill on the v3 glass), plus the per-frame motion of the spec:
chest breathing and calm CMU micro-motion (seated idle 13_02 / standing 82_08) on top of the look-at. Final settings (64 spp, adaptive 0.02,
OIDN, volume step 1.0, 1080x1920) into final_frames/; the old-hero frames of S3 / S5 are moved to old_hero/ first (never deleted).
Resumable (v3/final_v3_state.json); a frame that fails or crashes the process twice is skipped, logged and retried at the end.
After each shot its middle frame goes to review/<S>_v3.jpg. usage: blender -b --python final_v3.py   (run by final_v3.sh)"""
import os, sys, time, json, math, shutil
C = "/content/drive/MyDrive/renders/clip_B"; sys.path.insert(0, C)
FD = os.path.join(C, "final_frames"); OLD = os.path.join(C, "old_hero"); RV = os.path.join(C, "review"); os.makedirs(OLD, exist_ok=True); os.makedirs(RV, exist_ok=True)
SF = os.path.join(C, "v3", "final_v3_state.json")
STATE = json.load(open(SF)) if os.path.exists(SF) else {"done": [], "crash": {}, "skipped": []}
def save_state(): json.dump(STATE, open(SF + ".tmp", "w")); os.replace(SF + ".tmp", SF)
if STATE.get("current") is not None:                                            # the last run died on this frame
    c_ = str(STATE["current"]); STATE["crash"][c_] = STATE["crash"].get(c_, 0) + 1; STATE["current"] = None; save_state()
os.environ.update(DRAFT_OUT=os.path.join(C, "v3", "stills", "_unused"), DRAFT_STEP="1.0", DRAFT_ADAPT="0.02")
sys.argv = [sys.argv[0], "--", "0", "64", "100"]
__file__ = os.path.join(C, "clip_draft.py")
_src = open(__file__).read(); exec(compile(_src[:_src.index("# ---- render loop ----")], __file__, "exec"))
import hero_v3 as H3
from mathutils import Vector, Matrix
S3SC = 1.73 / 1.719
stand3 = H3.build_hero(coll, "HeroStandV3", S3SC); seat3 = H3.build_hero(coll, "HeroSeatV3", S3SC)
sr = seat["root"]; r3 = seat3["root"]; r3.parent = rig; r3.rotation_euler = (0, 0, math.pi); r3.location = sr.location.copy()
RZ = Matrix.Rotation(math.pi, 3, "Z")
def seat3_pose(look_world, mo):
    for k in range(2):
        vl.update(); posed = H3.pose_seated_from(r3, sr, r3.matrix_world.inverted() @ look_world, mo)
        hip3 = 0.5 * (posed["upperleg01.L"].translation + posed["upperleg01.R"].translation)
        hipo = 0.5 * (sr.pose.bones["thigh.L"].head + sr.pose.bones["thigh.R"].head)
        r3.location = sr.location + RZ @ (hipo * SCALE - hip3 * S3SC)
    vl.update()
def stand3_place(look_world, mo):
    o = stand["root"]; r = stand3["root"]; r.location = (o.location.x, o.location.y, 0.0); r.rotation_euler = o.rotation_euler.copy(); vl.update()
    H3.pose_standing(r, r.matrix_world.inverted() @ look_world, "L", mo); vl.update()
    r.location.z = -H3.lowest_z(stand3) * S3SC; vl.update()
def rim3_make(h, energy):
    ld = bpy.data.lights.new("Rim3_" + h["root"].name, "AREA"); ld.energy = energy; ld.size = 1.5; ld.color = H3.RIM_COL
    lo = bpy.data.objects.new(ld.name, ld); coll.objects.link(lo); lo.rotation_mode = "QUATERNION"; lo.visible_camera = False
    rc = bpy.data.collections.new(ld.name + "_recv"); rc.objects.link(h["shell"])
    lo.light_linking.receiver_collection = rc; rc.collection_objects[0].light_linking.link_state = "INCLUDE"; return lo
RIM3 = {"stand": rim3_make(stand3, 180.0), "seat": rim3_make(seat3, 72.0)}
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
def look_target(sid, f):
    if sid == "S5": return bbox_c("SteeringWheel", Matrix.Identity(4))                            # at the wheel
    if sid == "S9": c = rig.matrix_world.translation; return Vector((c.x, c.y + 3.0, 0.0))          # upside down: up at the ground
    if sid == "S8": return rig.matrix_world @ Vector((0.0, 10.0, 0.8))                              # S8b loop entry: ahead along the car
    return bbox_c("Body", Matrix.Identity(4))                                                       # S3: at the car
show(stand, False); show(seat, False); RIM["stand"].hide_render = RIM["seat"].hide_render = True    # the old hero is never in these frames
SHOTS3 = [("S3", range(140, 249)), ("S5", range(332, 414)), ("S8b", range(536, 576)), ("S9", range(576, 634))]
def render_frame(f):
    sid, s, (loc, aim, ln, fs, up), st = plan(f)
    for who, h3 in (("stand", stand3), ("seat", seat3)):
        on = st[who] is not None; show(h3, on); RIM3[who].hide_render = not on
        if on: H3.set_state(h3, dissolve=st[who], glow=glow(f, 1.15 if who == "stand" else 1.0), t=f / 24.0, breath=0.5 + 0.5 * math.sin(2 * math.pi * f / (24 * 4.5)))
    if st["stand"] is not None: stand3_place(look_target(sid, f), H3.mocap_rot("82_08", f))
    if st["seat"] is not None: seat3_pose(look_target(sid, f), H3.mocap_rot("13_02", f)); cab3_update()
    for lo in CAB3.values(): lo.hide_render = st["seat"] is None
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
        if st[who] is not None: rim3_update(who, cam_now)
    sparks_set(f, cam_now); vl.update()
    fp = os.path.join(FD, f"f_{f:04d}.png"); tmp = "/tmp/v3_frame.png"
    if os.path.exists(fp) and os.path.getsize(fp) != 4096 and not os.path.exists(os.path.join(OLD, f"f_{f:04d}.png")):
        shutil.move(fp, os.path.join(OLD, f"f_{f:04d}.png"))                     # the old-hero frame is kept, not deleted
    sc.render.filepath = tmp; t1 = time.time(); bpy.ops.render.render(write_still=True); tr = time.time() - t1
    if not (os.path.exists(tmp) and os.path.getsize(tmp) > 4096): raise RuntimeError("no image written")
    shutil.copyfile(tmp, fp + ".part"); os.replace(fp + ".part", fp)
    return sid, tr
def review(name, rng):
    mid = rng[len(rng) // 2]; fp = os.path.join(FD, f"f_{mid:04d}.png")
    if os.path.exists(fp) and mid in STATE["done"]:
        import subprocess                                                       # Blender's Python has no PIL: the system python writes the jpg
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        r = subprocess.run(["/usr/bin/python3", "-c", "import sys; from PIL import Image; Image.open(sys.argv[1]).convert('RGB').save(sys.argv[2], quality=90)",
                            fp, os.path.join(RV, f"{name}_v3.jpg")], capture_output=True, text=True, env=env)
        log(f"V3 review: {name} -> review/{name}_v3.jpg (frame {mid})" if r.returncode == 0 else f"V3 review: {name} jpg failed: {r.stderr.strip()[-150:]}")
todo = [f for _, r in SHOTS3 for f in r]
left = [f for f in todo if f not in STATE["done"]]
log(f"V3 start: {len(left)} of {len(todo)} frames left (S3 140-248, S5 332-413, S8b 536-575, S9 576-633), 64 spp, 1080x1920; old-hero frames -> old_hero/")
t_all = time.time(); n = 0; deferred = []
def run(f, final_pass=False):
    global n
    cr = STATE["crash"].get(str(f), 0)
    if cr >= 3: return                                                          # crashed the process three times: left to old_hero/, logged at the end
    if cr >= 2 and not final_pass:
        deferred.append(f); return
    for attempt in (1, 2):
        STATE["current"] = f; save_state()
        try:
            sid, tr = render_frame(f)
            STATE["current"] = None; STATE["done"].append(f)
            if f in STATE["skipped"]: STATE["skipped"].remove(f)
            save_state(); n += 1
            if n % 10 == 1 or f in (248, 413, 575, 633):
                log(f"V3 f={f:04d} {sid} hero v3 render {tr:.1f}s  [{n} new, {len(STATE['done'])}/{len(todo)}, {(time.time() - t_all) / 60:.1f} min]")
            return
        except Exception as e:
            STATE["current"] = None; save_state(); log(f"V3 f={f:04d} error, attempt {attempt}: {str(e)[:150]}")
    if f not in STATE["skipped"]: STATE["skipped"].append(f)
    save_state(); log(f"V3 f={f:04d} SKIPPED after 2 attempts, redone at the end")
for name, rng in SHOTS3:
    for f in rng:
        if f not in STATE["done"]: run(f)
    review(name, rng)
for f in sorted(set(deferred + STATE["skipped"])):                             # the end: one more go at the skipped ones
    if f not in STATE["done"]: run(f, final_pass=True)
left = [f for f in todo if f not in STATE["done"]]
log(f"V3_DONE {len(todo) - len(left)}/{len(todo)} frames, {n} new in {(time.time() - t_all) / 60:.1f} min" + (f"; still missing {left} (the old-hero frame stays in old_hero/)" if left else ""))
print("V3_DONE", flush=True)
