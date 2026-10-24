# clip_B stage 2 v2 assembly: S1 -> S2 white flash + match cut into the first marker, title, final card,
# song_B + quiet riser (2.0-2.44 s) + soft hit on the first beat -> draft_clip_v2.mp4 and a short S1-S4 cut
import os, json, re, subprocess, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
C = "/content/drive/MyDrive/renders/clip_B"; SRC = f"{C}/draft_frames"; DST = "/content/draft_v2_final"
W, H, N, CARD, FPS = 540, 960, 1500, 1449, 24
subprocess.run(f"rm -rf {DST}; mkdir -p {DST}", shell=True)
FI = "/usr/share/fonts/opentype/inter/"; LB = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"; LR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
def load(f, d=SRC): return np.asarray(Image.open(f"{d}/f_{f:04d}.png").convert("RGB"), np.float32) / 255.0
def save(a, f): Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(f"{DST}/f_{f:04d}.png")
def blur(a, r): return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0
done = set()
# 2.0-2.44 s: bloom grows from the glowing nozzles; white >= 80 % only on frames 58-60 (peak 59 = 2.458 s, the first beat)
for f in range(48, 59):
    a = load(f); t = (f - 47) / 11.0
    g = np.clip(blur(a, 3 + 22 * t) * (0.25 + 1.0 * t * t), 0, 1); o = 1 - (1 - a) * (1 - g)
    m = 0.85 if f == 58 else 0.15 * t ** 4                                        # only 58-59 go (almost) white: no long flash on a phone
    save(o * (1 - m) + m, f); done.add(f)
save(np.ones((H, W, 3), np.float32), 59); done.add(59)
# 2.46-2.88 s: the white shrinks into one point, which is the first runway marker of S2 (match cut)
yy, xx = np.mgrid[0:H, 0:W]
for f in range(60, 70):
    a = load(f); e = (f - 59) / 10.0; lum = a.mean(axis=2)
    y0, y1, x0, x1 = int(H * 0.25), int(H * 0.8), int(W * 0.2), int(W * 0.8); sub = lum[y0:y1, x0:x1]
    ys, xs = np.nonzero(sub >= max(0.85, sub.max() - 0.05)); cy, cx = (ys.mean() + y0, xs.mean() + x0) if len(ys) else (H / 2, W / 2)
    R = 520 * (1 - e) ** 3 + 4; d = np.hypot(yy - cy, xx - cx)
    disk = np.clip(1 - (d - R) / (0.35 * R + 6), 0, 1); halo = np.exp(-(d / (R + 30)) ** 2) * 0.5 * (1 - e)
    m = np.clip(np.maximum(disk, halo) + 0.45 * (1 - e) ** 4, 0, 1)[..., None]
    save(a * (1 - m) + m, f); done.add(f)
    if f == 60: print("flash point at", round(cx), round(cy))
# title 2.8-5.5 s: CLAUDE small on top, STILL IN CONTROL large below, Inter, white with a soft glow, 0.4 s in / out, inside the 4:5 zone
def tracked(dr, text, font, y, fill, track):
    w = sum(font.getlength(ch) for ch in text) + track * (len(text) - 1); x = (W - w) / 2
    for ch in text: dr.text((x, y), ch, font=font, fill=fill); x += font.getlength(ch) + track
    return w
lay = Image.new("L", (W, H), 0); dr = ImageDraw.Draw(lay)
w1 = tracked(dr, "CLAUDE", ImageFont.truetype(FI + "Inter-Medium.otf", 18), 258, 255, 7)
w2 = tracked(dr, "STILL IN CONTROL", ImageFont.truetype(FI + "Inter-Bold.otf", 40), 286, 255, 1.5); print("title widths", round(w1), round(w2))
TL = np.asarray(lay, np.float32) / 255.0; TGl = blur(np.repeat(TL[..., None], 3, 2), 8)[..., 0] * 1.6
T0, T1, FD = 67, 132, 10
for f in range(T0, T1 + 1):
    al = min(1.0, (f - T0) / FD, (T1 - f) / FD); al = max(0.0, al)
    base = load(f, DST) if f in done else load(f)
    gl = np.clip(TGl * al, 0, 1)[..., None] * np.array([1.0, 0.93, 0.85], np.float32)
    o = 1 - (1 - base) * (1 - gl); tx = (TL * al)[..., None]
    save(o * (1 - tx) + tx, f); done.add(f)
# final card from 60.384 s: line 2 2.5x, line 3 2x larger than in v1 (readable on a phone)
def fits(text, font, track): return sum(font.getlength(ch) for ch in text) + track * (len(text) - 1)
F1, F2, F3 = ImageFont.truetype(LB, 50), ImageFont.truetype(LR, 50), ImageFont.truetype(LR, 30)
L2 = ["EVERY FRAME IS CODE"] if fits("EVERY FRAME IS CODE", F2, 12.5) <= 0.94 * W else ["EVERY FRAME", "IS CODE"]
rows = [("Claude Opus 5.5", F1, (245, 240, 235), 1, 50)] + [(t, F2, (255, 138, 61), 12.5, 50) for t in L2] + [("MUSIC · LYRIA 3.5", F3, (165, 160, 155), 8, 30)]
gaps = [34] + [12] * (len(L2) - 1) + [36]; hblk = sum(r[4] for r in rows) + sum(gaps); y = 480 - hblk / 2
card = Image.new("RGB", (W, H), (0, 0, 0)); dc = ImageDraw.Draw(card)
for i, (t, fnt, col, tr, hh) in enumerate(rows):
    tracked(dc, t, fnt, y, col, tr); y += hh + (gaps[i] if i < len(gaps) else 0)
