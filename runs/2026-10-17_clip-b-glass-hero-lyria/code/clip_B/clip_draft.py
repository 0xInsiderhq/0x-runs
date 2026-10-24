"""clip_B stage 2: draft clip, shots S1-S14 per timing.json on the stunt_v2 scene, low samples -> draft_frames/f_0000.png (resumable).
Clip frame f (0-based, 24 fps) -> stunt frame s (float, sub-frame evaluation for the slow-mo), per-shot camera, hero state, markers.
Frames 59-71 (cut to black) and the final card are made in the assembly step, not here.
usage: blender -b --python clip_draft.py -- [all | a-b | f1,f2,...] [samples] [percent]"""
import bpy, bmesh, sys, os, math, json, time, random
from mathutils import Vector, Matrix, Quaternion
C = os.path.dirname(os.path.abspath(__file__))
a0 = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SEL = a0[0] if a0 else "all"; SAMP = int(a0[1]) if len(a0) > 1 else 16; PCT = int(a0[2]) if len(a0) > 2 else 50
OUTD = os.environ.get("DRAFT_OUT", os.path.join(C, "draft_frames")); os.makedirs(OUTD, exist_ok=True)
PLOG = os.path.join(C, "progress.log")
WARM = os.environ.get("DRAFT_WARMUP") == "1"              # timing runs: a 1-spp render first (sync, BVH), then the timed one
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
BLACK = range(59, 60)                       # the white flash on the first beat is made in the assembly step (no cut to black any more)
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
MK1 = next(o.matrix_world.translation.copy() for o, e in MK if abs(o.matrix_world.translation.x - 30.6) < 0.2 and abs(o.matrix_world.translation.y - 66.0) < 0.2)   # S2: the flash point
_mk = [None]
def markers(lo, hi, boost=1.0, emit=1.0):
    if _mk[0] == (lo, hi, boost, emit): return
    mk_lo.outputs[0].default_value, mk_hi.outputs[0].default_value = lo, hi; g4.inputs[1].default_value = S0 * emit
    for o, e in MK: o.data.energy = e * boost if lo < o.matrix_world.translation.y < hi else 0.0
    _mk[0] = (lo, hi, boost, emit)
# ---- helpers ----
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def lerp(a, b, t): return a + (b - a) * t
def bez(p0, p1, p2, p3, t): q_ = 1 - t; return p0 * q_ ** 3 + p1 * (3 * t * q_ * q_) + p2 * (3 * t * t * q_) + p3 * t ** 3
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
    if sid == "S10": u = max(0.0, u); return 119.0 + 185.0 * (0.15 * u + 0.85 * u ** (P10 + 1) / (P10 + 1))   # jets on the drop hit, slow-mo ramping to real time
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
S4_CUTS = [249, min(BEATS, key=lambda x: abs(x - 276)), min(BEATS, key=lambda x: abs(x - 304)), 332]; S13_CUTS = beat_cuts(1060, 1355, every=4, min_len=20)
S4_DET = [("TailBar", (0, -1), 35, 1.3, 0.15, 45), ("WFL_Rim", (-1, 0), 30, 1.1, 0.10, 40), ("LampLED", None, -30, 0.9, 0.10, 50),      # camera always outside: along
          ("Diffuser", (0, -1), -25, 1.2, 0.25, 40), ("Mirror", None, 40, 0.9, 0.10, 50), ("NoseBarLED", (0, 1), 15, 1.2, 0.25, 40)]         # the given axis or out from the car centre
# ==== v2 effects: S2 car back light, S4 tail wave / side sweep / wheel spin-up, S5 wheel mark, leg glow, vapour trails, S11 drift + smoke + sparks ====
CAR_OBS = [o for o in bpy.data.objects["CarRoot"].children_recursive if o.type == "MESH" and o.name not in coll.objects]
def _linked_light(name, kind, energy, color, **kw):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = color
    for k, v in kw.items(): setattr(ld, k, v)
    lo = bpy.data.objects.new(name, ld); sc.collection.objects.link(lo); lo.rotation_mode = "QUATERNION"; lo.visible_camera = False; lo.hide_render = True
    rc = bpy.data.collections.new(name + "_recv")
    for o in CAR_OBS: rc.objects.link(o)
    lo.light_linking.receiver_collection = rc
    for i in range(len(rc.objects)): rc.collection_objects[i].light_linking.link_state = "INCLUDE"
    return lo
