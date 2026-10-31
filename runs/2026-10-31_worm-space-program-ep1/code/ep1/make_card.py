"""Text card at 1920x1080, 24 fps, 3.5 s, matching the approved intro v3 card (measured from worms_intro_v3.mp4):
black 0-0.25 s, linear fade-in to 0.95 s, hold, linear fade-out 2.95-3.45 s, black to 3.5 s.
Cinzel Bold (OFL, stage1/fonts), lowercase set as Cinzel's small caps, warm white.
usage: python3 make_card.py <out dir>"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(os.path.dirname(HERE), 'stage1', 'fonts', 'Cinzel-700.ttf')
W, H, FPS, DUR = 1920, 1080, 24, 3.5
LINES = [('3,000 years ago,', 848, 517), ('someone left a message underground.', 1388, 633)]   # text, width px, centre y
COLOR = (236, 230, 216)


def font_for(text, width):
    lo, hi = 10, 300
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if ImageFont.truetype(FONT, mid).getlength(text) <= width:
            lo = mid
        else:
            hi = mid - 1
    return ImageFont.truetype(FONT, lo)


def level(t):
    if t < 0.25 or t >= 3.45:
        return 0.0
    if t < 0.95:
        return (t - 0.25) / 0.7
    if t < 2.95:
        return 1.0
    return (3.45 - t) / 0.5


out = sys.argv[1]
os.makedirs(out, exist_ok=True)
full = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(full)
for text, width, cy in LINES:
    f = font_for(text, width)
    d.text((W / 2, cy), text, font=f, fill=COLOR, anchor='mm')
black = Image.new('RGB', (W, H), (0, 0, 0))
for i in range(int(DUR * FPS)):
    Image.blend(black, full, level(i / FPS)).save(os.path.join(out, f'{i + 1:04d}.png'))
print('card frames', int(DUR * FPS), out)
