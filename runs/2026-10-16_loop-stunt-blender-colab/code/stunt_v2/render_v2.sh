#!/bin/bash
# stunt_v2 full render -> frames_exr/f_####.exr (multilayer: Combined + glow AOV), 1080x1350, 64 samples.
# Resumable: finished frames are skipped (use_overwrite off + placeholders); half-written frames are removed first.
V2=/content/drive/MyDrive/renders/stunt_v2
find "$V2/frames_exr" -name 'f_*.exr' -size -20k -delete
cd "$V2" && /content/blender/blender -b stunt.blend --python gpu_on.py -a > /content/render_v2.log 2>&1
echo EXIT=$? >> /content/render_v2.log