CAR_RIM = _linked_light("CarRim", "AREA", 900.0, (0.82, 0.88, 1.0), size=2.5)                                    # S2: back light, the body reads against the fog
SWEEP = _linked_light("SideSweep", "AREA", 400.0, (1.0, 0.97, 0.92), shape="RECTANGLE", size=0.06, size_y=1.3)   # S4b: a band of light runs along the side
# S4a: the red tail stripe lights up as a wave from left to right (object-space x of the bar)
TB = bpy.data.objects["TailBar"]; _tn = TB.material_slots[0].material.node_tree
TB_X = (min(v[0] for v in TB.bound_box), max(v[0] for v in TB.bound_box))
_tco = _tn.nodes.new("ShaderNodeTexCoord"); _tsx = _tn.nodes.new("ShaderNodeSeparateXYZ"); _tn.links.new(_tco.outputs["Object"], _tsx.inputs[0])
TWAVE = _tn.nodes.new("ShaderNodeValue"); TWAVE.name = "tail_wave"; TWAVE.outputs[0].default_value = 1e3
_tsub = _tn.nodes.new("ShaderNodeMath"); _tsub.operation = "SUBTRACT"; _tn.links.new(TWAVE.outputs[0], _tsub.inputs[0]); _tn.links.new(_tsx.outputs["X"], _tsub.inputs[1])
_tmr = _tn.nodes.new("ShaderNodeMapRange"); _tmr.interpolation_type = "SMOOTHSTEP"; _tmr.inputs["From Min"].default_value = -0.04; _tmr.inputs["From Max"].default_value = 0.04
_tn.links.new(_tsub.outputs[0], _tmr.inputs["Value"])
_tout = next(n for n in _tn.nodes if n.bl_idname == "ShaderNodeOutputMaterial"); _tsrc = _tout.inputs["Surface"].links[0].from_socket
_tdk = _tn.nodes.new("ShaderNodeBsdfPrincipled"); _tdk.inputs["Base Color"].default_value = (0.06, 0.005, 0.005, 1); _tdk.inputs["Roughness"].default_value = 0.25
_tmx = _tn.nodes.new("ShaderNodeMixShader"); _tn.links.new(_tmr.outputs["Result"], _tmx.inputs[0]); _tn.links.new(_tdk.outputs[0], _tmx.inputs[1])
_tn.links.new(_tsrc, _tmx.inputs[2]); _tn.links.new(_tmx.outputs[0], _tout.inputs["Surface"])
TG = bpy.data.objects["TailGlow"]; TG_E = TG.data.energy; _tl = [None]
def tail_set(w):
    w = 1e3 if w is None else w
    if _tl[0] == w: return
    TWAVE.outputs[0].default_value = w; TG.data.energy = TG_E * clamp((w - TB_X[0]) / (TB_X[1] - TB_X[0])); _tl[0] = w
# S4c: the front-right wheel spins up on the spot (its stunt key curve muted meanwhile)
WSP = bpy.data.objects["WFR_Spin"]; _wfc = WSP.animation_data.action.fcurves[0]; WSP_BASE = _wfc.evaluate(1.0)
def wheel_spin(ang):
    if ang is None:
        if _wfc.mute: _wfc.mute = False
        return
    _wfc.mute = True; WSP.rotation_euler[0] = WSP_BASE - ang                      # forward rolling = decreasing angle
# S5: a light 12-o'clock mark on the steering wheel rim so its turning reads
_wme = bpy.data.meshes.new("WheelMark"); _bm = bmesh.new(); bmesh.ops.create_cube(_bm, size=1.0)
for v in _bm.verts: v.co = Vector((v.co.x * 0.036, v.co.y * 0.03, v.co.z * 0.024))
_bm.to_mesh(_wme); _bm.free()
_wmm = bpy.data.materials.new("WheelMarkMat"); _wmm.use_nodes = True; _wp = _wmm.node_tree.nodes["Principled BSDF"]
_wp.inputs["Base Color"].default_value = (0.85, 0.82, 0.75, 1); _wp.inputs["Roughness"].default_value = 0.35; _wme.materials.append(_wmm)
_wp.inputs["Emission Color"].default_value = (1.0, 0.85, 0.6, 1); _wp.inputs["Emission Strength"].default_value = 4.0       # shift-light strip at 12 o'clock
WMARK = bpy.data.objects.new("WheelMark", _wme); coll.objects.link(WMARK); WMARK.parent = WHEEL; WMARK.location = (0.0, -0.004, 0.158)
# legs glow at ~55 % of the chest (thighs, shins, pelvis), head stays ~35 %: the whole figure reads
LEG_GLOW = 0.55
def _leg_glow(h):
    arm = h["root"]; nt = h["core"].data.materials[0].node_tree
    mxh = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeMath" and n.operation == "MAXIMUM" and n.inputs[1].is_linked
               and n.inputs[1].links[0].from_node.bl_idname == "ShaderNodeMapRange" and abs(n.inputs[1].links[0].from_node.inputs["To Min"].default_value - 0.35) < 1e-3)
    outs = [l.to_socket for l in mxh.outputs[0].links]; cur = mxh.outputs[0]
    for bone, rad in (("hips", 0.24), ("thigh.L", 0.25), ("thigh.R", 0.25), ("shin.L", 0.27), ("shin.R", 0.27)):
        if bone not in arm.data.bones: print("leg glow: no bone", bone, flush=True); continue
        b = arm.data.bones[bone]; e = bpy.data.objects.new(f"{arm.name}_glow_{bone}", None); coll.objects.link(e)
        e.parent = arm; e.parent_type = "BONE"; e.parent_bone = bone; e.location = (0.0, -0.5 * b.length, 0.0)   # bone parent sits at the tail: mid-bone
        tc = nt.nodes.new("ShaderNodeTexCoord"); tc.object = e
        ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = "LENGTH"; nt.links.new(tc.outputs["Object"], ln.inputs[0])
        mq = nt.nodes.new("ShaderNodeMapRange"); mq.interpolation_type = "SMOOTHSTEP"
        for k, v in (("From Min", 0.03), ("From Max", rad), ("To Min", LEG_GLOW), ("To Max", 0.0)): mq.inputs[k].default_value = v
        nt.links.new(ln.outputs["Value"], mq.inputs["Value"])
        mm = nt.nodes.new("ShaderNodeMath"); mm.operation = "MAXIMUM"; nt.links.new(cur, mm.inputs[0]); nt.links.new(mq.outputs["Result"], mm.inputs[1]); cur = mm.outputs[0]
    for so in outs: nt.links.new(cur, so)
