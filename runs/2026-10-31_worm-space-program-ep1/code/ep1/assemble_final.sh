#!/bin/bash
# Episode 1 final, 1920x1080, 24 fps, 34.0 s: hook 2.5 + ident 3.5 (12 fps frames, doubled, like intro v3)
# + text card 3.5 + story 24.5 (24 fps), sound B (music never stops; Dima 31.10), loudness -16 LUFS, true peak under -1.5.
set -e
E="$(cd "$(dirname "$0")" && pwd)"
F="$E/final"
cd "$F"
ENC="-c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 24"
for p in hook:30 ident2:42; do n=$(ls intro/${p%%:*} | wc -l); [ "$n" -eq "${p##*:}" ] || { echo "missing ${p%%:*} frames: $n"; exit 1; }; done
[ "$(ls frames | wc -l)" -eq 588 ] || { echo "story frames: $(ls frames | wc -l)"; exit 1; }
python3 "$E/make_card.py" "$F/card"
ffmpeg -y -loglevel error -framerate 12 -i intro/hook/%04d.png -vf "format=yuv420p" $ENC s1_hook.mp4
ffmpeg -y -loglevel error -framerate 12 -i intro/ident2/%04d.png -vf "format=yuv420p,fade=out:st=3.15:d=0.35" $ENC s2_ident.mp4
ffmpeg -y -loglevel error -framerate 24 -i card/%04d.png -vf "format=yuv420p" $ENC s3_card.mp4
ffmpeg -y -loglevel error -framerate 24 -i frames/%04d.png -vf "format=yuv420p,fade=out:st=23.9:d=0.6" $ENC s4_story.mp4
printf "file 's1_hook.mp4'\nfile 's2_ident.mp4'\nfile 's3_card.mp4'\nfile 's4_story.mp4'\n" > list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c copy video.mp4
# master: loudnorm alone stopped at -16.9 (one pass) and -16.3 (two pass + limiter), so:
# soft peak limiter -> two-pass linear loudnorm -> make-up gain measured with ebur128
PRE="alimiter=limit=0.5:attack=2:release=60:level=false"
M=$(ffmpeg -hide_banner -i "$E/out/ep1_draft_B.wav" -af "$PRE,loudnorm=I=-16:TP=-2.0:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/^{/,/^}/p')
v() { echo "$M" | python3 -c "import sys, json; print(json.load(sys.stdin)['$1'])"; }
LN="loudnorm=I=-16:TP=-2.0:LRA=11:measured_I=$(v input_i):measured_TP=$(v input_tp):measured_LRA=$(v input_lra):measured_thresh=$(v input_thresh):offset=$(v target_offset):linear=true"
# the second limiter keeps headroom for the ~0.5 dB of overs AAC adds; make-up gain comes last
ffmpeg -y -loglevel error -i "$E/out/ep1_draft_B.wav" -af "$PRE,$LN,alimiter=limit=0.7:attack=1:release=50:level=false" -ar 48000 master_pre.wav
I=$(ffmpeg -nostats -i master_pre.wav -af ebur128 -f null - 2>&1 | grep -E "^ +I:" | tail -1 | awk '{print $2}')
G=$(python3 -c "print(round(-16.0 - ($I), 2))"); echo "make-up gain ${G} dB"
ffmpeg -y -loglevel error -i master_pre.wav -af "volume=${G}dB" master.wav
ffmpeg -y -loglevel error -i video.mp4 -i master.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest worm_space_program_ep1.mp4
cp video.mp4 worm_space_program_ep1_silent.mp4
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames -of compact worm_space_program_ep1.mp4
ffmpeg -nostats -i worm_space_program_ep1.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "I:|Peak:" | tail -2
