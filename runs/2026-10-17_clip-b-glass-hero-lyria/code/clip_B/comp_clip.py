"""clip_B effects pass (same look as stunt_v2 comp.py): soft bloom from the 'glow' AOV only -> AgX -> PNG.
usage: blender -b --python comp_clip.py -- IN.exr OUT.png [width height]"""
import bpy, sys, os
a = sys.argv[sys.argv.index("--") + 1:]; SRC, DST = a[0], a[1]; WX, WY = (int(a[2]), int(a[3])) if len(a) > 3 else (1080, 1920)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.engine = "BLENDER_WORKBENCH"
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = WX, WY, 100
sc.view_settings.view_transform = "AgX"
try: sc.view_settings.look = "AgX - Medium High Contrast"
except Exception: pass
sc.view_settings.exposure = 0.3
cd = bpy.data.cameras.new("C"); co = bpy.data.objects.new("C", cd); sc.collection.objects.link(co); sc.camera = co
im = sc.render.image_settings; im.file_format = "PNG"; im.color_mode = "RGB"; im.color_depth = "8"
sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
img = bpy.data.images.load(SRC); inp = nt.nodes.new("CompositorNodeImage"); inp.image = img
outs = {o.name: o for o in inp.outputs}; comb = outs.get("Image") or outs.get("Combined"); glow = outs.get("glow")
gl = nt.nodes.new("CompositorNodeGlare"); types = [i.identifier for i in gl.bl_rna.properties["glare_type"].enum_items]
gl.glare_type = "FOG_GLOW" if "FOG_GLOW" in types else "BLOOM"
try: gl.quality = "HIGH"
except Exception: pass
for n, v in (("Threshold", 0.5), ("Strength", 0.35), ("Size", 0.45)):
    if n in gl.inputs: gl.inputs[n].default_value = v
add = nt.nodes.new("CompositorNodeMixRGB"); add.blend_type = "ADD"; add.inputs[0].default_value = 1.0
lens = nt.nodes.new("CompositorNodeLensdist")
if "Dispersion" in lens.inputs: lens.inputs["Dispersion"].default_value = 0.006
out = nt.nodes.new("CompositorNodeComposite")
if glow is not None:
    nt.links.new(glow, gl.inputs["Image"]); gout = gl.outputs.get("Glare") or gl.outputs["Image"]
    nt.links.new(comb, add.inputs[1]); nt.links.new(gout, add.inputs[2]); nt.links.new(add.outputs[0], lens.inputs["Image"])
else:
    nt.links.new(comb, lens.inputs["Image"])
nt.links.new(lens.outputs["Image"], out.inputs["Image"])
sc.render.filepath = DST; bpy.ops.render.render(write_still=True); print("COMP_DONE", DST, flush=True)