for h in (stand, seat): _leg_glow(h)
# S10 vapour: every point drags a trail of copies along its own path (dense at the nozzle, widening, fading), instead of separate puffs
VTRAIL = {0: (0.04, 6), 1: (0.08, 6), 2: (0.15, 5), 3: (0.25, 4)}                # per age bin: trail length (story s), copies
for i in range(4):
    ng = bpy.data.node_groups[f"VaporGN{i}"]; Nn, Lk = ng.nodes, ng.links
    m2p = next(n for n in Nn if n.bl_idname == "GeometryNodeMeshToPoints"); dg = next(n for n in Nn if n.bl_idname == "GeometryNodeDeleteGeometry")
    agen = next(n for n in Nn if n.bl_idname == "ShaderNodeMath" and n.operation == "SUBTRACT" and n.inputs[0].is_linked and n.inputs[0].links[0].from_node.name == "time")
    tl_, K = VTRAIL[i]
    dup = Nn.new("GeometryNodeDuplicateElements"); dup.domain = "POINT"; dup.inputs["Amount"].default_value = K
    Lk.new(m2p.outputs[0], dup.inputs["Geometry"]); Lk.new(dup.outputs["Geometry"], dg.inputs["Geometry"])
    k1 = Nn.new("ShaderNodeMath"); k1.operation = "MULTIPLY"; Lk.new(dup.outputs["Duplicate Index"], k1.inputs[0]); k1.inputs[1].default_value = tl_ / max(1, K - 1)
    k2 = Nn.new("ShaderNodeMath"); k2.operation = "SUBTRACT"; Lk.new(agen.outputs[0], k2.inputs[0]); Lk.new(k1.outputs[0], k2.inputs[1])
    k3 = Nn.new("ShaderNodeMath"); k3.operation = "MAXIMUM"; Lk.new(k2.outputs[0], k3.inputs[0]); k3.inputs[1].default_value = 0.0
    for l in list(agen.outputs[0].links):
        if l.to_node == k2 or (l.to_node.bl_idname == "ShaderNodeMath" and l.to_node.operation in ("LESS_THAN", "GREATER_THAN")): continue
        to = l.to_socket; Lk.remove(l); Lk.new(k3.outputs[0], to)
for n in bpy.data.materials["Vapor"].node_tree.nodes:                            # softer billows: fewer holes, no cotton-ball clumps
    if n.bl_idname == "ShaderNodeMapRange" and abs(n.inputs["From Min"].default_value - 0.36) < 1e-3:
        n.inputs["From Min"].default_value = 0.26; n.inputs["To Min"].default_value = 0.25; n.inputs["To Max"].default_value = 1.5
# dense directional jets at the nozzles (children of the car body, so they get motion blur), on top of the world-space vapour cloud
NOZ = {"LF": (-0.93, 0.62, 0.24), "LR": (-0.93, -0.92, 0.24), "RF": (0.93, 0.62, 0.24), "RR": (0.93, -0.92, 0.24)}       # traj.NOZZLES, car frame
JPULSE = [(119, 9.6, ("LF_up", "LR_up")), (139, 7.2, ("LF_dn", "RF_dn")), (157, 9.6, ("RF_up", "RR_up")), (175, 4.3, ("LR_dn", "RR_dn")),   # events.txt (stunt frames)
          (179, 6.0, ("LF_dn", "RF_dn", "LR_dn", "RR_dn")), (187, 4.8, ("LF_dn", "RF_dn", "LR_dn", "RR_dn")), (324, 7.2, ("LF_up", "RF_up", "LR_up", "RR_up"))]
