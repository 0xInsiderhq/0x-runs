# clip_B stage 4: final frames (1080x1920) -> flash / match cut, title, final card -> clip_clean.mp4, clip_tiktok.mp4 (lyrics subtitles), clip_x.mp4 (4:5 crop)
# sound: song_B + a quiet SFX layer (ducked under the vocal), master -16 LUFS / true peak <= -1.5 dBTP; H.264 High crf 17, AAC 256k 48 kHz, +faststart
import os, json, re, math, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
C = "/content/drive/MyDrive/renders/clip_B"; SRC = os.environ.get("A_SRC", f"{C}/final_frames"); WORK = os.environ.get("A_WORK", "/content/final_work"); OUTD = os.environ.get("A_OUT", C)
CLEAN, TIK = f"{WORK}/clean", f"{WORK}/tiktok"
W, H, N, CARD, FPS, SR = 1080, 1920, 1500, 1449, 24, 48000
T = json.load(open(f"{C}/timing.json")); ENV = json.load(open(f"{C}/audio/vocal_env.json"))["env"]
subprocess.run(f"rm -rf {WORK}; mkdir -p {CLEAN} {TIK}", shell=True)
FI = "/usr/share/fonts/opentype/inter/"; LB = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"; LR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
def load(f, d=SRC): return np.asarray(Image.open(f"{d}/f_{f:04d}.png").convert("RGB"), np.float32) / 255.0
def save(a, f, d=CLEAN): Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(f"{d}/f_{f:04d}.png", compress_level=1)
def blur(a, r): return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0
def tracked(dr, text, font, y, fill, track):
    w = sum(font.getlength(ch) for ch in text) + track * (len(text) - 1); x = (W - w) / 2
    for ch in text: dr.text((x, y), ch, font=font, fill=fill); x += font.getlength(ch) + track
    return w
done = set()
# ---- 2.0-2.44 s: bloom from the glowing nozzles, white only on 58-59 (peak 59 = the first beat) ----
for f in range(48, 59):
    a = load(f); t = (f - 47) / 11.0
    g = np.clip(blur(a, 6 + 44 * t) * (0.25 + 1.0 * t * t), 0, 1); o = 1 - (1 - a) * (1 - g)
    m = 0.85 if f == 58 else 0.15 * t ** 4
    save(o * (1 - m) + m, f); done.add(f)
save(np.ones((H, W, 3), np.float32), 59); done.add(59)
# ---- the white shrinks into one point = the first runway marker of S2 (match cut) ----
yy, xx = np.mgrid[0:H, 0:W]
for f in range(60, 70):
    a = load(f); e = (f - 59) / 10.0; lum = a.mean(axis=2)
    y0, y1, x0, x1 = int(H * 0.25), int(H * 0.8), int(W * 0.2), int(W * 0.8); sub = lum[y0:y1, x0:x1]
    ys, xs = np.nonzero(sub >= max(0.85, sub.max() - 0.05)); cy, cx = (ys.mean() + y0, xs.mean() + x0) if len(ys) else (H / 2, W / 2)
    R = 1040 * (1 - e) ** 3 + 8; d = np.hypot(yy - cy, xx - cx)
    disk = np.clip(1 - (d - R) / (0.35 * R + 12), 0, 1); halo = np.exp(-(d / (R + 60)) ** 2) * 0.5 * (1 - e)
    m = np.clip(np.maximum(disk, halo) + 0.45 * (1 - e) ** 4, 0, 1)[..., None]
    save(a * (1 - m) + m, f); done.add(f)
    if f == 60: print("flash point at", round(cx), round(cy), flush=True)
