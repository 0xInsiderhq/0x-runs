#!/bin/bash
# v2 (Dima 31.10): re-render only what changed, 1920x1080, in the background (log in final/v2/render_v2.log).
# hook + ident with the new sky (sky.py), the 2 s ident of the X cut, and the 28 explosion frames (F405-432)
# of the E shot with the Mantaflow firecracker. The rest of the story keeps its v1 frames.
E="$(cd "$(dirname "$0")" && pwd)"; F="$E/final"; V="$F/v2"
B=/content/blender/blender
mkdir -p "$V"
X() { echo "import sys; sys.path.insert(0, '$E'); __file__='$E/$1'; exec(compile(open('$E/$1').read(), '$1', 'exec'))"; }
cd "$E"
for spec in "hook" "ident2" "ident2 24"; do
  W=1920 H=1080 SAMPLES=64 OUTDIR="$V/intro" CSV="$V/render_times_intro_v2.csv" \
    $B -b --python-expr "$(X intro_render.py)" -- $spec 2>&1 | grep --line-buffered -E "^frame|SKY|rror|Traceback"
done
W=1920 H=1080 SAMPLES=64 BOUNCES=6 ADAPTIVE=0.02 FPS=24 FRAMES=$(seq -s, 405 432) OUTDIR="$V/e_frames" CSV="$V/render_times_v2.csv" \
  $B -b --python-expr "$(X ep1_anim.py)" -- e_launch 2>&1 | grep --line-buffered -E "FRAME|BUILD|BAKE|rror|Traceback"
echo V2_RENDER_DONE
