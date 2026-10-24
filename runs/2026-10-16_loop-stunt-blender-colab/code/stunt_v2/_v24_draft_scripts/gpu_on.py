import bpy
pr = bpy.context.preferences.addons["cycles"].preferences
pr.compute_device_type = "OPTIX"; pr.get_devices()
for d in pr.devices: d.use = d.type == "OPTIX"
bpy.context.scene.cycles.device = "GPU"
print("GPU_ON", [(d.name, d.type) for d in pr.devices if d.use], flush=True)
