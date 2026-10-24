#!/bin/bash
# continue the render after a disconnect: installs Blender if needed, skips finished frames
[ -x /content/blender/blender ] || bash /content/drive/MyDrive/renders/get_blender.sh > /content/get_blender.log 2>&1
pgrep -f '[s]tunt.blend --python gpu_on.py -a' > /dev/null && { echo "already rendering"; exit 0; }
nohup bash /content/drive/MyDrive/renders/stunt/render.sh > /dev/null 2>&1 &
echo "render started (resumes from the first missing frame)"
