"""Assemble the full shot and save stunt.blend.  usage: blender -b --python build.py -- [samples]"""
import sys, os, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as C, materials as M, traj as T, car as CAR, env as ENV, fx as FX

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SAMPLES = int(args[0]) if args else 128
t0 = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
C.setup_cycles(sc, SAMPLES)
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1080, 1350, 100
sc.render.fps = T.FPS; sc.frame_start, sc.frame_end = 1, T.FRAMES
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
sc.cycles.motion_blur_position = "CENTER"
sc.cycles.volume_step_rate = 3.5; sc.cycles.volume_max_steps = 256; sc.cycles.volume_bounces = 0
sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 4
sc.cycles.caustics_reflective = False; sc.cycles.caustics_refractive = False; sc.cycles.sample_clamp_indirect = 3.0
sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.05; sc.cycles.adaptive_min_samples = 0
sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.render.use_persistent_data = True
sc.view_settings.exposure = 0.3

S, ev, FR, CAMS = T.build_all()
print("timeline:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in ev.items() if k in ("t_top", "t_land", "t_stop", "cut_frame")}, flush=True)
ENV.build(sc)
cc = bpy.data.collections.new("Car"); sc.collection.children.link(cc)
car = CAR.build_car(cc)
root, rig = car["root"], car["rig"]
FX.build_jets(cc, rig, S)
fxc = bpy.data.collections.new("FX"); sc.collection.children.link(fxc)
FX.build_dust(fxc, S, ev)
print(f"scene built {time.time() - t0:.0f}s", flush=True)

# ---- car animation (per-frame keys, linear) ----
root.rotation_mode = "QUATERNION"; rig.rotation_mode = "XYZ"
for s in FR:
    f = s["frame"]
    root.location = s["pos"]; root.rotation_quaternion = s["quat"]
    root.keyframe_insert("location", frame=f); root.keyframe_insert("rotation_quaternion", frame=f)
    rig.location = (0, 0, s["dz"]); rig.rotation_euler = (s["pitch"], s["roll"], 0)
    rig.keyframe_insert("location", frame=f); rig.keyframe_insert("rotation_euler", frame=f)
    for key, (hub, spin) in car["wheels"].items():
        hub.location.z = 0.35 + s["droop"]; hub.keyframe_insert("location", index=2, frame=f)
        if key[0] == "F":
            hub.rotation_euler.z = s["steer"]; hub.keyframe_insert("rotation_euler", index=2, frame=f)
        spin.rotation_euler.x = s["spin"]; spin.keyframe_insert("rotation_euler", index=0, frame=f)
for ob in bpy.data.objects:
    ad = ob.animation_data
    if ad and ad.action:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points: kp.interpolation = "LINEAR"
    if ob.name.endswith("_Spin"):
        try: ob.cycles.motion_steps = 3
        except Exception: pass

# ---- handheld cameras ----
cams = {}
for key in ("A", "B"):
    cd = bpy.data.cameras.new("Cam" + key); cd.sensor_width = 36; cd.sensor_fit = "AUTO"
    cd.dof.use_dof = True; cd.dof.aperture_blades = 9; cd.dof.aperture_rotation = math.radians(12)
    cd.clip_start = 0.05; cd.clip_end = 2000
    ob = bpy.data.objects.new("Cam" + key, cd); sc.collection.objects.link(ob); ob.rotation_mode = "QUATERNION"
    for c in CAMS:
        d = c[key]; f = c["frame"]
        ob.location = d["loc"]; ob.rotation_quaternion = d["quat"]
        cd.lens = d["lens"]; cd.dof.focus_distance = d["focus"]; cd.dof.aperture_fstop = d["fstop"]
        ob.keyframe_insert("location", frame=f); ob.keyframe_insert("rotation_quaternion", frame=f)
        cd.keyframe_insert("lens", frame=f); cd.dof.keyframe_insert("focus_distance", frame=f); cd.dof.keyframe_insert("aperture_fstop", frame=f)
    cams[key] = ob
sc.camera = cams["A"]
mA = sc.timeline_markers.new("ShotA", frame=1); mA.camera = cams["A"]
mB = sc.timeline_markers.new("ShotB", frame=ev["cut_frame"]); mB.camera = cams["B"]

# ---- compositor: streak glare + soft bloom + slight lens dispersion ----
def setg(node, **kw):
    names = {"threshold": ["Highlights Threshold", "Threshold"], "mix": ["Mix"], "size": ["Size"], "streaks": ["Streaks"],
             "angle_offset": ["Streaks Angle", "Angle"], "fade": ["Fade"], "strength": ["Strength"], "quality": [], "glare_type": []}
    for k, v in kw.items():
        done = False
        if hasattr(node, k):
            try: setattr(node, k, v); done = True
            except Exception: pass
        for n in names[k]:
            if n in node.inputs:
                try: node.inputs[n].default_value = v; done = True
                except Exception: pass
        if not done: print("glare: could not set", k)
sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
rl = nt.nodes.new("CompositorNodeRLayers")
g1 = nt.nodes.new("CompositorNodeGlare"); setg(g1, glare_type="STREAKS", quality="HIGH", streaks=4, angle_offset=math.radians(22), threshold=1.4, fade=0.92, mix=0.0, strength=0.9)
g2 = nt.nodes.new("CompositorNodeGlare")
types = [i.identifier for i in g2.bl_rna.properties["glare_type"].enum_items]
setg(g2, glare_type="BLOOM" if "BLOOM" in types else "FOG_GLOW", quality="HIGH", threshold=1.2, size=(0.45 if "Size" in g2.inputs else 8), strength=0.18)
ld = nt.nodes.new("CompositorNodeLensdist")
for nme, val in (("Dispersion", 0.012), ("Distortion", 0.004)):
    if nme in ld.inputs: ld.inputs[nme].default_value = val
co = nt.nodes.new("CompositorNodeComposite")
nt.links.new(rl.outputs["Image"], g1.inputs["Image"]); nt.links.new(g1.outputs["Image"], g2.inputs["Image"])
nt.links.new(g2.outputs["Image"], ld.inputs["Image"]); nt.links.new(ld.outputs["Image"], co.inputs["Image"])
print("glare inputs:", [i.name for i in g1.inputs], flush=True)

FRAMES_DIR = os.path.join(C.STUNT, "frames"); os.makedirs(FRAMES_DIR, exist_ok=True)
sc.render.filepath = os.path.join(FRAMES_DIR, "f_")
sc.render.use_overwrite = False; sc.render.use_placeholder = True
sc.render.image_settings.compression = 15
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(C.STUNT, "stunt.blend"))
print(f"BUILD_DONE {time.time() - t0:.0f}s", flush=True)
