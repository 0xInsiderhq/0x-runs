#!/bin/bash
# Episode 1 animatic: approved intro v3 (0-9.5 s: hook, ident, text card) + story frames (12 fps, doubled to 24),
# 960x540. Three versions: A = sound by the episode plan (silence after the explosion),
# B = music never stops (Dima's 30.10 rule for the whole episode), silent = for the no-sound check.
set -e
E="$(cd "$(dirname "$0")" && pwd)"
ST1="$E/../stage1"
A="$E/animatic"
cd "$A"
ENC="-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 24"
n=$(ls frames/*.png | wc -l); echo "story frames: $n"
ffmpeg -y -loglevel error -i "$ST1/out/worms_intro_v3.mp4" -t 9.5 -an -vf "scale=960:540,fps=24" $ENC intro.mp4
ffmpeg -y -loglevel error -framerate 12 -i frames/%04d.png -vf "fps=24,format=yuv420p,fade=out:st=23.9:d=0.6" $ENC story.mp4
printf "file 'intro.mp4'\nfile 'story.mp4'\n" > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c copy video.mp4
for v in A B; do
  ffmpeg -y -loglevel error -i video.mp4 -i "$E/out/ep1_draft_$v.wav" -map 0:v -map 1:a -c:v copy \
    -af "loudnorm=I=-16:TP=-2.0:LRA=11" -ar 48000 -c:a aac -b:a 192k -shortest ep1_animatic_$v.mp4
  echo "$v: $(ffprobe -v error -show_entries format=duration -of csv=p=0 ep1_animatic_$v.mp4) s"
  ffmpeg -nostats -i ep1_animatic_$v.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "I:|Peak:" | tail -2
done
cp video.mp4 ep1_animatic_silent.mp4
echo "silent: $(ffprobe -v error -show_entries format=duration -of csv=p=0 ep1_animatic_silent.mp4) s"
