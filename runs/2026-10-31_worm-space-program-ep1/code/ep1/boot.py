"""Common start for every Blender run on Colab: paths to stage1 + ep1, GPU (OptiX/CUDA), OIDN denoise.
usage inside a script:  import boot  (before wsp_lib / shots)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ST1 = os.path.join(ROOT, 'stage1')
for p in (ST1, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import bpy
import wsp_lib as W

GPU_NAME = os.environ.get('GPU_NAME', 'NVIDIA L4')


def enable_gpu():
    prefs = bpy.context.preferences.addons['cycles'].preferences
    used = None
    for t in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = t
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == t for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == t
            used = t
            break
    s = bpy.context.scene
    s.cycles.device = 'GPU'
    s.cycles.denoiser = 'OPENIMAGEDENOISE'   # OptiX denoiser has no nvoptix.bin on Colab
    s.cycles.denoising_use_gpu = True
    return used


_reset = W.reset


def reset():
    s = _reset()
    enable_gpu()
    return s


W.reset = reset   # shots.py calls W.reset() at run time, so it picks this up too


def args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
