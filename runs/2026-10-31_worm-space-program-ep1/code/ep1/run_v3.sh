#!/bin/bash
# v3 (Dima 31.10): re-render only the launch and blast shot (E, frames 361-432): the approved fireball back,
# soft brown-grey smoke and soft launch dust (volume puffs). Everything else stays as in v2.
E="$(cd "$(dirname "$0")" && pwd)"; V="$E/final/v3"
B=/content/blender/blender
mkdir -p "$V"
X() { echo "import sys; sys.path.insert(0, '$E'); __file__='$E/$1'; exec(compile(open('$E/$1').read(), '$1', 'exec'))"; }
cd "$E"
W=1920 H=1080 SAMPLES=64 BOUNCES=6 ADAPTIVE=0.02 FPS=24 FRAMES=${FRAMES:-$(seq -s, 361 432)} OUTDIR="$V/e_frames" CSV="$V/render_times_v3.csv" \
  $B -b --python-expr "$(X ep1_anim.py)" -- e_launch 2>&1 | grep --line-buffered -E "FRAME|BUILD|rror|Traceback"
echo V3_RENDER_DONE
