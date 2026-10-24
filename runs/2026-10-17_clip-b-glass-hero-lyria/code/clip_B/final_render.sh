#!/bin/bash
# clip_B stage 3 final: 1080x1920, 64 spp adaptive 0.02 + OIDN, final volume step; resumable (finished PNGs are skipped, broken ones removed first)
C=/content/drive/MyDrive/renders/clip_B
mkdir -p $C/final_frames $C/review
python3 - <<'PYEOF'
import glob, os
from PIL import Image
bad = 0
for p in sorted(glob.glob("/content/drive/MyDrive/renders/clip_B/final_frames/f_*.png"))[-6:]:
    try:
        Image.open(p).verify()
    except Exception:
        os.remove(p); bad += 1
print("removed broken frames:", bad)
PYEOF
echo "--- FINAL render start $(date +%H:%M:%S): 64 spp, 1080x1920" >> $C/progress.log
cd $C && DRAFT_OUT=$C/final_frames DRAFT_STEP=1.0 DRAFT_ADAPT=0.02 /content/blender/blender -b --python clip_draft.py -- all 64 100 > /content/final_render.log 2>&1
echo "RENDER_EXIT=$? $(date +%H:%M:%S)" >> $C/progress.log
