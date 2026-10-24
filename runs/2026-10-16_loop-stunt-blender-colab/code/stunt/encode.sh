#!/bin/bash
# PNG frames + synthesized audio -> H.264/AAC MP4 (light film grain + vignette in post)
cd "$(dirname "$0")"
ffmpeg -y -framerate 24 -i frames/f_%04d.png -i stunt_audio.wav \
  -vf "vignette=angle=PI/5.5,noise=alls=5:allf=t,format=yuv420p" \
  -c:v libx264 -preset slow -crf 16 -profile:v high -movflags +faststart \
  -c:a aac -b:a 256k -shortest stunt.mp4 > /content/encode.log 2>&1
echo ENCODE_EXIT=$? >> /content/encode.log
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of compact stunt.mp4 >> /content/encode.log
