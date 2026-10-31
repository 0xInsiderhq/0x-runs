"""Stage 2 step 1: rebuild a stage 1 still with shots.py on the Colab GPU and compare with out/.
usage: blender -b -P check_stills.py -- s3_cap [s2_blueprint ...]"""
import os, time
import boot
import shots

shots.log = lambda *a, **k: None          # stage 1 log line says "cloud CPU"; this run is logged from the session
shots.OUT = os.path.join(boot.HERE, 'check') + os.sep
os.makedirs(shots.OUT, exist_ok=True)
for name in boot.args():
    t0 = time.time()
    getattr(shots, name)()
    print('CHECK', name, round(time.time() - t0, 1), flush=True)
