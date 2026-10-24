#!/bin/bash
# full animation into frames/ (resumable: skips finished frames, removes empty placeholders of interrupted ones)
cd "$(dirname "$0")"
mkdir -p frames
find frames -name 'f_*.png' -size 0 -delete
/content/blender/blender -b stunt.blend --python gpu_on.py -a > /content/render.log 2>&1
echo RENDER_EXIT=$? >> /content/render.log
