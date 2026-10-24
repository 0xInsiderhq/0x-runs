"""clip_B stage 2: draft clip, shots S1-S14 per timing.json on the stunt_v2 scene, low samples -> draft_frames/f_0000.png (resumable).
Clip frame f (0-based, 24 fps) -> stunt frame s (float, sub-frame evaluation for the slow-mo), per-shot camera, hero state, markers.
Frames 59-71 (cut to black) and the final card are made in the assembly step, not here.
usage: blender -b --python clip_draft.py -- [all | a-b | f1,f2,...] [samples] [percent]"""
import bpy, sys, os, math, json, time
from mathutils import Vector, Matrix
C = os.path.dirname(os.path.abspath(__file__))
a0 = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SEL = a0[0] if a0 else "all"; SAMP = int(a0[1]) if len(a0) > 1 else 16; PCT = int(a0[2]) if len(a0) > 2 else 50
OUTD = os.environ.get("DRAFT_OUT", os.path.join(C, "draft_frames")); os.makedirs(OUTD, exist_ok=True)
PLOG = os.path.join(C, "progress.log")
def log(msg):
    print(msg, flush=True)
    with open(PLOG, "a") as fh: fh.write(time.strftime("%H:%M:%S ") + msg + "\n")
# ---- the stage-1 scene set-up from stills.py (stunt scene, both heroes, cabin, light paths, helpers), without its still jobs ----
_src = open(os.path.join(C, "stills.py")).read(); _cut = _src.index('if WHICH[0] in ("FINAL", "PRE3"):')
sys.argv = [sys.argv[0], "--", "SETUP", str(SAMP)]
exec(compile(_src[:_cut], os.path.join(C, "stills.py"), "exec"))
vl = bpy.context.view_layer
PCT = int(a0[2]) if len(a0) > 2 else 50                 # stills.py set its own PCT
T = json.load(open(os.path.join(C, "timing.json"))); ENVV = json.load(open(os.path.join(C, "audio", "vocal_env.json")))["env"]
SHOTS = [(s["id"], s["start_frame"], s["end_frame"]) for s in T["shots"]]; BEATS = [b["frame"] for b in T["beats"]]
BLACK = range(59, 72)                       # hard cut to black on the first beat, the first marker pair lights on the next one
CARD = 1449                                 # final card from here (assembly step)
# ---- draft render settings ----
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1080, 1920, PCT
sc.cycles.samples = SAMP; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = float(os.environ.get("DRAFT_ADAPT", 0.05))
sc.cycles.use_denoising = True; sc.cycles.denoiser = "OPENIMAGEDENOISE"; sc.cycles.denoising_use_gpu = True
sc.cycles.volume_step_rate = float(os.environ.get("DRAFT_STEP", 3.0)); sc.render.use_persistent_data = True; sc.render.use_motion_blur = False
im = sc.render.image_settings; im.file_format = "PNG"; im.color_mode = "RGB"; im.color_depth = "8"
EXPO = 0.3; sc.view_settings.exposure = EXPO
# compositor = comp_clip.py look: fog glow from the 'glow' AOV only + slight dispersion
sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear(); sc.render.use_compositing = True
rl = nt.nodes.new("CompositorNodeRLayers"); gl = nt.nodes.new("CompositorNodeGlare")
gl.glare_type = "FOG_GLOW" if "FOG_GLOW" in [i.identifier for i in gl.bl_rna.properties["glare_type"].enum_items] else "BLOOM"
try: gl.quality = "HIGH"
except Exception: pass
for n, v in (("Threshold", 0.5), ("Strength", 0.35), ("Size", 0.45)):
    if n in gl.inputs: gl.inputs[n].default_value = v
