#!/bin/bash
# v3 (Dima 31.10): v2 with the launch+blast shot (frames 361-432) from final/v3. Two versions, 1920x1080, 24 fps.
#  full (34.0 s): hook 2.5 + ident 3.5 + card 3.5 + story 24.5, sound B as approved
#  X cut (31.0 s): hook 2.5 + ident 2.0 + card 2.0 + story from 6.5, no black: the ident dissolves into the card,
#                  the card into the story; sound B with the intro score rebuilt for this layout (LAYOUT=x)
# Story frames: v1 frames with the 28 new explosion frames swapped in. Master: -16 LUFS, true peak under -1.5.
set -e
E="$(cd "$(dirname "$0")" && pwd)"; F="$E/final"; V="$F/v2"; V3="$F/v3"
cd "$V"
ENC="-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 24"

master() {   # wav, video, out: limiter -> two-pass linear loudnorm -> limiter -> make-up gain (as assemble_final.sh)
  PRE="alimiter=limit=0.5:attack=2:release=60:level=false"
  M=$(ffmpeg -hide_banner -i "$1" -af "$PRE,loudnorm=I=-16:TP=-2.0:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p')
  v() { echo "$M" | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"; }
  LN="loudnorm=I=-16:TP=-2.0:LRA=11:measured_I=$(v input_i):measured_TP=$(v input_tp):measured_LRA=$(v input_lra):measured_thresh=$(v input_thresh):offset=$(v target_offset):linear=true"
  ffmpeg -y -loglevel error -i "$1" -af "$PRE,$LN,alimiter=limit=0.7:attack=1:release=50:level=false" -ar 48000 master_pre.wav
  I=$(ffmpeg -nostats -i master_pre.wav -af ebur128 -f null - 2>&1 | grep -E "^ +I:" | tail -1 | awk '{print $2}')
  G=$(python3 -c "print(round(-16.0 - ($I), 2))"); echo "make-up gain ${G} dB"
  ffmpeg -y -loglevel error -i master_pre.wav -af "volume=${G}dB" master.wav
  ffmpeg -y -loglevel error -i "$2" -i master.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest "$3"
  ffprobe -v error -show_entries format=duration:stream=nb_frames -of compact "$3"
  ffmpeg -hide_banner -i "$3" -af "loudnorm=print_format=json" -f null - 2>&1 | grep -E '"input_(i|tp)"'
}

for p in hook:30 ident2:42 ident2_24f:24; do n=$(ls intro/${p%%:*} | wc -l); [ "$n" -eq "${p##*:}" ] || { echo "intro ${p%%:*}: $n"; exit 1; }; done
[ "$(ls "$V3/e_frames" | wc -l)" -eq 72 ] || { echo "v3 e_frames: $(ls "$V3/e_frames" | wc -l)"; exit 1; }
ST=/content/v3_story                                        # Drive has no symlinks: link list lives on local disk
rm -rf "$ST" && mkdir "$ST"
for f in "$F"/frames/*.png; do ln -s "$f" "$ST/"; done
for f in "$V3"/e_frames/*.png; do ln -sf "$f" "$ST/$(basename "$f")"; done
[ "$(ls "$ST" | wc -l)" -eq 588 ] || { echo "story: $(ls "$ST" | wc -l)"; exit 1; }

ffmpeg -y -loglevel error -framerate 12 -i intro/hook/%04d.png -vf "format=yuv420p" $ENC s1_hook.mp4
ffmpeg -y -loglevel error -framerate 12 -i intro/ident2/%04d.png -vf "format=yuv420p,fade=out:st=3.15:d=0.35" $ENC s2_ident.mp4
ffmpeg -y -loglevel error -framerate 24 -i "$ST/%04d.png" -vf "format=yuv420p,fade=out:st=23.9:d=0.6" $ENC "$V3/s4_story.mp4"
printf "file 's1_hook.mp4'\nfile 's2_ident.mp4'\nfile '$F/s3_card.mp4'\nfile '$V3/s4_story.mp4'\n" > list_full.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list_full.txt -c copy "$V3/video_full.mp4"
echo "== full"; master "$E/out/ep1_draft_B.wav" "$V3/video_full.mp4" "$V3/worm_space_program_ep1_v3.mp4"

ffmpeg -y -loglevel error -framerate 12 -i intro/ident2_24f/%04d.png -vf "format=yuv420p" $ENC x_ident.mp4
ffmpeg -y -loglevel error -loop 1 -framerate 24 -t 2.55 -i "$F/card/0048.png" -vf "format=yuv420p" $ENC x_card.mp4
ffmpeg -y -loglevel error -i s1_hook.mp4 -i x_ident.mp4 -i x_card.mp4 -i "$V3/s4_story.mp4" -filter_complex \
  "[0:v]fps=24,settb=AVTB[h];[1:v]fps=24,settb=AVTB[i];[2:v]fps=24,settb=AVTB[c];[3:v]fps=24,settb=AVTB[s];\
[i][c]xfade=transition=fade:duration=0.3:offset=1.7[ic];[h][ic]concat=n=2:v=1:a=0,fps=24,settb=AVTB[hc];\
[hc][s]xfade=transition=fade:duration=0.25:offset=6.5,format=yuv420p[v]" -map "[v]" $ENC "$V3/video_x.mp4"
echo "== X cut"; master "$E/out/ep1_draft_B_x.wav" "$V3/video_x.mp4" "$V3/worm_space_program_ep1_v3_x.mp4"
