import os, re, time, subprocess
D = "/content/drive/MyDrive/renders/stunt/frames"; LOG = "/content/render.log"
done = sorted(f for f in os.listdir(D) if f.endswith(".png") and os.path.getsize(os.path.join(D, f)) > 0) if os.path.isdir(D) else []
log = open(LOG).read() if os.path.exists(LOG) else ""
t = [int(a) * 60 + float(b) for a, b in re.findall(r"^Time: (\d+):([\d.]+)", log, re.M)][-30:]
avg = sum(t) / len(t) if t else 0
run = subprocess.run("pgrep -f '[s]tunt.blend --python gpu_on.py -a'", shell=True).returncode == 0
print(f"frames {len(done)}/360  last {done[-1] if done else '-'}  avg {avg:.1f} s/frame  ETA {(360 - len(done)) * avg / 60:.0f} min  rendering={run}")
if "RENDER_EXIT" in log: print(log.strip().splitlines()[-1])
