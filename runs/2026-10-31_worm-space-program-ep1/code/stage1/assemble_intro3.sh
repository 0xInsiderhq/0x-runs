#!/bin/bash
# Intro sample v2: hook + crown-cap medallion ident (3.5 s) + text card + story, epic soundtrack.
set -e
D="$(cd "$(dirname "$0")" && pwd)/out/intro"
cd "$D"
ENC="-c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -r 24"
ffmpeg -y -loglevel error -framerate 12 -i ident2/%04d.png -vf "format=yuv420p,fade=out:st=3.15:d=0.35" $ENC scene2_ident2.tmp.mp4 && mv scene2_ident2.tmp.mp4 scene2_ident2.mp4
printf "file 'scene1_hook.mp4'\nfile 'scene2_ident2.mp4'\nfile 'scene3_card.mp4'\nfile 'scene4_story.mp4'\n" > list2.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list2.txt -c copy video2_only.tmp.mp4 && mv video2_only.tmp.mp4 video2_only.mp4
ffmpeg -y -loglevel error -i video2_only.mp4 -i intro_audio3.wav -map 0:v -map 1:a -c:v copy \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -shortest worms_intro_v3.tmp.mp4 && mv worms_intro_v3.tmp.mp4 worms_intro_v3.mp4
ffprobe -v error -show_entries format=duration -of csv=p=0 worms_intro_v3.mp4
ffmpeg -nostats -i worms_intro_v3.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "I:|Peak:" | tail -2
