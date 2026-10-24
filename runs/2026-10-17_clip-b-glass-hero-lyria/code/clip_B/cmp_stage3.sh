#!/bin/bash
# stage 3 quality test: full 1080x1920, adaptive 0.02 + OIDN, final volume step, frames S3 (230) and the heaviest S10 (816, motion blur on)
cd /content/drive/MyDrive/renders/clip_B
for SPP in 32 64 128; do
  DRAFT_OUT=/content/cmp/$SPP DRAFT_STEP=1.0 DRAFT_ADAPT=0.02 DRAFT_WARMUP=1 /content/blender/blender -b --python clip_draft.py -- 230,816 $SPP 100 > /content/cmp_$SPP.log 2>&1
  grep '^DRAFT f=' /content/cmp_$SPP.log | sed "s/^/spp=$SPP /" >> /content/cmp_times.txt
done
echo CMP_DONE >> /content/cmp_times.txt