# ---- title 2.8-5.5 s: CLAUDE small, STILL IN CONTROL large, Inter, white with a soft glow, 0.4 s in / out, inside the 4:5 zone ----
lay = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(lay)
tracked(dr, "CLAUDE", ImageFont.truetype(FI + "Inter-Medium.otf", 36), 516, 255, 14)
tracked(dr, "STILL IN CONTROL", ImageFont.truetype(FI + "Inter-Bold.otf", 80), 572, 255, 3)
TL = np.asarray(lay, np.float32) / 255.0; TGl = blur(np.repeat(TL[..., None], 3, 2), 16)[..., 0] * 1.6
T0, T1, FDN = 67, 132, 10
for f in range(T0, T1 + 1):
    al = max(0.0, min(1.0, (f - T0) / FDN, (T1 - f) / FDN))
    base = load(f, CLEAN) if f in done else load(f)
    gl = np.clip(TGl * al, 0, 1)[..., None] * np.array([1.0, 0.93, 0.85], np.float32)
    o = 1 - (1 - base) * (1 - gl); tx = (TL * al)[..., None]
    save(o * (1 - tx) + tx, f); done.add(f)
# ---- final card from 60.384 s (line 2 2.5x, line 3 2x the v1 size) ----
def fits(text, font, track): return sum(font.getlength(ch) for ch in text) + track * (len(text) - 1)
F1, F2, F3 = ImageFont.truetype(LB, 100), ImageFont.truetype(LR, 100), ImageFont.truetype(LR, 60)
L2 = ["EVERY FRAME IS CODE"] if fits("EVERY FRAME IS CODE", F2, 25) <= 0.94 * W else ["EVERY FRAME", "IS CODE"]
rows = [("Claude Opus 5.5", F1, (245, 240, 235), 2, 100)] + [(t, F2, (255, 138, 61), 25, 100) for t in L2] + [("MUSIC · LYRIA 3.5", F3, (165, 160, 155), 16, 60)]
gaps = [68] + [24] * (len(L2) - 1) + [72]; y = H / 2 - (sum(r[4] for r in rows) + sum(gaps)) / 2
card = Image.new("RGB", (W, H), (0, 0, 0)); dc = ImageDraw.Draw(card)
for i, (t, fnt, col, tr, hh) in enumerate(rows):
    tracked(dc, t, fnt, y, col, tr); y += hh + (gaps[i] if i < len(gaps) else 0)
CARDA = np.asarray(card, np.float32) / 255.0
for f in range(CARD, N):
    k = min(f, CARD + 12); base = load(k) if os.path.exists(f"{SRC}/f_{k:04d}.png") else np.zeros((H, W, 3), np.float32)
    im = base * (1 - min(1.0, (f - CARD) / 12.0)); a = max(0.0, min(1.0, (f - CARD - 6) / 12.0))
    save(np.maximum(im, CARDA * a), f); done.add(f)
missing = []
for f in range(N):
    if f in done: continue
    s_ = f"{SRC}/f_{f:04d}.png"
    if os.path.exists(s_): os.symlink(s_, f"{CLEAN}/f_{f:04d}.png")
    else: missing.append(f)
print("clean frames ready, missing:", missing[:10], len(missing), flush=True)
assert not missing, "final frames missing"
# ---- TikTok version: lyrics subtitles (Inter SemiBold, white, soft dark shadow), lower part of the 4:5 zone, above the app UI ----
FS = ImageFont.truetype(FI + "Inter-SemiBold.otf", 56); SUBS = {}
for ln in T["lines"]:
    a, b = ln["start_frame"], ln["end_frame"]; text = ln["text"]; words = text.split(); rows_ = [text]
    if FS.getlength(text) > 0.84 * W:
        best = min(range(1, len(words)), key=lambda k: abs(FS.getlength(" ".join(words[:k])) - FS.getlength(" ".join(words[k:]))))
        rows_ = [" ".join(words[:best]), " ".join(words[best:])]
    lay = Image.new("L", (W, H), 0); d2 = ImageDraw.Draw(lay); y = 1400 - (len(rows_) - 1) * 70
    for r_ in rows_: d2.text(((W - FS.getlength(r_)) / 2, y), r_, font=FS, fill=255); y += 70
    TX = np.asarray(lay, np.float32) / 255.0; SH = blur(np.repeat(TX[..., None], 3, 2), 7)[..., 0]
    for f in range(a, b):
        al = max(0.0, min(1.0, (f - a + 1) / 3.0, (b - f) / 3.0)); SUBS[f] = (TX, SH, al)
