# clip_B stage 4 (short structure): final frames 0-1055 (0-44.0 s) -> flash / match cut, title, then the final card 2 s over the last S12 frame
# (~46 s): clip_clean.mp4, clip_tiktok.mp4 (lyrics subtitles), clip_x.mp4 (1080x1350 centre crop: hook S1 + 20.5-44.0 s, the same fade and card,
# the sound spliced on a beat with a 0.25 s crossfade). Song fades from the strong beat near 42.5 s to 44.0 s; a quiet SFX layer ducked under the
# vocal; each output -16 LUFS / true peak <= -1.5 dBTP (two-pass loudnorm, linear); H.264 High crf 17, AAC 256k 48 kHz, +faststart; ffprobe +
# loudness check -> stage4_info.json, report.md. Missing v3 frames fall back to old_hero/.
import os, json, re, math, subprocess, time, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
C = "/content/drive/MyDrive/renders/clip_B"; SRC = os.environ.get("A_SRC", f"{C}/final_frames"); OLDH = f"{C}/old_hero"
WORK = os.environ.get("A_WORK", "/content/final_work"); OUTD = os.environ.get("A_OUT", C)
CLEAN, TIK = f"{WORK}/clean", f"{WORK}/tiktok"
os.makedirs(OUTD, exist_ok=True)
W, H, FPS, SR = 1080, 1920, 24, 48000
END = 1056                                   # 44.0 s: frames 0..1055 of the clip
LAST = 1059                                  # the last S12 frame: the card sits over it
CARDN = 48                                   # 2.0 s of card
N = END + CARDN                              # 1104 frames = 46.0 s
T = json.load(open(f"{C}/timing.json")); ENV = json.load(open(f"{C}/audio/vocal_env.json"))["env"]
subprocess.run(f"rm -rf {WORK}; mkdir -p {CLEAN} {TIK}", shell=True)
FI = "/usr/share/fonts/opentype/inter/"; LB = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"; LR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FB = os.environ.get("A_FALLBACK")            # dry runs only: frames still missing come from here (resized), never set for the real assembly
def srcp(f):
    if FB and 140 <= f <= 633:                   # dry run next to the v3 render (it moves these frames): take a stable copy
        os.makedirs(f"{WORK}/fb", exist_ok=True); r = f"{WORK}/fb/f_{f:04d}.png"
        if os.path.exists(r): return r
        for q in (f"{SRC}/f_{f:04d}.png", f"{OLDH}/f_{f:04d}.png", f"{FB}/f_{f:04d}.png"):
            try:
                if os.path.getsize(q) != 4096: Image.open(q).convert("RGB").resize((W, H)).save(r, compress_level=1); return r
            except (FileNotFoundError, OSError): pass
        return None
    p = f"{SRC}/f_{f:04d}.png"
    if os.path.exists(p) and os.path.getsize(p) != 4096: return p
    q = f"{OLDH}/f_{f:04d}.png"
    if os.path.exists(q): return q
    if FB and os.path.exists(f"{FB}/f_{f:04d}.png"):
        os.makedirs(f"{WORK}/fb", exist_ok=True); r = f"{WORK}/fb/f_{f:04d}.png"
        if not os.path.exists(r): Image.open(f"{FB}/f_{f:04d}.png").convert("RGB").resize((W, H)).save(r, compress_level=1)
        return r
    return None
def load(f, d=None):
    p = f"{d}/f_{f:04d}.png" if d else srcp(f); return np.asarray(Image.open(p).convert("RGB"), np.float32) / 255.0
def save(a, f, d=CLEAN): Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(f"{d}/f_{f:04d}.png", compress_level=1)
def blur(a, r): return np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0
def tracked(dr, text, font, y, fill, track):
    w = sum(font.getlength(ch) for ch in text) + track * (len(text) - 1); x = (W - w) / 2
    for ch in text: dr.text((x, y), ch, font=font, fill=fill); x += font.getlength(ch) + track
    return w
def btime(b): return float(b.get("t", b.get("time", b["frame"] / FPS))) if isinstance(b, dict) else float(b) / FPS
def strong_beat(t_target, lo, hi):
    cands = [b for b in T["beats"] if lo <= btime(b) <= hi]
    key = next((k for k in ("downbeat", "strong", "accent", "strength", "energy") if cands and isinstance(cands[0], dict) and k in cands[0]), None)
    if key:
        b_ = max(cands, key=lambda b: (float(b[key]), -abs(btime(b) - t_target))); return btime(b_), (key if float(b_[key]) else "nearest beat")
    return btime(min(cands, key=lambda b: abs(btime(b) - t_target))), "nearest beat"