add = nt.nodes.new("CompositorNodeMixRGB"); add.blend_type = "ADD"; add.inputs[0].default_value = 1.0
lens = nt.nodes.new("CompositorNodeLensdist")
if "Dispersion" in lens.inputs: lens.inputs["Dispersion"].default_value = 0.006
comp = nt.nodes.new("CompositorNodeComposite")
nt.links.new(rl.outputs["glow"], gl.inputs["Image"]); nt.links.new(rl.outputs["Image"], add.inputs[1])
nt.links.new(gl.outputs.get("Glare") or gl.outputs["Image"], add.inputs[2]); nt.links.new(add.outputs[0], lens.inputs["Image"]); nt.links.new(lens.outputs["Image"], comp.inputs["Image"])
# ---- runway markers: lit when lo < y < hi (emission mask on MarkerRed + the marker point lights) ----
mr = bpy.data.materials["MarkerRed"].node_tree; em = next(n for n in mr.nodes if n.bl_idname == "ShaderNodeEmission")
S0 = em.inputs["Strength"].default_value
def _n(t, **kw):
    x = mr.nodes.new(t)
    for k, v in kw.items(): setattr(x, k, v)
    return x
geo = _n("ShaderNodeNewGeometry"); sep = _n("ShaderNodeSeparateXYZ"); mr.links.new(geo.outputs["Position"], sep.inputs[0])
mk_lo = _n("ShaderNodeValue", name="mk_lo"); mk_hi = _n("ShaderNodeValue", name="mk_hi")
g1 = _n("ShaderNodeMath", operation="GREATER_THAN"); g2 = _n("ShaderNodeMath", operation="LESS_THAN"); g3 = _n("ShaderNodeMath", operation="MULTIPLY"); g4 = _n("ShaderNodeMath", operation="MULTIPLY")
mr.links.new(sep.outputs["Y"], g1.inputs[0]); mr.links.new(mk_lo.outputs[0], g1.inputs[1]); mr.links.new(sep.outputs["Y"], g2.inputs[0]); mr.links.new(mk_hi.outputs[0], g2.inputs[1])
mr.links.new(g1.outputs[0], g3.inputs[0]); mr.links.new(g2.outputs[0], g3.inputs[1]); mr.links.new(g3.outputs[0], g4.inputs[0]); g4.inputs[1].default_value = S0
mr.links.new(g4.outputs[0], em.inputs["Strength"])
MK = [(o, o.data.energy) for o in bpy.data.objects if o.type == "LIGHT" and o.name.startswith("Marker")]
_mk = [None]
def markers(lo, hi, boost=1.0):
    if _mk[0] == (lo, hi, boost): return
    mk_lo.outputs[0].default_value, mk_hi.outputs[0].default_value = lo, hi
    for o, e in MK: o.data.energy = e * boost if lo < o.matrix_world.translation.y < hi else 0.0
    _mk[0] = (lo, hi, boost)
# ---- helpers ----
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def lerp(a, b, t): return a + (b - a) * t
def stunt(s): sc.frame_set(int(math.floor(s)), subframe=s - math.floor(s))
def look_rot(loc, aim, up):
    z = -(aim - loc).normalized(); x = up.cross(z)
    if x.length < 1e-6: x = Vector((1, 0, 0))
    x.normalize(); y = z.cross(x); return Matrix((x, y, z)).transposed().to_quaternion()
cd = bpy.data.cameras.new("DraftCam"); cd.sensor_width = 36; cd.sensor_fit = "AUTO"; cd.dof.use_dof = True
camo = bpy.data.objects.new("DraftCam", cd); sc.collection.objects.link(camo); camo.rotation_mode = "QUATERNION"; sc.camera = camo
def set_cam(loc, aim, lens, fstop=4.0, up=Vector((0, 0, 1))):
    camo.location = loc; camo.rotation_quaternion = look_rot(loc, aim, up); cd.lens = lens
    cd.dof.focus_distance = (aim - loc).length; cd.dof.aperture_fstop = fstop
def show(h, on):
    if h.get("_on") == on: return
    for ob in [h["root"]] + list(h["root"].children_recursive): ob.hide_render = not on
    h["_on"] = on
