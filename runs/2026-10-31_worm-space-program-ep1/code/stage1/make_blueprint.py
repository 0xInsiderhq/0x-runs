import os
import random, math
from PIL import Image, ImageDraw, ImageFilter
random.seed(7)
W, H = 1024, 1280
paper = Image.new('RGBA', (W, H), (226, 214, 188, 255))
px = paper.load()
# fibres and stains
d = ImageDraw.Draw(paper)
for i in range(2500):
    x, y = random.randrange(W), random.randrange(H)
    c = random.randint(200, 235)
    d.line([(x, y), (x + random.randint(-12, 12), y + random.randint(-4, 4))], fill=(c, c - 10, c - 30, 255), width=1)
for i in range(6):
    x, y, r = random.randrange(W), random.randrange(H), random.randint(60, 180)
    stain = Image.new('L', (W, H), 0)
    ImageDraw.Draw(stain).ellipse([x - r, y - r, x + r, y + r], fill=40)
    stain = stain.filter(ImageFilter.GaussianBlur(40))
    brown = Image.new('RGBA', (W, H), (150, 115, 70, 255))
    paper = Image.composite(brown, paper, stain)
ink = Image.new('L', (W, H), 0)
di = ImageDraw.Draw(ink)
def stroke(p0, p1, w=9, passes=3, jit=4, val=220):
    for k in range(passes):
        pts = []
        n = max(2, int(math.dist(p0, p1) / 14))
        for i in range(n + 1):
            t = i / n
            x = p0[0] + (p1[0] - p0[0]) * t + random.uniform(-jit, jit)
            y = p0[1] + (p1[1] - p0[1]) * t + random.uniform(-jit, jit)
            pts.append((x, y))
        di.line(pts, fill=random.randint(val - 60, val), width=max(2, w + random.randint(-2, 2)))
def ellipse(cx, cy, rx, ry, w=7, val=220, a0=0, a1=360):
    pts = []
    for a in range(a0, a1 + 1, 6):
        r = math.radians(a)
        pts.append((cx + rx * math.cos(r) + random.uniform(-3, 3), cy + ry * math.sin(r) + random.uniform(-3, 3)))
    for k in range(2):
        di.line(pts, fill=random.randint(val - 50, val), width=w)
cx = 512
# can body
top, bot, hw = 430, 900, 150
stroke((cx - hw, top), (cx - hw, bot)); stroke((cx + hw, top), (cx + hw, bot))
ellipse(cx, top, hw, 30); ellipse(cx, bot, hw, 30, a0=0, a1=180)
for y in range(top + 70, bot - 40, 60):
    ellipse(cx, y, hw, 24, w=3, val=150, a0=0, a1=180)
# cone
stroke((cx - hw, top), (cx, 170)); stroke((cx + hw, top), (cx, 170))
for k in range(5):
    stroke((cx - hw + 30 * k, top - 10), (cx - 10 + 4 * k, 200), w=2, passes=1, val=120)
# side caps (three circles)
for i, y in enumerate([560, 660, 760]):
    ellipse(cx + hw + 4, y, 26, 26, w=5)
# legs
stroke((cx - hw + 20, bot - 20), (cx - hw - 110, bot + 190)); stroke((cx + hw - 20, bot - 20), (cx + hw + 110, bot + 190))
for x in (cx - hw - 110, cx + hw + 110):
    ellipse(x, bot + 200, 14, 10, w=8, val=250)
# THE NOZZLE: bottle cap under the can, emphasised
ellipse(cx, bot + 52, 70, 22, w=8, val=250)
stroke((cx - 70, bot + 52), (cx - 62, bot + 90), w=8); stroke((cx + 70, bot + 52), (cx + 62, bot + 90), w=8)
ellipse(cx, bot + 90, 62, 18, w=8, val=250, a0=0, a1=180)
for k in range(-3, 4):
    stroke((cx + k * 18, bot + 112), (cx + k * 26, bot + 175 + abs(k) * -6), w=4, passes=2, val=200)
# arrow pointing at nozzle (no text)
stroke((cx + 330, bot + 160), (cx + 95, bot + 75), w=6)
stroke((cx + 95, bot + 75), (cx + 140, bot + 70), w=6); stroke((cx + 95, bot + 75), (cx + 120, bot + 115), w=6)
# circle around nozzle
ellipse(cx, bot + 70, 120, 70, w=5, val=200)
# smudges
sm = ink.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.35))
ink = Image.composite(ink, sm, ink.point(lambda v: 255 if v > 30 else 0))
ink = ink.filter(ImageFilter.GaussianBlur(1.2))
charcoal = Image.new('RGBA', (W, H), (20, 17, 16, 255))
paper = Image.composite(charcoal, paper, ink)
# torn edge alpha mask
mask = Image.new('L', (W, H), 0)
md = ImageDraw.Draw(mask)
poly = []
m = 44
def edge(a0, a1, fixed, horiz, sign):
    out = []; v = a0; off = 0.0
    step = 1 if a1 > a0 else -1
    while (v - a1) * step < 0:
        off = 0.7 * off + random.uniform(-9, 9)
        if random.random() < 0.06: off += random.uniform(-22, 22)
        out.append((v, fixed + off) if horiz else (fixed + off, v))
        v += step * random.randint(5, 13)
    return out
poly += edge(m, W - m, m, True, 1)
poly += edge(m, H - m, W - m, False, 1)
poly += edge(W - m, m, H - m, True, 1)
poly += edge(H - m, m, m, False, 1)
md.polygon(poly, fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(1.5))
paper.putalpha(mask)
paper.save('blueprint.png')
print('ok', paper.size)