FADE_T, fade_how = strong_beat(42.5, 41.9, 43.0)                                       # the song fades from here to 44.0 s
CUT_T, cut_how = strong_beat(20.5, 20.0, 21.0)                                        # clip_x: the main part starts on this beat
HOOK_N = 59                                                                           # clip_x hook: S1 frames 0-58 (to the flash on the first beat, 2.438 s)
print(f"fade from {FADE_T:.3f} s ({fade_how}), clip_x cut at {CUT_T:.3f} s ({cut_how})", flush=True)
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
# ---- final card (as approved: line 2 2.5x, line 3 2x the v1 size), 2 s over the last S12 frame: the frame dims, the card fades in ----
def fits(text, font, track): return sum(font.getlength(ch) for ch in text) + track * (len(text) - 1)
F1, F2, F3 = ImageFont.truetype(LB, 100), ImageFont.truetype(LR, 100), ImageFont.truetype(LR, 60)
L2 = ["EVERY FRAME IS CODE"] if fits("EVERY FRAME IS CODE", F2, 25) <= 0.94 * W else ["EVERY FRAME", "IS CODE"]
rows = [("Claude Opus 5.5", F1, (245, 240, 235), 2, 100)] + [(t, F2, (255, 138, 61), 25, 100) for t in L2] + [("MUSIC · LYRIA 3.5", F3, (165, 160, 155), 16, 60)]
gaps = [68] + [24] * (len(L2) - 1) + [72]; y = H / 2 - (sum(r[4] for r in rows) + sum(gaps)) / 2
card = Image.new("RGB", (W, H), (0, 0, 0)); cmask = Image.new("L", (W, H), 0); dc = ImageDraw.Draw(card); dm = ImageDraw.Draw(cmask)
for i, (t, fnt, col, tr, hh) in enumerate(rows):
    tracked(dc, t, fnt, y, col, tr); tracked(dm, t, fnt, y, 255, tr); y += hh + (gaps[i] if i < len(gaps) else 0)
CARDA = np.asarray(card, np.float32) / 255.0; CM = np.asarray(cmask, np.float32) / 255.0; CSH = blur(np.repeat(CM[..., None], 3, 2), 10)[..., 0]
BG = load(LAST)
for k in range(CARDN):
    f = END + k; e = min(1.0, k / 12.0); a = max(0.0, min(1.0, (k - 4) / 12.0))
    bg = BG * (1 - 0.62 * e); sh = np.clip(CSH * 1.3 * a, 0, 0.8)[..., None]; m = (CM * a)[..., None]
    save((bg * (1 - sh)) * (1 - m) + CARDA * m, f); done.add(f)
missing = []
for f in range(END):
    if f in done: continue
    s_ = srcp(f)
    if s_: os.symlink(s_, f"{CLEAN}/f_{f:04d}.png")
    else: missing.append(f)
print("clean frames ready, missing:", missing[:10], len(missing), flush=True)
assert not missing, "final frames missing"
# ---- TikTok version: lyrics subtitles (Inter SemiBold, white, soft dark shadow) inside 0-44 s ----
FS = ImageFont.truetype(FI + "Inter-SemiBold.otf", 56); SUBS = {}
for ln in T["lines"]:
    a, b = ln["start_frame"], min(ln["end_frame"], END); text = ln["text"]; words = text.split(); rows_ = [text]
    if a >= END - 6: continue
    if FS.getlength(text) > 0.84 * W:
        best = min(range(1, len(words)), key=lambda k: abs(FS.getlength(" ".join(words[:k])) - FS.getlength(" ".join(words[k:]))))
        rows_ = [" ".join(words[:best]), " ".join(words[best:])]
    lay = Image.new("L", (W, H), 0); d2 = ImageDraw.Draw(lay); y = 1400 - (len(rows_) - 1) * 70
    for r_ in rows_: d2.text(((W - FS.getlength(r_)) / 2, y), r_, font=FS, fill=255); y += 70
    TX = np.asarray(lay, np.float32) / 255.0; SHd = blur(np.repeat(TX[..., None], 3, 2), 7)[..., 0]
    for f in range(a, b):
        al = max(0.0, min(1.0, (f - a + 1) / 3.0, (b - f) / 3.0)); SUBS[f] = (TX, SHd, al)
for f in range(N):
    if f in SUBS:
        TX, SHd, al = SUBS[f]; base = load(f, CLEAN); sh = np.clip(SHd * 1.4 * al, 0, 0.75)[..., None]
        o = base * (1 - sh); tx = (TX * al)[..., None]; save(o * (1 - tx) + tx, f, TIK)
    else: os.symlink(os.path.realpath(f"{CLEAN}/f_{f:04d}.png"), f"{TIK}/f_{f:04d}.png")
