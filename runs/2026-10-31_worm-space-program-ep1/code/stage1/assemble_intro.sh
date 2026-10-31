#!/bin/bash
# Build intro sample: hook + ident from 12 fps PNG frames, card + story already encoded; join and add sound.
set -e
D="$(cd "$(dirname "$0")" && pwd)/out/intro"
cd "$D"
ENC="-c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -r 24"
# hook: fill the frames that were not rendered with the previous rendered frame
rm -rf hook_full && mkdir hook_full
last=""
for i in $(seq 1 30); do
  f=$(printf "%04d.png" $i)
  if [ -f "hook/$f" ]; then last="hook/$f"; fi
  cp "$last" "hook_full/$f"
done
ffmpeg -y -loglevel error -framerate 12 -i hook_full/%04d.png -vf "format=yuv420p" $ENC scene1_hook.tmp.mp4 && mv scene1_hook.tmp.mp4 scene1_hook.mp4
ffmpeg -y -loglevel error -framerate 12 -i ident/%04d.png -vf "format=yuv420p,fade=out:st=2.15:d=0.35" $ENC scene2_ident.tmp.mp4 && mv scene2_ident.tmp.mp4 scene2_ident.mp4
printf "file 'scene1_hook.mp4'\nfile 'scene2_ident.mp4'\nfile 'scene3_card.mp4'\nfile 'scene4_story.mp4'\n" > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c copy video_only.tmp.mp4 && mv video_only.tmp.mp4 video_only.mp4
ffmpeg -y -loglevel error -i video_only.mp4 -i intro_audio.wav -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -shortest worms_intro_sample.tmp.mp4 && mv worms_intro_sample.tmp.mp4 worms_intro_sample.mp4
ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 worms_intro_sample.mp4
ffmpeg -nostats -i worms_intro_sample.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "I:|Peak:" | tail -2
