import bpy, math, os
from mathutils import Vector
STUNT = os.path.dirname(os.path.abspath(__file__))

def setup_cycles(scene, samples, gpu=True):
    scene.render.engine = "CYCLES"
    cy = scene.cycles; dev = "CPU"
    if gpu:
        try:
            pr = bpy.context.preferences.addons["cycles"].preferences
            pr.compute_device_type = "OPTIX"; pr.get_devices()
            ok = [d for d in pr.devices if d.type == "OPTIX"]
            for d in pr.devices: d.use = d.type == "OPTIX"
            if ok: dev = "GPU"
        except Exception as e: print("GPU setup failed:", e)
    cy.device = dev; print("DEVICE:", dev, flush=True)
    cy.samples = samples; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
    cy.use_denoising = True; cy.denoiser = "OPENIMAGEDENOISE"
    try: cy.denoising_use_gpu = dev == "GPU"
    except Exception: pass
    cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cy.max_bounces, cy.diffuse_bounces, cy.glossy_bounces = 8, 3, 4
    cy.transmission_bounces, cy.volume_bounces, cy.transparent_max_bounces = 8, 1, 8
    cy.sample_clamp_indirect = 6.0; cy.caustics_reflective = cy.caustics_refractive = False
    scene.view_settings.view_transform = "AgX"
    try: scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception: pass
    scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_mode = "RGB"
    return dev

def look_at(ob, target, roll=0.0):
    d = Vector(target) - ob.location
    ob.rotation_mode = "XYZ"; ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if roll: ob.rotation_euler.rotate_axis("Z", roll)

def area(scene, name, loc, target, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy = energy; ld.size = size; ld.color = color
    ob = bpy.data.objects.new(name, ld); scene.collection.objects.link(ob); ob.location = loc; look_at(ob, target)
    return ob