def chest(h): return h["root"].matrix_world @ h["root"].pose.bones["chest"].head
for lo in [o for o in coll.objects if o.name.startswith("Rim_")]: bpy.data.objects.remove(lo)
RIM = {"stand": rim_for(stand, chest(stand) + Vector((0, -3, 0)), 1.0, 120.0), "seat": rim_for(seat, chest(seat) + Vector((0, 3, 0)), -1.0, 48.0)}
def rim_update(who, cam_loc):
    h = stand if who == "stand" else seat; side = 1.0 if who == "stand" else -1.0; lo = RIM[who]
    tgt = chest(h); back = flat(tgt - cam_loc); p = tgt + back * 2.2 + rotz(back, 90 * side) * 1.2 + Vector((0, 0, 1.3))
    lo.location = p; lo.rotation_quaternion = (tgt - p).to_track_quat("-Z", "Y")
def place_world(p, cam_world):
    """standing hero at a world spot on the ground: hips profile to the camera, chest + head turned to the loop"""
    p = Vector((p.x, p.y, 0.0)); uu = flat(LOOP_C - p)
    f = max((rotz(uu, a) for a in (75, -75)), key=lambda q: q.dot(flat(cam_world - p)))
    t = math.degrees(math.atan2(f.cross(uu).z, f.dot(uu)))
    r = stand["root"]; r.location = (0, 0, 0); r.rotation_euler = (0, 0, math.atan2(f.x, -f.y))
    H.pose_standing(r, torso_yaw=math.radians(t * 0.3), head_yaw=math.radians(t * 0.7)); r.location = (p.x, p.y, 0); vl.update()
    r.location.z = -H.lowest_z(stand) * SCALE; vl.update(); return p, uu, f
WHEEL = bpy.data.objects["SteeringWheel"]; W_TILT = WHEEL.rotation_euler.x; WHEEL.rotation_mode = "YXZ"; WHEEL.rotation_euler = (W_TILT, 0, 0)
def bbox_c(name, Minv):
    ob = bpy.data.objects[name]; c = sum((Vector(v) for v in ob.bound_box), Vector()) / 8.0; return Minv @ (ob.matrix_world @ c)
# ---- clip frame -> stunt frame ----
P10 = 2.553
def stunt_frame(f, sid, a, b):
    u = (f - a) / max(1, b - a)
    if sid == "S1": return 118.6 + 5.4 * u
    if sid in ("S2", "S3", "S4", "S5"): return 1.0
    if sid == "S6": return 10.0 + 35.0 * u
    if sid == "S7": return 45.0 + 30.0 * u
    if sid == "S8": return 75.0 + 37.0 * u
    if sid == "S9": return 112.0 + 3.6 * (f - 576) / 29.0 if f < 605 else 115.6 + 0.4 * (f - 605) / 29.0
    if sid == "S10": return 119.0 + 185.0 * (0.15 * u + 0.85 * u ** (P10 + 1) / (P10 + 1))   # jets on the drop hit, slow-mo ramping to real time
    if sid == "S11": return 191.0 + (f - 819) if f < 859 else 231.0 + 0.5 * (f - 859)       # touchdown (stunt 194) on 'hit' = clip 822
    if sid == "S12": return 258.5 + 0.4 * (f - 914)
    if sid == "S13": return 317.0 + 6.0 * u
    return 323.0 + 0.1 * (f - 1355)                                                       # S14: final exhale of the jets at 324
def beat_cuts(a, b, every=1, min_len=6):
    bs = [x for x in BEATS if a <= x < b][::every]; cuts = [a] + [x for x in bs if x - a >= min_len and b - x >= min_len] + [b]
    return sorted(set(cuts))
def sub_of(f, cuts):
    for k in range(len(cuts) - 1):
        if cuts[k] <= f < cuts[k + 1]: return k, (f - cuts[k]) / max(1, cuts[k + 1] - cuts[k])
    return len(cuts) - 2, 1.0
S4_CUTS = beat_cuts(249, 332); S13_CUTS = beat_cuts(1060, 1355, every=4, min_len=20)
S4_DET = [("TailBar", (0, -1), 35, 1.3, 0.15, 45), ("WFL_Rim", (-1, 0), 30, 1.1, 0.10, 40), ("LampLED", None, -30, 0.9, 0.10, 50),      # camera always outside: along
          ("Diffuser", (0, -1), -25, 1.2, 0.25, 40), ("Mirror", None, 40, 0.9, 0.10, 50), ("NoseBarLED", (0, 1), 15, 1.2, 0.25, 40)]         # the given axis or out from the car centre