for f in range(N):
    if f in SUBS:
        TX, SH, al = SUBS[f]; base = load(f, CLEAN); sh = np.clip(SH * 1.4 * al, 0, 0.75)[..., None]
        o = base * (1 - sh); tx = (TX * al)[..., None]; save(o * (1 - tx) + tx, f, TIK)
    else: os.symlink(os.path.realpath(f"{CLEAN}/f_{f:04d}.png"), f"{TIK}/f_{f:04d}.png")
print("tiktok frames ready:", len(SUBS), "subtitled", flush=True)
# ---- sound: song_B + quiet SFX, ducked under the vocal ----
raw = subprocess.run(f"ffmpeg -v error -i /content/drive/MyDrive/renders/song/song_B.mp3 -t 62.5 -f f32le -ac 2 -ar {SR} -", shell=True, capture_output=True).stdout
song = np.frombuffer(raw, np.float32).reshape(-1, 2).copy(); L = len(song); sfx = np.zeros(L, np.float32); rng = np.random.default_rng(7)
def lowpass(x, fc):
    fc = np.broadcast_to(np.asarray(fc, np.float64), x.shape); al_ = 1 - np.exp(-2 * np.pi * fc / SR); y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)): acc += al_[i] * (x[i] - acc); y[i] = acc
    return y
def put(sig, t0, gain_db):
    i0 = int(t0 * SR); n = min(len(sig), L - i0)
    if n > 0: sfx[i0:i0 + n] += (sig[:n] / (np.abs(sig).max() + 1e-9) * 10 ** (gain_db / 20)).astype(np.float32)
def hiss(dur, fc0, fc1, att=0.02, rel=0.3):
    n = int(dur * SR); t = np.arange(n) / SR; x = lowpass(rng.standard_normal(n), fc0 * (fc1 / fc0) ** (t / max(dur, 1e-3)))
    return x * np.minimum(1, t / att) * np.minimum(1, (dur - t) / rel)
def thump(dur=0.9, f0=90, f1=50, tau=0.22):
    n = int(dur * SR); t = np.arange(n) / SR; ph = 2 * np.pi * np.cumsum(f1 + (f0 - f1) * np.exp(-t / 0.04)) / SR
    nl = lowpass(rng.standard_normal(n), 900.0); return (np.sin(ph) * np.exp(-t / tau) + 0.6 * nl / (np.abs(nl).max() + 1e-9) * np.exp(-t / 0.05)) * np.minimum(1, t / 0.002)
n = int(0.438 * SR); t = np.arange(n) / SR                                           # riser 2.0-2.438 s + soft hit on the first beat (as in draft v2)
ris = 0.7 * lowpass(rng.standard_normal(n), 600 * (8000 / 600) ** (t / 0.438)); ris = ris / np.abs(ris).max() + 0.3 * np.sin(2 * np.pi * np.cumsum(180 * 4 ** (t / 0.438)) / SR)
put(ris * (t / 0.438) ** 2.2, 2.0, -22); put(thump(), 2.438, -12)
put(hiss(1.95, 1800, 1400, 0.3, 0.4), 0.05, -30)                                     # S1: the jets in heavy slow motion, a low hiss
def s10(f): u = max(0.0, (f - 634) / 185.0); return 119.0 + 185.0 * (0.15 * u + 0.85 * u ** 3.553 / 3.553)
def f_of(s0):
    f = 634.0
    while s10(f) < s0 and f < 822: f += 0.05
    return f
for s0, du in ((119, 9.6), (139, 7.2), (157, 9.6), (175, 4.3), (179, 6.0), (187, 4.8)):   # S10 jet pulses (stunt frames -> clip time)
    fa, fb = f_of(s0), f_of(s0 + du); put(hiss(max(0.25, (fb - fa) / FPS), 4500, 2500, 0.01, 0.15), fa / FPS, -24)
