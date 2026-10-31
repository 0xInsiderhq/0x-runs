"""Re-render the approved stage 1 intro (shaft hook + crown-cap ident) with the v2 sky (sky.py), on the GPU.
Runs stage1/intro.py unchanged except: no __main__ block, the roar shake works on fractional frames,
and render_frames() is replaced here: it puts in the new sky, then renders, optionally squeezing the time.
usage: blender -b -P intro_render.py -- hook|ident2 [OUT_N]
  OUT_N: output frames (default the original 30 / 42 at 12 fps). ident2 24 = the 2 s logo of the X cut:
  the same animation, sampled at (42-1)/(24-1) original frames per output frame.
env:   W, H, SAMPLES (read by intro.py), FRAMES="1,20" (output frames), OUTDIR, CSV"""
import os, time
import boot
import bpy
import sky

args = boot.args()
PART = args[0]
OUT_N = int(args[1]) if len(args) > 1 else None
OUT = os.environ.get('OUTDIR', os.path.join(boot.HERE, 'final', 'intro_v2'))
CSV = os.environ.get('CSV', os.path.join(OUT, 'render_times_intro_v2.csv'))

src = open(os.path.join(boot.ST1, 'intro.py'), encoding='utf-8').read()
src = src.replace("if __name__ == '__main__':", 'if False:')
for a in ("side = 0.12 if f % 2 else -0.12", "side = 0.07 if f % 2 else -0.07"):
    src = src.replace(a, a.replace('f % 2', 'int(round(f)) % 2'))
ns = {'__file__': os.path.join(boot.ST1, 'intro.py'), '__name__': 'intro_v2'}
exec(compile(src, 'intro.py', 'exec'), ns)


def render_frames(name, per_frame=None, n=None):
    n = n or ns['N']
    (sky.upgrade_hook if name == 'hook' else sky.upgrade_ident)()
    sc = bpy.context.scene
    ns['W'].render_settings(ns['RW'], ns['RH'], ns['SAMPLES'])
    sc.render.fps = ns['FPS']; sc.frame_start, sc.frame_end = 1, n
    m = OUT_N or n
    outdir = os.path.join(OUT, name if m == n else f'{name}_{m}f'); os.makedirs(outdir, exist_ok=True)
    frames = [int(x) for x in os.environ['FRAMES'].split(',')] if os.environ.get('FRAMES') else list(range(1, m + 1))
    for i in frames:
        fs = 1 + (i - 1) * (n - 1) / (m - 1) if m != n else i
        sc.frame_set(int(fs), subframe=fs - int(fs))
        if per_frame:
            per_frame(fs)
        sc.render.filepath = os.path.join(outdir, f'{i:04d}.png')
        t0 = time.time(); bpy.ops.render.render(write_still=True); dt = round(time.time() - t0, 2)
        new = not os.path.exists(CSV)
        with open(CSV, 'a') as fh:
            if new:
                fh.write('part,frame,seconds,gpu\n')
            fh.write(f'{os.path.basename(outdir)},{i},{dt},{boot.GPU_NAME}\n')
        print('frame', name, i, dt, flush=True)


ns['render_frames'] = render_frames
ns[PART]()