# placements of the standing hero (only head and torso ever move; set once per placement)
car1 = car_M.copy(); S3_CAM = W((-1.75, -5.15, 1.05)); _a3 = math.radians(6); S3_AIM = W((-1.75 + math.sin(_a3) * 6, -5.15 + math.cos(_a3) * 6, 1.05 + math.tan(math.radians(1.0)) * 6))
stunt(300.0); CARF = rig.matrix_world.copy(); stunt(1.0)
PF = CARF @ Vector((-1.8, -0.8, 0.0)); PF.z = 0.0; UF = flat(LOOP_C - PF)
CAM13B = PF - UF * 3.4 + rotz(UF, -90) * 1.2 + Vector((0, 0, 1.25))
_place = [None]
def stand_at(key):
    if _place[0] == key: return
    if key == "start": place_stand((-2.16, -2.54, 0.0), cam_world=S3_CAM, look_loop=True)
    else: place_world(PF, CAM13B)
    _place[0] = key
def glow(f, base): return base * (0.75 + 0.5 * ENVV[min(f, len(ENVV) - 1)])
# ---- per-frame plan ----
def plan(f):
    sid, a, b = next(x for x in SHOTS if x[1] <= f < x[2]); u = (f - a) / max(1, b - a)
    s = stunt_frame(f, sid, a, b); stunt(s); M = rig.matrix_world.copy(); Minv = M.inverted(); Lm = lambda p: M @ Vector(p)
    car = M.translation.copy(); cup = M.to_3x3() @ Vector((0, 0, 1))
    st = dict(stand=None, seat=None, mk=(-1e4, 1e4, 1.0), expo=EXPO, wheel=0.0, sub="")
    if sid == "S1":                                       # hook: upside down at the loop top, jets, slow push-in from the side
        st["seat"] = 0.0; k = ease(u)
        cam = (car + Vector((-12.0 + 3.0 * k, -1.0 + 0.4 * k, -3.5 + 0.5 * k)), car + Vector((0, 0, -0.3)), 35, 5.6, None)
    elif sid == "S2":                                     # markers light one pair per beat from the camera outwards; the scene comes up out of the dark
        k = sum(1 for x in BEATS if 72 <= x <= f); st["mk"] = (12.0, 12.0 + 12.0 * k, 3.0) if k > 0 else (0.0, 0.0, 3.0)   # along the right row; brighter so the car catches the red
        st["expo"] = lerp(-1.5, EXPO, ease((f - 72) / (128 - 72)))
        cam = (Vector((31.5, 4.0 + 1.2 * u, 0.30)), Vector((22.0, 45.0, 1.5)), 24, 8.0, None)
    elif sid in ("S3", "S4"):
        stand_at("start")
        if sid == "S3":                                   # assembles from particles beside the car (S3n framing, slow push-in)
            st["stand"] = lerp(1.1, 0.0, ease((f - 140) / (200 - 140)))
            d = (S3_AIM - S3_CAM).normalized(); k = 0.2 * ease(u); cam = (S3_CAM + d * k, S3_AIM + d * k, 26, 4.0, None)
        else:                                             # car details on the beats
            st["stand"] = 0.0; k, v = sub_of(f, S4_CUTS); name, dirl, ang, dist, dz, ln = S4_DET[k % len(S4_DET)]
            c = bbox_c(name, Minv); dv = rotz(Vector((dirl[0], dirl[1], 0)) if dirl else Vector((c.x, c.y, 0)).normalized(), ang); side = rotz(dv, 90)
            loc = c + dv * dist + Vector((0, 0, dz)) + side * lerp(-0.10, 0.10, v); st["sub"] = name
            cam = (Lm(loc), Lm(c), ln, 2.0, None)
    elif sid == "S5":                                     # cabin through the windshield, the wheel turns by itself
        st["seat"] = 0.0; st["wheel"] = math.radians(28) * math.sin(2 * math.pi * (f - 332) / 54.0)
        loc, aim = Lm((-1.15, 3.5, 1.55)), Lm((0.0, Y_HIP - 0.12, 0.70)); cam = (loc + (aim - loc).normalized() * 0.35 * ease(u), aim, 46, 2.8, None)
    elif sid == "S6":                                     # launch: low behind, the loop ahead in the fog
        st["seat"] = 0.0; cam = (car1 @ Vector((0.55, -6.5, 0.35)), Vector((25.5, 58.0, 6.0)), 26, 8.0, None)
    elif sid == "S7":                                     # bass dropout: high wide
        st["seat"] = 0.0; cam = (Vector((5.5, 33.0 + 2.0 * u, 15.0)), Vector((24.5, 54.0, 3.5)), 24, 11.0, None)
    elif sid == "S8":                                     # loop entry: locked to the car, the world turns over
        st["seat"] = 0.0
        if f < 536: cam = (Lm((0.0, -5.2, 2.0)), Lm((0.0, 4.0, 0.5)), 26, 8.0, cup); st["sub"] = "chase"
        else: cam = (Lm((-1.15, 3.5, 1.55)), Lm((0.0, Y_HIP - 0.12, 0.70)), 40, 4.0, cup); st["sub"] = "windshield"
    elif sid == "S9":                                     # hangs upside down, near freeze; hero calm behind the glass (world-up camera)
        st["seat"] = 0.0; y = lerp(3.8, 3.3, ease(u)); cam = (Lm((-0.9, y, 1.45)), Lm((0.0, Y_HIP - 0.10, 0.75)), 40, 4.0, None)
    elif sid == "S10":                                    # jets + roll, slow-mo ramping up
        st["seat"] = 0.0
        if f < 726: cam = (car + Vector((-8.5, 2.0, 0.8)), car, 30, 8.0, None); st["sub"] = "side"
        else: cam = (Vector((car.x - 6.5, car.y - 11.0, max(0.6, car.z - 4.0))), car, 28, 8.0, None); st["sub"] = "front-low"
    elif sid == "S11":                                    # touchdown on 'hit', slide to the stop; camera jolt
        st["seat"] = 0.0; j = 0.035 * math.exp(-max(0, f - 822) / 5.0) * (1 if f >= 822 else 0)
        loc = Vector((18.0, 13.5, 0.45)) + Vector((math.sin(f * 2.7), 0, math.cos(f * 3.1))) * j
        cam = (loc, car + Vector((0, 0, 0.5)), 45, 8.0, None)
    elif sid == "S12":                                    # orbit, stopping by ~42 s
        st["seat"] = 0.0; ang = math.radians(66 + 204 * ease((f - 914) / (1008 - 914)) + 3.0 * clamp((f - 1008) / 52.0))
        loc = car + Vector((math.cos(ang), math.sin(ang), 0)) * 5.5 + Vector((0, 0, 1.45)); cam = (loc, car + Vector((0, 0, 0.55)), 30, 5.6, None)
    elif sid == "S13":                                    # dissolve in the cabin, reassembly outside, beauty shots every 4 beats
        k, v = sub_of(f, S13_CUTS); a1, b1 = S13_CUTS[k], S13_CUTS[k + 1]
        if k == 0:
            st["seat"] = lerp(0.0, 1.1, ease((f - a1 - 4) / (b1 - a1 - 10))); st["sub"] = "cabin dissolve"
            loc, aim = Lm((-1.15, 3.5, 1.55)), Lm((0.0, Y_HIP - 0.12, 0.70)); cam = (loc + (aim - loc).normalized() * 0.2 * v, aim, 46, 2.8, None)
        else:
            stand_at("final"); ch = chest(stand)
            if k == 1:
                st["stand"] = lerp(1.1, 0.0, ease((f - a1 - 2) / (b1 - a1 - 10))); st["sub"] = "reassembly"
                cam = (CAM13B + (ch - CAM13B).normalized() * 0.3 * v, ch + Vector((0, 0, 0.15)), 32, 4.0, None)
            elif k == 2:
                st["stand"] = 0.0; st["sub"] = "over-shoulder to the loop"
                loc = ch - UF * 1.25 + rotz(UF, -90) * 0.45 + Vector((0, 0, 0.35 + 0.1 * v)); cam = (loc, LOOP_C + Vector((0, 0, -2.0)), 30, 5.6, None)
            elif k == 3:
                st["stand"] = 0.0; st["sub"] = "wide low, loop in smoke"
                loc = PF - UF * 9.0 + rotz(UF, 90) * 3.0 + Vector((0, 0, 0.4)) + rotz(UF, -90) * 0.8 * v; cam = (loc, PF + UF * 20 + Vector((0, 0, 5.0)), 24, 11.0, None)
            elif k == 4:
                st["stand"] = 0.0; st["sub"] = "red stripe"
                c = bbox_c("TailBar", Minv); loc = Lm(c + rotz(Vector((0, -1, 0)), -35) * 1.0 + Vector((0, 0, 0.12)) + Vector((0.12, 0, 0)) * lerp(-1, 1, v))
                cam = (loc, Lm(c), 55, 2.0, None)
            else:
                st["stand"] = 0.0; st["sub"] = "silhouette"                     # low, from behind: the hero against the glowing loop
                loc = PF - UF * 3.2 + rotz(UF, -90) * 0.9 + Vector((0, 0, 0.35 + 0.1 * v)); cam = (loc, ch + UF * 2.0 + Vector((0, 0, 1.0)), 28, 5.6, None)
    else:                                                 # S14: markers out in reverse, the hero scatters upwards
        stand_at("final"); ch = chest(stand); f_h = flat(stand["root"].matrix_world.to_3x3() @ Vector((0, -1, 0)))
        st["stand"] = lerp(0.0, 1.1, ease((f - 1380) / (CARD - 1380)))
        k = sum(1 for x in BEATS if 1355 <= x <= f); st["mk"] = (-1e4, 66.0 - 12.0 * k, 1.0) if k > 0 else (-1e4, 1e4, 1.0)
        loc = PF + rotz(f_h, -30) * 3.4 + Vector((0, 0, 1.0 + 0.3 * u)); cam = (loc, ch + Vector((0, 0, 0.35 + 0.15 * u)), 35, 4.0, None)
    return sid, s, cam, st