def _jet_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); m.cycles.volume_step_rate = 0.25
    N = nt.nodes.new; o = N("ShaderNodeOutputMaterial"); tc = N("ShaderNodeTexCoord"); sp = N("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sp.inputs[0])
    g = N("ShaderNodeValue"); g.name = "gas"; jt = N("ShaderNodeValue"); jt.name = "jt"
    def Mth(op, a, b, clamp=False):
        x = N("ShaderNodeMath"); x.operation = op; x.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if hasattr(v, "is_output"): nt.links.new(v, x.inputs[i])
            else: x.inputs[i].default_value = v
        return x.outputs[0]
    xy = N("ShaderNodeVectorMath"); xy.operation = "MULTIPLY"; nt.links.new(tc.outputs["Object"], xy.inputs[0]); xy.inputs[1].default_value = (1.0, 1.0, 0.0)
    rr = N("ShaderNodeVectorMath"); rr.operation = "LENGTH"; nt.links.new(xy.outputs[0], rr.inputs[0])
    z = sp.outputs["Z"]; width = Mth("ADD", Mth("MULTIPLY", z, 0.39), 0.03)                                  # cone radius 3 cm at the nozzle -> 42 cm
    radial = Mth("POWER", Mth("SUBTRACT", 1.0, Mth("DIVIDE", rr.outputs["Value"], width), clamp=True), 1.5)
    along = Mth("POWER", Mth("SUBTRACT", 1.0, z, clamp=True), 1.6)                                          # dense at the nozzle, thins out along the jet
    st_ = N("ShaderNodeVectorMath"); st_.operation = "MULTIPLY"; nt.links.new(tc.outputs["Object"], st_.inputs[0]); st_.inputs[1].default_value = (6.0, 6.0, 1.6)
    nz = N("ShaderNodeTexNoise"); nz.noise_dimensions = "4D"; nz.inputs["Scale"].default_value = 2.0; nz.inputs["Detail"].default_value = 4.0; nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(st_.outputs[0], nz.inputs["Vector"]); nt.links.new(Mth("MULTIPLY", jt.outputs[0], 0.35), nz.inputs["W"])       # streaks stretched along the jet
    mq = N("ShaderNodeMapRange")
    for k, v in (("From Min", 0.3), ("From Max", 0.75), ("To Min", 0.35), ("To Max", 1.4)): mq.inputs[k].default_value = v
    nt.links.new(nz.outputs["Fac"], mq.inputs["Value"])
    d = Mth("MULTIPLY", Mth("MULTIPLY", Mth("MULTIPLY", radial, along), mq.outputs["Result"]), Mth("MULTIPLY", g.outputs[0], 9.0))
    v = N("ShaderNodeVolumePrincipled"); nt.links.new(d, v.inputs["Density"]); v.inputs["Color"].default_value = (0.94, 0.95, 0.97, 1)
    v.inputs["Anisotropy"].default_value = 0.35; v.inputs["Emission Strength"].default_value = 0.0; nt.links.new(v.outputs[0], o.inputs["Volume"])
    return m, g.outputs[0], jt.outputs[0]
JCONE = {}
for k, p in NOZ.items():
    for up in (True, False):
        nm = f"{k}_{'up' if up else 'dn'}"; dv = Vector((0.45 * (-1 if k[0] == "L" else 1), 0.0, 1.0 if up else -1.0)).normalized()
        bm_ = bmesh.new(); cc_ = bmesh.ops.create_cone(bm_, cap_ends=True, segments=20, radius1=0.03, radius2=0.42, depth=1.0)
        for vv in cc_["verts"]: vv.co.z += 0.5
        me_ = bpy.data.meshes.new("JetStream_" + nm); bm_.to_mesh(me_); bm_.free()
        mat_, gs_, jt_ = _jet_mat("JetStream_" + nm); me_.materials.append(mat_)
        ob = bpy.data.objects.new("JetStream_" + nm, me_); coll.objects.link(ob); ob.parent = rig; ob.visible_shadow = False; ob.hide_render = True
        ob.location = Vector(p) + dv * 0.03; ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = dv.to_track_quat("Z", "Y")
        JCONE[nm] = (ob, gs_, jt_)
def _gas(nm, s):
    g = 0.0
    for s0, du, names in JPULSE:
        if nm not in names or s < s0: continue
        tau = 5.0 if s0 > 300 else 2.5
        g = max(g, min(1.0, (s - s0) / 0.6) if s <= s0 + du else math.exp(-(s - s0 - du) / tau))
    return g
def jets_set(s):
    for nm, (ob, gs_, jt_) in JCONE.items():
        g = _gas(nm, s); on = g > 0.01; ob.hide_render = not on
        if on: gs_.default_value = g; jt_.default_value = s; ob.scale = (1.0, 1.0, 0.35 + 1.15 * g ** 0.5)
# S1 2.0-2.44 s: the nozzles start to glow (emissive cores + lights), feeding the bloom that grows into the white flash
_cm = bpy.data.materials.new("JetCoreGlow"); _cm.use_nodes = True; _cn = _cm.node_tree; _cn.nodes.clear()
_cout = _cn.nodes.new("ShaderNodeOutputMaterial"); _cem = _cn.nodes.new("ShaderNodeEmission"); _cem.inputs["Color"].default_value = (0.92, 0.96, 1.0, 1)
CORE_K = _cn.nodes.new("ShaderNodeValue"); CORE_K.name = "core_k"
_cmu = _cn.nodes.new("ShaderNodeMath"); _cmu.operation = "MULTIPLY"; _cn.links.new(CORE_K.outputs[0], _cmu.inputs[0]); _cmu.inputs[1].default_value = 120.0
_cn.links.new(_cmu.outputs[0], _cem.inputs["Strength"]); _cn.links.new(_cem.outputs[0], _cout.inputs["Surface"])
_cao = _cn.nodes.new("ShaderNodeOutputAOV"); _cao.aov_name = "glow"; _cvs = _cn.nodes.new("ShaderNodeVectorMath"); _cvs.operation = "SCALE"
_cvs.inputs[0].default_value = (6.0, 6.2, 6.5); _cn.links.new(CORE_K.outputs[0], _cvs.inputs["Scale"]); _cn.links.new(_cvs.outputs[0], _cao.inputs["Color"])
JCORE = {}
for nm, (ob_, gs_, jt_) in JCONE.items():
    bm_ = bmesh.new(); cc_ = bmesh.ops.create_cone(bm_, cap_ends=True, segments=16, radius1=0.025, radius2=0.06, depth=0.35)
    for vv in cc_["verts"]: vv.co.z += 0.175
    me_ = bpy.data.meshes.new("JetCore_" + nm); bm_.to_mesh(me_); bm_.free(); me_.materials.append(_cm)
    ob = bpy.data.objects.new("JetCore_" + nm, me_); coll.objects.link(ob); ob.parent = rig; ob.visible_shadow = False; ob.hide_render = True
    ob.location = ob_.location.copy(); ob.rotation_mode = "QUATERNION"; ob.rotation_quaternion = ob_.rotation_quaternion.copy()
    ld = bpy.data.lights.new("JetCoreL_" + nm, "POINT"); ld.color = (0.9, 0.95, 1.0); ld.shadow_soft_size = 0.05; ld.energy = 0.0
    lo = bpy.data.objects.new("JetCoreL_" + nm, ld); coll.objects.link(lo); lo.parent = rig; lo.hide_render = True
    lo.location = ob_.location + (ob_.rotation_quaternion @ Vector((0.0, 0.0, 0.2)))
    JCORE[nm] = (ob, lo)
_ck = [None]
def cores_set(k, s):
    key = (round(k, 4), round(s, 3)) if k > 0 else 0
    if _ck[0] == key: return
    CORE_K.outputs[0].default_value = k * k
    for nm, (ob, lo) in JCORE.items():
        on = k > 0.001 and _gas(nm, s) > 0.3; ob.hide_render = not on; lo.hide_render = not on
        if on: lo.data.energy = 80.0 * k * k                                     # soft: the body panel must not blow out before the flash
    _ck[0] = key
# S11 drift: after the touchdown the car slides sideways braking, spins a full turn and stops in the stunt's own final pose (S12-S14 unchanged).
# Keys on a copy of CarRoot's action at the stunt frames the clip frames map to, so motion blur sees the real motion.
CR = bpy.data.objects["CarRoot"]; _a0 = CR.animation_data.action; _a1 = _a0.copy(); _a1.name = "CarRootDrift"
F0 = {(fc.data_path, fc.array_index): fc for fc in _a0.fcurves}; F1 = {(fc.data_path, fc.array_index): fc for fc in _a1.fcurves}
D0, D1, DS = 194.0, 249.0, 231.0                                                # touchdown, end of the slide, the stunt's stop (stunt frames)
def _o_loc(q): return Vector([F0[("location", i)].evaluate(q) for i in range(3)])
def _o_rot(q): return Quaternion([F0[("rotation_quaternion", i)].evaluate(q) for i in range(4)]).normalized()
def _yaw(u):                                                                    # turns of yaw: sideways fast, a braking slide, then round to the original heading
    if u < 0.18: return 0.25 * ease(u / 0.18)
    if u < 0.55: return 0.25 + 0.17 * (u - 0.18) / 0.37
    x = (u - 0.55) / 0.45; return 0.42 + 0.58 * (1 - (1 - x) ** 2.2)
DRIFT = []; _qp = None
for f in range(822, 896):
    s_ = stunt_frame(f, "S11", 819, 914); uc = (f - 822) / (895 - 822); q = D0 + (DS - D0) * (1 - (1 - uc) ** 3)
    d = flat(_o_loc(min(q + 0.5, DS - 0.1)) - _o_loc(min(q, DS - 0.6) - 0.5))
    p = _o_loc(q) + rotz(d, 90) * (1.3 * math.sin(math.pi * uc)); p.z = _o_loc(q).z
    rq = Quaternion((0, 0, 1), 2 * math.pi * _yaw(uc)) @ _o_rot(q)
    if _qp is not None and rq.dot(_qp) < 0: rq = -rq
    _qp = rq; DRIFT.append((f, s_, p, rq))
for key in [("location", 0), ("location", 1)] + [("rotation_quaternion", i) for i in range(4)]:
    fc = F1[key]
    for kp in reversed(list(fc.keyframe_points)):
        if D0 < kp.co[0] <= D1 + 1e-3: fc.keyframe_points.remove(kp)
    if key[0] == "rotation_quaternion":                                          # a full turn takes q to -q: later keys flipped to stay continuous
        for kp in fc.keyframe_points:
            if kp.co[0] > D1: kp.co[1] = -kp.co[1]; kp.handle_left[1] = -kp.handle_left[1]; kp.handle_right[1] = -kp.handle_right[1]
    for f, s_, p, rq in DRIFT:
        if s_ <= D0 + 1e-6: continue
        kp = fc.keyframe_points.insert(s_, p[key[1]] if key[0] == "location" else rq[key[1]], options={"FAST"}); kp.interpolation = "LINEAR"
    fc.update()
CR.animation_data.action = _a1
if hasattr(CR.animation_data, "action_slot") and CR.animation_data.action_slot is None and len(_a1.slots): CR.animation_data.action_slot = _a1.slots[0]
DP = {f: p for f, s_, p, rq in DRIFT}; DM = {f: Matrix.Translation(p) @ rq.to_matrix().to_4x4() for f, s_, p, rq in DRIFT}
WHL = {n: bpy.data.objects[n + "_Hub"].matrix_local.translation.copy() for n in ("WFL", "WFR", "WRL", "WRR")}
# tyre smoke: puffs left at the wheels along the slide (the stunt's dust material, lighter)
_dm = bpy.data.materials["Dust"].copy(); _dm.name = "TireSmoke"
for n in _dm.node_tree.nodes:
    if n.bl_idname == "ShaderNodeVolumePrincipled": n.inputs["Color"].default_value = (0.80, 0.80, 0.82, 1)
_smm = bpy.data.meshes.new("SmokePuff"); _bm = bmesh.new(); bmesh.ops.create_icosphere(_bm, subdivisions=2, radius=1.0); _bm.to_mesh(_smm); _bm.free(); _smm.materials.append(_dm)
_rs = random.Random(5); SMOKE = []
for f, s_, p, rq in DRIFT[1::2]:
    if f > 888: break
    for wn, kk in (("WRL", 1.0), ("WRR", 1.0), ("WFL", 0.5), ("WFR", 0.5)):
        if kk < 1 and f < 830: continue
        c = DM[f] @ WHL[wn]; c.z = 0.12
        ob = bpy.data.objects.new(f"Smoke{len(SMOKE):03d}", _smm); coll.objects.link(ob); ob.visible_shadow = False
        ob["seed"] = _rs.uniform(0, 100); ob["dens"] = 0.0; ob.hide_render = True
        SMOKE.append((ob, f, c, kk, Vector((_rs.gauss(0, 0.3), _rs.gauss(0, 0.3), 0.25))))
_sm_on = [True]
def smoke_set(f):
    act = 819 <= f <= 960
    if not act and not _sm_on[0]: return
    for ob, fb, c, kk, dr in SMOKE:
        tau = (f - fb) / 24.0
        if not act or tau < 0 or tau > 3.0:
            ob.hide_render = True; continue
        r = 0.25 + 1.25 * (1 - math.exp(-tau / 0.55)); ob.hide_render = False
        ob.location = c + dr * tau + Vector((0, 0, 0.35 * r)); ob.scale = (r, r, r * 0.6)
        ob["dens"] = 1.3 * kk * min(1.0, tau / 0.06) * math.exp(-tau / 0.75); ob.update_tag()
    _sm_on[0] = act
# sparks: thin glowing streaks from the underside on the touchdown and while scraping sideways
_spm = bpy.data.materials.new("Sparks"); _spm.use_nodes = True; _st = _spm.node_tree; _st.nodes.clear()
_so = _st.nodes.new("ShaderNodeOutputMaterial"); _se = _st.nodes.new("ShaderNodeEmission"); _se.inputs["Color"].default_value = (1.0, 0.55, 0.18, 1); _se.inputs["Strength"].default_value = 45.0
_st.links.new(_se.outputs[0], _so.inputs["Surface"]); _sa = _st.nodes.new("ShaderNodeOutputAOV"); _sa.aov_name = "glow"; _sa.inputs["Color"].default_value = (4.0, 2.2, 0.7, 1)
SPK_ME = bpy.data.meshes.new("SparksMesh"); SPK_ME.materials.append(_spm)
SPK = bpy.data.objects.new("Sparks", SPK_ME); coll.objects.link(SPK); SPK.visible_shadow = False; SPK.cycles.use_motion_blur = False; SPK.hide_render = True   # sparks removed
_rk = random.Random(9); SPARKS = []
for f, s_, p, rq in DRIFT:
    if f > 862: break
    vcar = (DP[min(f + 1, 895)] - DP[max(f - 1, 822)]) * 12.0                    # m per clip second
    for i in range(40 if f <= 824 else (6 if f < 850 else 2)):
        lp = Vector((_rk.uniform(-0.85, 0.85), _rk.choice((-1.9, 1.9, _rk.uniform(-1.9, 1.9))), 0.06)); c = DM[f] @ lp; c.z = 0.03
        SPARKS.append((f + _rk.random(), c, vcar * 0.7 + Vector((_rk.gauss(0, 2.5), _rk.gauss(0, 2.5), _rk.uniform(1.5, 4.5))), _rk.uniform(0.25, 0.6)))
_spk_n = [0]
def sparks_set(f, cam_loc):
    verts, faces = [], []
    if 822 <= f <= 880:
        for fb, c, v, life in SPARKS:
            tau = (f - fb) / 24.0
            if tau <= 0 or tau > life: continue
            b = c + v * tau + Vector((0, 0, -4.9 * tau * tau)); t0 = max(0.0, tau - 0.035); a = c + v * t0 + Vector((0, 0, -4.9 * t0 * t0))
            if b.z < 0.01: continue
            side = (b - a).cross(cam_loc - b)
            if side.length < 1e-9: continue
            side = side.normalized() * (0.006 * (1 - tau / life) + 0.002); k = len(verts)
            verts += [a - side, a + side, b + side, b - side]; faces.append((k, k + 1, k + 2, k + 3))
    if not verts and _spk_n[0] == 0: return
    SPK_ME.clear_geometry()
    if verts: SPK_ME.from_pydata(verts, [], faces)
    SPK_ME.update(); _spk_n[0] = len(verts)
# follow camera for S10 / S11 (constraints are evaluated at the motion-blur sub-steps too, so the tracked car stays sharp)
AIMO = bpy.data.objects.new("CamAim", None); sc.collection.objects.link(AIMO); AIMO.parent = CR; AIMO.location = (0.0, 0.0, 0.55)
c_loc = camo.constraints.new("COPY_LOCATION"); c_loc.target = CR; c_loc.use_offset = True
c_lim = camo.constraints.new("LIMIT_LOCATION"); c_lim.use_min_z = True; c_lim.min_z = 0.6
c_trk = camo.constraints.new("TRACK_TO"); c_trk.target = AIMO; c_trk.track_axis = "TRACK_NEGATIVE_Z"; c_trk.up_axis = "UP_Y"
for c in camo.constraints: c.mute = True
def follow(fl):
    for c in camo.constraints: c.mute = fl is None
    if fl is None: return
    offset, use_z, minz = fl; c_loc.use_z = use_z; c_lim.mute = minz is None; c_lim.min_z = minz or 0.0; camo.location = offset
# placements of the standing hero (only head and torso ever move; set once per placement)
car1 = car_M.copy(); S3_CAM = W((-1.75, -5.15, 1.05)); _a3 = math.radians(6); S3_AIM = W((-1.75 + math.sin(_a3) * 6, -5.15 + math.cos(_a3) * 6, 1.05 + math.tan(math.radians(1.0)) * 6))
stunt(300.0); CARF = rig.matrix_world.copy(); stunt(1.0)
PF = CARF @ Vector((-1.8, -0.8, 0.0)); PF.z = 0.0; UF = flat(LOOP_C - PF)
CAM13B = PF - UF * 3.4 + rotz(UF, -90) * 1.2 + Vector((0, 0, 1.25))
def _s2_end_fit(target=0.72):
    # S2 ends low behind the car: move the camera along its line to the car until the body spans `target` of the frame width
    cc = car1 @ Vector((0.0, -0.2, 0.6)); p = car1 @ Vector((1.25, -6.0, 0.12)); aim = cc + Vector((0.0, 0.0, 0.25))   # car centred, the loop above it
    pts = [body.matrix_world @ Vector(c) for c in body.bound_box]
    def width(p):
        set_cam(p, aim, 28.0); vl.update(); xs = [world_to_camera_view(sc, camo, q).x for q in pts]; return min(xs), max(xs)
    for _ in range(4):
        a_, b_ = width(p); p = cc + (p - cc) * ((b_ - a_) / target); p.z = 0.12
    a_, b_ = width(p); print("S2 end: car spans", round(a_, 3), "-", round(b_, 3), "of the frame width, camera", tuple(round(x, 2) for x in p), flush=True)
    return p, aim
S2_P3, S2_A3 = _s2_end_fit()
_place = [None]
def stand_at(key):
    if _place[0] == key: return
    if key == "start": place_stand((-2.16, -2.54, 0.0), cam_world=S3_CAM, look_loop=True)
    else: place_world(PF, CAM13B)
    _place[0] = key
def glow(f, base): return base * (0.75 + 0.5 * ENVV[min(f, len(ENVV) - 1)])
# ---- per-frame plan ----
def plan(f):
    sid, a, b = next(x for x in SHOTS if x[1] <= f < x[2])
    if sid == "S11" and f < 822: sid, a, b = "S10", 634, 819                     # S10 runs on to the touchdown: the cut to S11 lands on the hit (822)
    u = (f - a) / max(1, b - a)
    s = stunt_frame(f, sid, a, b); stunt(s); M = rig.matrix_world.copy(); Minv = M.inverted(); Lm = lambda p: M @ Vector(p)
    car = M.translation.copy(); cup = M.to_3x3() @ Vector((0, 0, 1))
    st = dict(stand=None, seat=None, mk=(-1e4, 1e4, 1.0, 1.0), expo=EXPO, wheel=0.0, sub="", tail=None, sweep=None, spin=None, rim=None, mb=None, follow=None, core=0.0)
    if sid == "S1":                                       # hook: upside down at the loop top, jets, slow push-in from the side
        st["seat"] = 0.0; k = ease(u)
        vc = Lm(bbox_c("Body", Minv)); loc0 = vc + Vector((-12.0 + 2.5 * k, -1.0 + 0.4 * k, -3.0 + 0.5 * k)); aim0 = vc   # body centre = frame centre
        if f >= 48:                                       # 2.0-2.44 s: push into the glowing nozzles, the flash peaks on the first beat (assembly step)
            w = clamp((f - 47) / 11.0); nz = Lm((-1.18, -0.15, 0.79)); tgt = nz + (loc0 - nz).normalized() * 1.8   # into the glowing jets, not the body panel
            loc0 = loc0.lerp(tgt, w ** 1.6); aim0 = aim0.lerp(nz, ease((f - 47) / 5.0)); st["core"] = w; st["sub"] = "push into the jets"
        cam = (loc0, aim0, 35, 5.6, None)
    elif sid == "S2":                                     # markers light one pair per beat from the camera outwards; the scene comes up out of the dark
        k = sum(1 for x in BEATS if 72 <= x <= f); st["mk"] = (60.0 - 12.0 * k, 72.0, 6.0, 2.0)   # match cut: the flash point is the marker at y = 66; a pair per beat toward the car, 2x brighter
        st["expo"] = lerp(-0.8, EXPO, ease((f - 62) / (128 - 62)))
        t = ease((f - 63) / (136 - 63)); P3, A3 = S2_P3, S2_A3   # pull back from the marker to low behind the car
        loc = bez(MK1 + Vector((-0.7, -0.75, 0.10)), Vector((29.0, 40.0, 1.6)), Vector((27.6, 18.5, 0.9)), P3, t)
        aim = MK1.lerp(A3, ease((t - 0.05) / 0.8)); cam = (loc, aim, lerp(50.0, 28.0, t), 5.6, None); st["sub"] = "marker close-up, pull back"
        cc = car1 @ Vector((0.0, -0.2, 0.6)); bk = flat(cc - P3); st["rim"] = (cc + bk * 3.6 + rotz(bk, 90) * 1.0 + Vector((0, 0, 2.2)), cc)
    elif sid in ("S3", "S4"):
        stand_at("start")
        if sid == "S3":                                   # assembles from particles beside the car (S3n framing, slow push-in)
            st["stand"] = lerp(1.1, 0.0, ease((f - 140) / (200 - 140)))
            d = (S3_AIM - S3_CAM).normalized(); k = 0.2 * ease(u); cam = (S3_CAM + d * k, S3_AIM + d * k, 26, 4.0, None)
        else:                                             # three details on the beats: tail stripe wave, light along the side, wheel spin-up
            st["stand"] = 0.0; k, v = sub_of(f, S4_CUTS); a1, b1 = S4_CUTS[k], S4_CUTS[k + 1]
            if k == 0:
                c = bbox_c("TailBar", Minv); st["sub"] = "tail wave"; bt = next((x for x in BEATS if a1 < x < b1), a1 + 13)
                st["tail"] = lerp(TB_X[0] - 0.05, TB_X[1] + 0.05, ease((f - bt) / 8.0)) if f >= bt else TB_X[0] - 0.05
                loc = c + rotz(Vector((0, -1, 0)), 40) * 1.25 + Vector((0, 0, 0.12)) + Vector((-0.08, 0, 0)) * v; cam = (Lm(loc), Lm(c + Vector((-0.15, 0, 0))), 40, 2.8, None)
            elif k == 1:
                st["sub"] = "side sweep"; y = lerp(-2.6, 2.6, ease((f - a1) / (b1 - a1 - 2)))
                st["sweep"] = (Lm((1.2, y, 0.62)), Lm((0.0, y, 0.55))); cam = (Lm((2.3, -2.9, 0.78 + 0.05 * v)), Lm((0.85, 0.6, 0.50)), 35, 4.0, None)
            else:
                c = bbox_c("WFR_Rim", Minv); st["sub"] = "wheel spin-up"; t = max(0.0, (f - a1 - 2) / 24.0)
                st["spin"] = 0.5 * 13.0 * t * t; st["mk"] = (-1e4, 1e4, 2.0, 2.0)
                loc = c + rotz(Vector((1, 0, 0)), 20) * 1.4 + Vector((0, 0, 0.06)); cam = (Lm(loc), Lm(c), 40, 4.0, None)
    elif sid == "S5":                                     # cabin through the windshield, the wheel turns by itself
        st["seat"] = 0.0; st["wheel"] = math.radians(70) * math.sin(2 * math.pi * (f - 332) / 54.0); k = ease(u)       # slow push-in, the wheel larger
        loc = Lm(Vector((-1.0, 3.4, 2.85)).lerp(Vector((-0.8, 2.8, 2.6)), k)); cam = (loc, Lm((0.0, 0.22, 0.62)), 65, 2.8, None)   # from above through the windshield: the wheel clears the dash
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
        st["seat"] = 0.0; st["mb"] = clamp(0.5 * (stunt_frame(f + 0.5, sid, a, b) - stunt_frame(f - 0.5, sid, a, b)), 0.03, 0.5)   # shutter scaled by the slow-mo
        if f < 726: st["follow"] = (Vector((-8.5, 2.0, 0.8)), True, None); cam = (None, None, 30, 8.0, None); st["sub"] = "side"
        else: st["follow"] = (Vector((-6.5, -11.0, -4.0)), True, 0.6); cam = (None, None, 28, 8.0, None); st["sub"] = "front-low"
    elif sid == "S11":                                    # touchdown on 'hit', slide to the stop; camera jolt
        st["seat"] = 0.0; j = 0.04 * math.exp(-max(0, f - 822) / 5.0) * (1 if f >= 822 else 0); st["sub"] = "drift"   # follow cam, jolt on the hit
        st["mb"] = clamp(0.5 * (stunt_frame(f + 0.5, sid, a, b) - stunt_frame(f - 0.5, sid, a, b)), 0.03, 0.5)
        st["follow"] = (Vector((-9.0, 2.5, 0.6)) + Vector((math.sin(f * 2.7), math.cos(f * 1.9), math.cos(f * 3.1))) * j, False, None); cam = (None, None, 38, 5.6, None)   # 2.4 m+ clear of the ground lamps
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
                st["stand"] = 0.0; st["sub"] = "behind the hero, the loop ahead"                       # hero >= 3 m from the lens, whole figure in frame
                loc = PF - UF * 3.5 + rotz(UF, -90) * 0.6 + Vector((0, 0, 1.1 + 0.1 * v)); cam = (loc, PF + UF * 30.0 + Vector((0, 0, 5.0)), 28, 5.6, None)
            elif k == 3:
                st["stand"] = 0.0; st["sub"] = "wide low, loop in smoke"
                loc = PF - UF * 9.0 + rotz(UF, 90) * 3.0 + Vector((0, 0, 0.4)) + rotz(UF, -90) * 0.8 * v; cam = (loc, PF + UF * 20 + Vector((0, 0, 5.0)), 24, 11.0, None)
            elif k == 4:
                st["stand"] = 0.0; st["sub"] = "dolly along the side"                                   # along the hero's side, 3.2 m+ from him: he stands next to the car, whole figure
                y = lerp(-3.6, 1.6, ease(v)); cam = (Lm((-5.0, y, 0.9)), Lm((-0.5, y + 2.0, 0.6)), 35, 4.0, None)   # the body fills the frame from the first frame
            else:
                st["stand"] = 0.0; st["sub"] = "silhouette"                     # low, from behind: the hero against the glowing loop
                loc = PF - UF * 3.2 + rotz(UF, -90) * 0.9 + Vector((0, 0, 0.35 + 0.1 * v)); cam = (loc, ch + UF * 2.0 + Vector((0, 0, 1.0)), 28, 5.6, None)
    else:                                                 # S14: markers out in reverse, the hero scatters upwards
        stand_at("final"); ch = chest(stand); f_h = flat(stand["root"].matrix_world.to_3x3() @ Vector((0, -1, 0)))
        st["stand"] = lerp(0.0, 1.1, ease((f - 1380) / (CARD - 1380)))
        k = sum(1 for x in BEATS if 1355 <= x <= f); st["mk"] = (-1e4, 66.0 - 12.0 * k, 1.0) if k > 0 else (-1e4, 1e4, 1.0)
        loc = PF + rotz(f_h, -30) * 3.4 + Vector((0, 0, 1.0 + 0.3 * u)); cam = (loc, ch + Vector((0, 0, 0.35 + 0.15 * u)), 35, 4.0, None)
    return sid, s, cam, st
for o in bpy.data.objects:
    if o.type == "LIGHT": o.visible_camera = False      # stunt fill lights (UnderFill next to the S11 camera) must never show up in the lens as panels
# ---- render loop ----
def frames_sel():
    if SEL == "all": return list(range(0, 1500))
    out = []
    for t in SEL.split(","):
        if "-" in t: x, y = t.split("-"); out += list(range(int(x), int(y) + 1))
        else: out.append(int(t))
    return out
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
        if st[who] is not None: rim_update(who, cam_now)
    vl.update()                                                                  # no sparks in S11 (drift + tyre smoke only)
    if WARM:
        s0_ = sc.cycles.samples; sc.cycles.samples = 1; sc.render.filepath = "/tmp/warm.png"; bpy.ops.render.render(write_still=True); sc.cycles.samples = s0_
    sc.render.filepath = fp; t1 = time.time(); bpy.ops.render.render(write_still=True); tr = time.time() - t1; n += 1
    dt = time.time() - t0
    if sid != last_sid or n % 10 == 0 or f == todo[-1] or SEL != "all":
        log(f"DRAFT f={f:04d} {sid} {st['sub']} s={s:.2f} {dt:.1f}s/frame, render {tr:.1f}s  [{n} new, {(time.time() - t_all) / 60:.1f} min]")
    last_sid = sid
log(f"DRAFT_DONE {n} frames in {(time.time() - t_all) / 60:.1f} min")