put(thump(1.1, 110, 45, 0.3), 822 / FPS, -14)                                        # touchdown on 'hit'
n = int(3.0 * SR); t = np.arange(n) / SR                                            # drift: tyre scrub + smoke hiss, fading
scr = lowpass(rng.standard_normal(n), 2500 + 800 * np.sin(2 * np.pi * 3.1 * t)) * np.exp(-t / 1.4) * np.minimum(1, t / 0.05)
put(scr, 823 / FPS, -22)
put(hiss(3.0, 1500, 600, 0.2, 1.5), 1365 / FPS, -30)                                # S14: the final exhale of the jets (slow motion)
envt = np.interp(np.arange(L) / SR * FPS, np.arange(len(ENV)), np.array(ENV, np.float64))
mix = song + (sfx * (1 - 0.6 * envt)).astype(np.float32)[:, None]; mix.astype(np.float32).tofile(f"{WORK}/mix.f32")
src = f"-f f32le -ar {SR} -ac 2 -i {WORK}/mix.f32"
p1 = subprocess.run(f"ffmpeg -hide_banner {src} -af loudnorm=I=-16:TP=-1.5:LRA=20:print_format=json -f null -", shell=True, capture_output=True, text=True).stderr
mm = json.loads(re.findall(r"\{[^{}]*\}", p1)[-1]); print("mix measured", {k: mm[k] for k in ("input_i", "input_tp", "input_lra")}, flush=True)
ln = (f"loudnorm=I=-16:TP=-1.5:LRA=20:measured_I={mm['input_i']}:measured_TP={mm['input_tp']}:measured_LRA={mm['input_lra']}"
      f":measured_thresh={mm['input_thresh']}:offset={mm['target_offset']}:linear=true")
subprocess.run(f"ffmpeg -y -v error {src} -af {ln},aresample=48000 -ar 48000 -c:a pcm_s24le {WORK}/mix.wav", shell=True)
# ---- encode ----
VC = "-c:v libx264 -profile:v high -preset slow -crf 17 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709"
AC = "-c:a aac -b:a 256k -ar 48000"
OUTS = [("clip_tiktok.mp4", TIK, ""), ("clip_clean.mp4", CLEAN, ""), ("clip_x.mp4", CLEAN, "-vf crop=1080:1350:0:285")]
info = {}
for name, d, vf in OUTS:
    out = f"{OUTD}/{name}"
    r = subprocess.run(f"ffmpeg -y -v error -framerate {FPS} -i {d}/f_%04d.png -i {WORK}/mix.wav -map 0:v -map 1:a {vf} {VC} {AC} -t 62.5 -movflags +faststart {out}",
                       shell=True, capture_output=True, text=True)
    pr = subprocess.run(f"ffprobe -v error -show_entries stream=codec_name,profile,width,height,r_frame_rate,nb_frames,pix_fmt,sample_rate,channels,bit_rate:format=duration,size,bit_rate -of json {out}",
                        shell=True, capture_output=True, text=True).stdout
    lo = subprocess.run(f"ffmpeg -hide_banner -i {out} -map 0:a -af ebur128=peak=true -f null -", shell=True, capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo); LRA = re.findall(r"LRA:\s+([\d.]+) LU", lo)
    info[name] = dict(ffprobe=json.loads(pr), I=float(I[-1]), TP=float(TP[-1]), LRA=float(LRA[-1]), err=r.stderr[-300:])
    print(name, "I", I[-1], "TP", TP[-1], "LRA", LRA[-1], os.path.getsize(out), r.stderr[-200:], flush=True)
bad = [k for k, v in info.items() if v["TP"] > -1.5 or abs(v["I"] + 16) > 0.5]
print("LOUDNESS_CHECK", "OK" if not bad else f"OUT OF SPEC: {bad}", flush=True)
json.dump(info, open(f"{OUTD}/stage4_info.json", "w"), indent=1)
print("STAGE4_DONE", flush=True)