print("tiktok frames ready:", len(SUBS), "subtitled", flush=True)
# ---- clip_x frames: hook S1 (0-58) + the main part from the cut beat to 44.0 s + the card ----
XD = f"{WORK}/x"; os.makedirs(XD, exist_ok=True); CUT_F = int(round(CUT_T * FPS)); xs_ = list(range(HOOK_N)) + list(range(CUT_F, N))
for i, f in enumerate(xs_): os.symlink(os.path.realpath(f"{CLEAN}/f_{f:04d}.png"), f"{XD}/f_{i:04d}.png")
NX = len(xs_); print("clip_x frames:", NX, f"(hook {HOOK_N}, main {CUT_F}-{N - 1})", flush=True)
# ---- sound: song_B + quiet SFX ducked under the vocal (0-44 s), fade from the strong beat to 44.0 s, silence under the card ----
raw = subprocess.run(f"ffmpeg -v error -i /content/drive/MyDrive/renders/song/song_B.mp3 -t 44.0 -f f32le -ac 2 -ar {SR} -", shell=True, capture_output=True).stdout
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
n = int(0.438 * SR); t = np.arange(n) / SR                                           # riser 2.0-2.438 s + soft hit on the first beat
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
envt = np.interp(np.arange(L) / SR * FPS, np.arange(len(ENV)), np.array(ENV, np.float64))
mix = song + (sfx * (1 - 0.6 * envt)).astype(np.float32)[:, None]
ts = np.arange(L) / SR; fade = np.clip((44.0 - ts) / (44.0 - FADE_T), 0, 1); fade = np.where(ts < FADE_T, 1.0, 0.5 - 0.5 * np.cos(np.pi * fade))
mix = (mix * fade[:, None]).astype(np.float32)
CARD_S = np.zeros((int(CARDN / FPS * SR), 2), np.float32)
main = np.concatenate([mix, CARD_S])
xf = int(0.25 * SR); h0 = int(HOOK_N / FPS * SR); c0 = int(CUT_T * SR)                # clip_x: hook to the first beat, crossfade 0.25 s into the cut beat
A = mix[:h0 + xf // 2].copy(); Bx = mix[c0 - xf // 2:].copy(); ramp = (0.5 - 0.5 * np.cos(np.pi * np.arange(xf) / xf)).astype(np.float32)[:, None]
xmix = np.concatenate([A[:-xf], A[-xf:] * (1 - ramp) + Bx[:xf] * ramp, Bx[xf:], CARD_S])
def master(sig, name):
    sig.astype(np.float32).tofile(f"{WORK}/{name}.f32"); src = f"-f f32le -ar {SR} -ac 2 -i {WORK}/{name}.f32"
    p1 = subprocess.run(f"ffmpeg -hide_banner {src} -af loudnorm=I=-16:TP=-1.5:LRA=20:print_format=json -f null -", shell=True, capture_output=True, text=True).stderr
    mm = json.loads(re.findall(r"\{[^{}]*\}", p1)[-1]); print(name, "measured", {k: mm[k] for k in ("input_i", "input_tp", "input_lra")}, flush=True)
    ln = (f"loudnorm=I=-16:TP=-1.5:LRA=20:measured_I={mm['input_i']}:measured_TP={mm['input_tp']}:measured_LRA={mm['input_lra']}"
          f":measured_thresh={mm['input_thresh']}:offset={mm['target_offset']}:linear=true")
    subprocess.run(f"ffmpeg -y -v error {src} -af {ln},aresample=48000 -ar 48000 -c:a pcm_s24le {WORK}/{name}.wav", shell=True)
    return f"{WORK}/{name}.wav"
WAV = master(main, "mix_main"); WAVX = master(xmix, "mix_x")
# ---- encode + checks ----
VC = "-c:v libx264 -profile:v high -preset slow -crf 17 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709"
AC = "-c:a aac -b:a 256k -ar 48000"
OUTS = [("clip_tiktok.mp4", TIK, WAV, "", N), ("clip_clean.mp4", CLEAN, WAV, "", N), ("clip_x.mp4", XD, WAVX, "-vf crop=1080:1350:0:285", NX)]
info = dict(fade_from_s=round(FADE_T, 3), fade_beat=fade_how, x_cut_s=round(CUT_T, 3), x_cut_beat=cut_how, x_hook_frames=HOOK_N)
for name, d, wav, vf, nf in OUTS:
    out = f"{OUTD}/{name}"; dur = nf / FPS
    r = subprocess.run(f"ffmpeg -y -v error -framerate {FPS} -i {d}/f_%04d.png -i {wav} -map 0:v -map 1:a {vf} {VC} {AC} -t {dur:.4f} -movflags +faststart {out}",
                       shell=True, capture_output=True, text=True)
    pr = subprocess.run(f"ffprobe -v error -show_entries stream=codec_name,profile,width,height,r_frame_rate,nb_frames,pix_fmt,sample_rate,channels,bit_rate:format=duration,size,bit_rate -of json {out}",
                        shell=True, capture_output=True, text=True).stdout
    lo = subprocess.run(f"ffmpeg -hide_banner -i {out} -map 0:a -af ebur128=peak=true -f null -", shell=True, capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo); LRA = re.findall(r"LRA:\s+([\d.]+) LU", lo)
    info[name] = dict(ffprobe=json.loads(pr), I=float(I[-1]), TP=float(TP[-1]), LRA=float(LRA[-1]), seconds=round(dur, 3), err=r.stderr[-300:])
    print(name, "dur", round(dur, 2), "I", I[-1], "TP", TP[-1], "LRA", LRA[-1], os.path.getsize(out), r.stderr[-200:], flush=True)
bad = [k for k in ("clip_tiktok.mp4", "clip_clean.mp4", "clip_x.mp4") if info[k]["TP"] > -1.5 or abs(info[k]["I"] + 16) > 0.5]
info["loudness_check"] = "OK" if not bad else f"OUT OF SPEC: {bad}"; print("LOUDNESS_CHECK", info["loudness_check"], flush=True)
json.dump(info, open(f"{OUTD}/stage4_info.json", "w"), indent=1)
# ---- report.md ----
PL = open(f"{C}/progress.log").read().splitlines()
def grab(pat): return [l for l in PL if re.search(pat, l)]
v3n = grab(r"^.{9}V3_DONE"); rexit = grab(r"^RENDER_EXIT=")
def vinfo(k):
    v = info[k]; s = [x for x in v["ffprobe"]["streams"] if x.get("codec_name") == "h264"][0]; a = [x for x in v["ffprobe"]["streams"] if x.get("codec_name") == "aac"][0]
    return f"| {k} | {s['width']}x{s['height']} | {float(v['ffprobe']['format']['duration']):.2f} s | {s.get('profile')} | {a.get('sample_rate')} Hz | {v['I']:.1f} LUFS | {v['TP']:.1f} dBTP | {int(v['ffprobe']['format']['size']) / 1e6:.1f} MB |"
rep = f"""# clip_B — отчёт (этап 4)

Собрано {time.strftime('%Y-%m-%d %H:%M')} UTC, автоматически после последнего кадра.

## Структура
- Основная версия: 0–44.0 с клипа, песня затухает с {FADE_T:.2f} с ({fade_how}) до 44.0 с, затем финальная карточка 2 с поверх последнего кадра S12 (кадр {LAST}). Итого {N / FPS:.1f} с.
- S13 и S14 не рендерились (по решению), в сборку не входят.
- Герой v3 в S3, S5, S8b, S9 (одобренные стиллы, микродвижение CMU + дыхание); старые кадры S3/S5 — в old_hero/.
- clip_x: кроп 1080x1350 по центру, хук S1 (кадры 0–{HOOK_N - 1}) + {CUT_T:.2f}–44.0 с (склейка на долю, {cut_how}), звук с кроссфейдом 0.25 с, то же затухание и карточка.

## Рендер
- Blender 4.5.14, Cycles на Colab L4, 1080x1920, 64 spp, adaptive 0.02, OIDN, volume step 1.0.
- Основной рендер: {rexit[-1].strip() if rexit else 'см. progress.log'}.
- Герой v3: {v3n[-1].strip()[9:] if v3n else 'см. progress.log'}.
- S12: первые ~45 кадров по 340–490 с (дым заноса из S11), остальное ~34 с; тест облегчённых настроек не понадобился — S12 был готов до теста.
- Юниты: L4 ≈ 1.54 CU/ч (по панели ресурсов Colab).

## Файлы
| файл | кадр | длительность | профиль | аудио | громкость | true peak | размер |
|---|---|---|---|---|---|---|---|
{vinfo('clip_tiktok.mp4')}
{vinfo('clip_clean.mp4')}
{vinfo('clip_x.mp4')}

Проверка громкости: {info['loudness_check']} (цель −16 LUFS, TP ≤ −1.5 dBTP). Кодеки: H.264 High crf 17, yuv420p, bt709; AAC 256k 48 кГц; +faststart.

## Что было не так
- Среда Colab дважды сбрасывалась (ночью и после конца основного рендера): восстановление по логу, кадры на Drive не терялись.
- В S12 дым от заноса сделал первые кадры в ~13 раз дороже обычных.
- В S6–S12 (кроме S8b и S9) в кабине мелко виден старый герой: эти планы отрендерены до решения по v3 и по договорённости идут как есть.
"""
open(f"{OUTD}/report.md", "w").write(rep)
print("STAGE4_DONE", flush=True)