# ---- render loop ----
def frames_sel():
    if SEL == "all": return list(range(0, 1500))
    if "-" in SEL and "," not in SEL: x, y = SEL.split("-"); return list(range(int(x), int(y) + 1))
    return [int(x) for x in SEL.split(",")]
todo = [f for f in frames_sel() if f not in BLACK and f <= CARD + 12]      # the card fades to black by CARD+12
def _ok(fp): return os.path.exists(fp) and os.path.getsize(fp) > 2000
done0 = sum(1 for f in todo if _ok(os.path.join(OUTD, f"f_{f:04d}.png")))
log(f"DRAFT start: {len(todo)} frames ({done0} already done), {SAMP} spp, {1080 * PCT // 100}x{1920 * PCT // 100} -> {OUTD}")
t_all = time.time(); n = 0; last_sid = None
for f in todo:
    fp = os.path.join(OUTD, f"f_{f:04d}.png")
    if _ok(fp): continue
    t0 = time.time(); sid, s, (loc, aim, ln, fs, up), st = plan(f)
    for who, h in (("stand", stand), ("seat", seat)):
        on = st[who] is not None; show(h, on); RIM[who].hide_render = not on
        if on: H.set_state(h, dissolve=st[who], glow=glow(f, 1.15 if who == "stand" else 1.0))
    markers(*st["mk"]); sc.view_settings.exposure = st["expo"]; WHEEL.rotation_euler = (W_TILT, st["wheel"], 0)
    set_cam(loc, aim, ln, fs, up if up is not None else Vector((0, 0, 1)))
    for who in ("stand", "seat"):
        if st[who] is not None: rim_update(who, loc)
    vl.update(); sc.render.filepath = fp; bpy.ops.render.render(write_still=True); n += 1
    dt = time.time() - t0
    if sid != last_sid or n % 10 == 0 or f == todo[-1]:
        log(f"DRAFT f={f:04d} {sid} {st['sub']} s={s:.2f} {dt:.1f}s/frame  [{n} new, {(time.time() - t_all) / 60:.1f} min]")
    last_sid = sid
log(f"DRAFT_DONE {n} frames in {(time.time() - t_all) / 60:.1f} min")
