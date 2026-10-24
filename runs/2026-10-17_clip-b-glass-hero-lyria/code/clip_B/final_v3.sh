C=/content/drive/MyDrive/renders/clip_B
for i in 1 2 3 4 5 6; do
  grep -q "^V3_DONE" /content/final_v3.log 2>/dev/null && break
  cd $C && /content/blender/blender -b --python final_v3.py >> /content/final_v3.log 2>&1
done
echo "$(date +%H:%M:%S) V3_EXIT" >> $C/progress.log
if ! grep -q "^V3_DONE" /content/final_v3.log; then echo "$(date +%H:%M:%S) STAGE4 not started: no V3_DONE, see /content/final_v3.log" >> $C/progress.log; exit 1; fi
for i in $(seq 1 720); do [ -f $C/v3/ASSEMBLY_READY ] && break; sleep 60; done
echo "$(date +%H:%M:%S) STAGE4 start" >> $C/progress.log
cd $C && python3 -u assemble_final.py > /content/assemble.log 2>&1; rc=$?
echo "$(date +%H:%M:%S) STAGE4_EXIT=$rc" >> $C/progress.log
