#!/bin/bash
# Stage 4: full 1080p render in the background (nohup), log in final/render_final.log.
# Story frames already on disk are skipped, so after a Colab reset just run it again.
E="$(cd "$(dirname "$0")" && pwd)"; R="$(dirname "$E")"; F="$E/final"
B=/content/blender/blender
mkdir -p "$F/frames" "$F/intro"
cd "$E"
W=1920 H=1080 SAMPLES=64 BOUNCES=6 ADAPTIVE=0.02 FPS=24 OUTDIR="$F/frames" CSV="$F/render_times.csv" \
  $B -b --python-expr "import sys; sys.path.insert(0, '$E'); __file__='$E/ep1_anim.py'; exec(compile(open('$E/ep1_anim.py').read(), 'ep1_anim.py', 'exec'))" -- all 2>&1 \
  | grep --line-buffered -E "FRAME|BUILD|SKIP|rror|Traceback"
echo "STORY_EXIT ${PIPESTATUS[0]}"
# intro hook + ident at 1080p, 12 fps like the approved v3, frames to final/intro/<part>
for part in hook ident2; do
  want=30; [ "$part" = ident2 ] && want=42
  n=$(ls "$F/intro/$part" 2>/dev/null | wc -l)
  if [ "$n" -ge "$want" ]; then echo "SKIP $part"; continue; fi
  (cd "$R/stage1" && W=1920 H=1080 SAMPLES=64 $B -b --python-expr "import sys; sys.path.insert(0, '$E'); import boot; sys.path.insert(0, boot.ST1); __file__='$R/stage1/intro.py'; src = open('$R/stage1/intro.py').read().replace(\"if __name__ == '__main__':\", 'if False:').replace(\"os.path.join(HERE, 'out', 'intro', name)\", \"os.path.join('$F', 'intro', name)\"); exec(compile(src, 'intro.py', 'exec')); $part()" 2>&1 \
    | grep --line-buffered -E "^frame|rror|Traceback")
done
echo FINAL_DONE