print("card line 2:", L2)
CARDA = np.asarray(card, np.float32) / 255.0
for f in range(CARD, N):
    k = min(f, CARD + 12); base = load(k) if os.path.exists(f"{SRC}/f_{k:04d}.png") else np.zeros((H, W, 3), np.float32)
    im = base * (1 - min(1.0, (f - CARD) / 12.0)); a = max(0.0, min(1.0, (f - CARD - 6) / 12.0))
    save(np.maximum(im, CARDA * a), f); done.add(f)
missing = []
for f in range(N):
    if f in done: continue
    s_ = f"{SRC}/f_{f:04d}.png"
    if os.path.exists(s_): os.symlink(s_, f"{DST}/f_{f:04d}.png")
    else: missing.append(f)
print("frames ready, missing:", missing[:10], len(missing))
# sound: song_B + a quiet riser 2.0-2.44 s + a soft hit on the first beat 2.438 s, mixed to -16 LUFS / TP -1.5
SR = 48000; SONG = "/content/drive/MyDrive/renders/song/song_B.mp3"
raw = subprocess.run(f"ffmpeg -v error -i {SONG} -t 62.5 -f f32le -ac 2 -ar {SR} -", shell=True, capture_output=True).stdout
song = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
rng = np.random.default_rng(3); sfx = np.zeros(len(song), np.float32)
t0, t1 = 2.0, 2.438; n = int((t1 - t0) * SR); tt = np.arange(n) / SR; T = t1 - t0
noise = rng.standard_normal(n).astype(np.float32); lp = np.zeros(n, np.float32); acc = 0.0
fc = 600 * (8000 / 600) ** (tt / T); al_ = 1 - np.exp(-2 * np.pi * fc / SR)
for i in range(n): acc += al_[i] * (noise[i] - acc); lp[i] = acc
ph = 2 * np.pi * np.cumsum(180 * (720 / 180) ** (tt / T)) / SR
riser = (0.7 * lp / (np.abs(lp).max() + 1e-9) + 0.3 * np.sin(ph)) * (tt / T) ** 2.2
sfx[int(t0 * SR):int(t0 * SR) + n] += riser * 10 ** (-22 / 20)
m_ = int(0.9 * SR); th = np.arange(m_) / SR; fq = 50 + 45 * np.exp(-th / 0.04); ph2 = 2 * np.pi * np.cumsum(fq) / SR
nb = rng.standard_normal(m_).astype(np.float32); nl = np.zeros(m_, np.float32); acc = 0.0
for i in range(m_): acc += 0.08 * (nb[i] - acc); nl[i] = acc
hit = (np.sin(ph2) * np.exp(-th / 0.22) + 0.6 * nl / (np.abs(nl).max() + 1e-9) * np.exp(-th / 0.05)) * np.minimum(1.0, th / 0.002)
hit /= np.abs(hit).max(); i0 = int(2.438 * SR); sfx[i0:i0 + m_] += hit[:len(sfx) - i0] * 10 ** (-12 / 20)
mix = song + sfx[:, None]; mix.astype(np.float32).tofile("/content/mix_v2.f32")
src = f"-f f32le -ar {SR} -ac 2 -i /content/mix_v2.f32"
p1 = subprocess.run(f"ffmpeg -hide_banner {src} -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null -", shell=True, capture_output=True, text=True).stderr
mm = json.loads(re.findall(r"\{[^{}]*\}", p1)[-1])
ln = f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={mm['input_i']}:measured_TP={mm['input_tp']}:measured_LRA={mm['input_lra']}:measured_thresh={mm['input_thresh']}:offset={mm['target_offset']}:linear=true"
subprocess.run(f"ffmpeg -y -v error {src} -af {ln},aresample=48000 -ar 48000 -c:a pcm_s16le /content/mix_v2.wav", shell=True)
for out, dur in ((f"{C}/draft_clip_v2.mp4", 62.5), (f"{C}/draft_v2_S1-S4.mp4", 332 / FPS)):
    r = subprocess.run(f"ffmpeg -y -v error -framerate {FPS} -i {DST}/f_%04d.png -i /content/mix_v2.wav -map 0:v -map 1:a -c:v libx264 -profile:v high -preset slow -crf 18 "
                       f"-pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -t {dur:.3f} -movflags +faststart {out}", shell=True, capture_output=True, text=True)
    print(out, r.stderr[-300:])
    print(subprocess.run(f"ffprobe -v error -show_entries stream=codec_name,profile,width,height,r_frame_rate,nb_frames,sample_rate:format=duration,size -of compact {out}", shell=True, capture_output=True, text=True).stdout)
lo = subprocess.run(f"ffmpeg -hide_banner -i {C}/draft_clip_v2.mp4 -map 0:a -af ebur128=peak=true -f null -", shell=True, capture_output=True, text=True).stderr
print("\n".join(l for l in lo.splitlines()[-12:] if l.strip()))
print("ASSEMBLY_DONE")
