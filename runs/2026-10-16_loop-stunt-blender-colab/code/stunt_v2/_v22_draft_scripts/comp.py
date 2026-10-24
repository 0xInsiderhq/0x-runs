"""Effects pass: clean multilayer EXR -> soft bloom from the 'glow' AOV only (loop LEDs + headlights) -> AgX -> PNG.
usage: blender -b --python comp.py -- SRC_DIR DST_DIR FRAMES [PERCENT]     FRAMES: '1-360' or '166,197,201'"""
import bpy, sys, os
args = sys.argv[sys.argv.index("--") + 1:]
SRC, DST, FR = args[0], args[1], args[2]; PCT = int(args[3]) if len(args) > 3 else 100
GLOW_STRENGTH, GLOW_SIZE, GLOW_THRESHOLD = 0.35, 0.45, 0.5
frames = []
for part in FR.split(","):
    if "-" in part: a, b = map(int, part.split("-")); frames += list(range(a, b + 1))
    else: frames.append(int(part))
os.makedirs(DST, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1080, 1350, PCT
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass
sc.view_settings.exposure = 0.3
cd = bpy.data.cameras.new("C"); co = bpy.data.objects.new("C", cd); sc.collection.objects.link(co); sc.camera = co
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"; sc.render.image_settings.color_depth = "8"
sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
first = sorted(f for f in os.listdir(SRC) if f.endswith(".exr"))[0]
img = bpy.data.images.load(os.path.join(SRC, first)); img.source = "SEQUENCE"
inp = nt.nodes.new("CompositorNodeImage"); inp.image = img; inp.frame_duration = 10000; inp.frame_start = 1; inp.frame_offset = 0
outs = {o.name: o for o in inp.outputs}
comb = outs.get("Image") or outs.get("Combined"); glow = outs.get("glow")
print("EXR passes:", list(outs), flush=True)
gl = nt.nodes.new("CompositorNodeGlare")
types = [i.identifier for i in gl.bl_rna.properties["glare_type"].enum_items]
gl.glare_type = "FOG_GLOW" if "FOG_GLOW" in types else "BLOOM"
try: gl.quality = "HIGH"
except Exception: pass
for name, val in (("Threshold", GLOW_THRESHOLD), ("Strength", GLOW_STRENGTH), ("Size", GLOW_SIZE)):
    if name in gl.inputs: gl.inputs[name].default_value = val
add = nt.nodes.new("CompositorNodeMixRGB"); add.blend_type = "ADD"; add.inputs[0].default_value = 1.0
lens = nt.nodes.new("CompositorNodeLensdist")
if "Dispersion" in lens.inputs: lens.inputs["Dispersion"].default_value = 0.006
out = nt.nodes.new("CompositorNodeComposite")
if glow is not None:
    nt.links.new(glow, gl.inputs["Image"])
    gout = gl.outputs.get("Glare") or gl.outputs["Image"]
    nt.links.new(comb, add.inputs[1]); nt.links.new(gout, add.inputs[2]); nt.links.new(add.outputs[0], lens.inputs["Image"])
else:
    nt.links.new(comb, lens.inputs["Image"])
nt.links.new(lens.outputs["Image"], out.inputs["Image"])
for f in frames:
    sc.frame_set(f); sc.render.filepath = os.path.join(DST, f"c_{f:04d}.png")
    bpy.ops.render.render(write_still=True)
print("COMP_DONE", len(frames), flush=True)
