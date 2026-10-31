"""Episode 1 timing, shared by the shot script (Blender) and the draft sound (numpy).
Story time is the episode time from the prompt (0 = hook start, story shots run 2.5-27.0 s).
The animatic puts the approved intro v3 first (hook 0-2.5, ident 2.5-6.0, text card 6.0-9.5),
so a story moment plays at animatic time = story time + INTRO_SHIFT."""
FPS = 12                 # animatic shots render at 12 fps, doubled to 24 on encode
STORY0 = 2.5             # first story shot starts right after the hook
END = 27.0
INTRO_SHIFT = 7.0        # ident 3.5 s + text card 3.5 s
TOTAL = END + INTRO_SHIFT
NFRAMES = round((END - STORY0) * FPS)


def frame(t):
    """story seconds -> story frame number (1 = story 2.5 s)"""
    return int(round((t - STORY0) * FPS)) + 1


def t_of(f):
    return STORY0 + (f - 1) / FPS


SHOTS = [  # name, first frame, last frame (story frames, 12 fps)
    ('a1_scribble', 1, 12),     # 2.50 hero scribbles the blueprint, team watches
    ('a2_blueprint', 13, 24),   # 3.50 the blueprint big, nozzle cap at the bottom
    ('a3_skeptic', 25, 36),     # 4.50 skeptic lowers his head, "hm-m"
    ('b1_can', 37, 58),         # 5.50 three worms drag the tin can: wind-up, jerk, twice
    ('b2_caps', 59, 77),        # 7.33 caps rolled in
    ('b3_legs', 78, 95),        # 8.92 a match leg pushed up
    ('b4_weld', 96, 111),       # 10.42 welding with firefly sparks
    ('b5_foil', 112, 126),      # 11.75 foil wrapped on top
    ('c_cap', 127, 156),        # 13.00 the extra cap: cap, rocket, cap, tail flick
    ('d_count', 157, 180),      # 15.50 countdown lights, head on the button
    ('e_launch', 181, 216),     # 17.50 ignition, wobble, explosion, orange flash
    ('f_silence', 217, 252),    # 20.50 silence, dust, push-in on the cap, skeptic looks at hero
    ('g_helmet', 253, 294),     # 23.50 hero slides into his thimble, moo, fade out
]

EV = dict(  # story seconds
    hero_pitch=2.62, skeptic_hm=4.75, jerk1=6.08, jerk2=6.92, plapi=7.55, match_tock=9.83,
    weld=10.45, foil=11.8, uh=13.75, flick=14.92, blu=15.75, mo=16.33, shlip=16.92, button=17.08,
    ignite=17.6, liftoff=18.25, boom=19.3, silence=20.5, moo=25.9, fade=26.4,
)
