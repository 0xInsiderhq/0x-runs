# Worm Space Program, episode 1 "The Extra Part": a 31-second 3D short (X cut; the full episode is 34 s) in Blender on Colab

**Model:** Claude Opus 5.5 in Claude Code (desktop app), driving a Google Colab notebook through the Colab MCP and Google Drive through Chrome.  
**Hardware:** Colab L4 (`nvidia-smi`: NVIDIA L4), Blender 5.2.3, Cycles + OpenImageDenoise.  
**Date:** 31 October 2026 (stage 1 of the series was done on 28 October in a separate cloud session)  
**Result:** episode 1 finished in three versions: 1920x1080, 24 fps, 34.0 s, 816 frames, −16.0 LUFS, −2.22 dBTP. The final v3 also has a 31-second cut for X: 744 frames, −16.11 LUFS, −2.26 dBTP. This repo has only that X cut of v3. The full versions and the v1 and v2 videos are not published here.

| | file |
|---|---|
| episode 1, v3, X cut (31.0 s) | [`worm_space_program_ep1_v3_x.mp4`](media/worm_space_program_ep1_v3_x.mp4) |
| three best frames, picked by the model | [`best1_blueprint_f0035.png`](media/best1_blueprint_f0035.png), [`best2_hero_and_rocket_f0275.png`](media/best2_hero_and_rocket_f0275.png), [`best3_explosion_f0409.png`](media/best3_explosion_f0409.png) |
| run log, one line per step | [`runlog.jsonl`](files/runlog.jsonl) |
| render time per frame | [`render_times.csv`](files/render_times.csv) (story), [`render_times_intro.csv`](files/render_times_intro.csv) (intro), [`render_times_animatic.csv`](files/render_times_animatic.csv) |
| code | [`code/`](code/): `stage1/` as handed over, `ep1/` written in this session |

## Prompt

Every message, word for word and in the original Russian, is in [prompt.md](prompt.md): the series prompt v3.3, the stage 2 addendum and the five messages of this session. In short: a series about earthworms who build a rocket from junk. Episode 1: they build it, one bottle cap is left over, the rocket explodes, the hero hides in his thimble helmet. Stage 1 (characters, workshop, rocket, 4 stills, worm voices, the "0x Production" intro) was approved before this session and reused as is.

## Timeline

All times are UTC, from `runlog.jsonl` (written in +02:00). Some log lines were written in batches, so a line's time is when it was written, not always when the step happened.

| time | what happened |
|---|---|
| 28 Oct 06:29 | stage 1 starts in a cloud session |
| 28 Oct 15:14 | stage 1 STOP passed: stills approved |
| 31 Oct 10:54 | home session starts, stage 1 unpacked, Colab connected |
| 11:19:28 | animatic render, 294 frames at 960x540, 12 fps (Colab clock) |
| 11:32 | STOP: animatic shown, two sound drafts (A: silence after the explosion, B: music never stops) |
| 11:43 | our reply: sound B and three fixes (the extra-cap gag, darkness in the last two shots, stronger jerks) |
| 11:50 | STOP again: animatic v2 |
| 15:28 | "Ок, дальше", Colab units 12.51. The Colab runtime had been reset in between: Blender reinstalled, Drive remounted |
| 15:35 | STOP: two 1920x1080 test frames and the estimate (about 52 min of GPU) |
| 15:37 | our reply: go to 1080p, fix the fireball and the flash |
| 15:41 | frame 409 after the fix shown |
| 15:50:52 | "Ок, запускай": full render starts (Colab clock) |
| 16:44:38 | render done: 588 story frames + 72 intro frames (Colab clock) |
| 16:53 | final assembled, checked, copied to the PC |

From our first message to the final file: about 6 h, of which the session waited for us for about 3 h 38 min between 11:50 and 15:28. GPU time in the final render: 2872.2 s for the story and 238.9 s for the intro, summed from the CSVs.

## What we measured

| | v1 full version (not in this repo) | asked for |
|---|---|---|
| size, fps | 1920x1080, 24 | 1920x1080, 24 |
| frames, length | 816, 34.000 s | episode 20–28 s plus intro, about 30–33 s in total |
| video, audio | H.264, AAC 48 kHz | |
| loudness | −16.0 LUFS (ffmpeg ebur128), −16.09 (loudnorm measure) | −16 LUFS |
| true peak | −2.22 dBTP | ≤ −1.5 dBTP |
| silences over 0.3 s under −45 dB | none | music never stops (sound B, our choice) |
| frozen stretches over 0.6 s | 3: the text card hold (6.9–9.1 s), the start of the extra-cap shot (20.0–20.6 s), the last pause before the fade (32.7–33.5 s) | |
| explosion sync | flash on screen at 26.333 s, boom placed in the sound at 26.300 s | |

Story render: 588 frames, mean 4.88 s, min 3.45 s, max 6.43 s per frame on the L4. The model's estimate before the render was 52.2 min for story + intro; the CSVs add up to 51.9 min of render time. The background job started at 15:50:52 and was seen finished at 16:44:38, so it ran under 54 min.

Colab units: 12.51 before the test frames and the final render, 9.68 after, so 2.83 used. The model estimated 1.9–2.1 before the render, using a units-per-hour rate from earlier L4 renders; the estimate left out the idle time of the runtime between stops.

## What it got wrong

The model's own list, from the log:

1. It first pulled a preview image out of Colab as base64 in a cell, which put 44 thousand characters into its context. It switched to Drive thumbnails in Chrome.
2. Animatic previews: worms hidden behind the can, the hero on the rim of the can out of view, the control pebble blown out, the explosion flash almost white.
3. Animatic v1: the extra-cap gag did not read, the hero was too small. The fireball read as a white disc, the rocket at launch as a black silhouette. After the first fix the explosion went out of the top of the frame. A faded fireball rendered as a black ball on 3 frames.
4. The first animatic mix had a true peak of −1.4 dBTP, over the −1.5 limit.
5. After the Colab reset the intro would not render: the DejaVu Serif font was missing. Fixed by installing `fonts-dejavu-core`.
6. At 1080p the fireball read as a flat faceted disc and the flash washed the whole frame in one peach colour. The model flagged the disc itself; we added the flash note. The first fix blew the core out to white, the second kept it orange.
7. Final master: one-pass loudnorm gave −16.9 LUFS, two-pass −16.3, then the make-up gain pushed the true peak to −1.47 dBTP after AAC encoding. A limiter before the make-up gain fixed it: −16.0 LUFS, −2.22 dBTP.
8. Part of the run log was written in batches, so some timestamps are later than the step itself.

## v2: real sky, firecracker blast, a short cut for X

After the first delivery we asked for four things (message 8 in [prompt.md](prompt.md)): a realistic sky, a firecracker-scale blast, a short version for X, and test frames before the re-render.

| | file |
|---|---|
| v2 frames | [`v2_logo_f20.png`](media/v2_logo_f20.png), [`v2_blast_peak_f0406.png`](media/v2_blast_peak_f0406.png) |
| render times | [`render_times_v2.csv`](files/render_times_v2.csv), [`render_times_intro_v2.csv`](files/render_times_intro_v2.csv) |

- **Mars:** the USGS Astrogeology "Mars Viking Global Color Mosaic 925m", listed as public domain with no use constraints. A shader adds the terminator and a thin limb. In the approved logo, the visible "Mars" turned out to be a red halo sphere hiding the real one. The model put the real Mars in its place at the same size.
- **Stars:** procedural, about 26,000 points plus a Milky Way band. The model did not use NASA SVS Deep Star Maps: the page states no licence and includes ESA Gaia data.
- **Blast:** a Mantaflow gas sim, baked in about 67 s. The fluid modifier left its grid empty at render time in background mode, so the baked VDBs are loaded as a Volume object.
- **What was re-rendered:** only the frames that changed: hook 30, logo 42, the 2 s X logo 24, and 28 blast frames. The GPU time was 512.3 s in the CSVs.
- **X cut:** the logo dissolves into the card and the card into the story, with no black. The story starts at 6.5 s. The intro score was rebuilt for that timing rather than cut.

| | v2 full | v2 X cut |
|---|---|---|
| loudness | −16.09 LUFS | −16.11 LUFS |
| true peak | −2.22 dBTP | −2.26 dBTP |
| silences over 0.3 s under −45 dB | none | none |
| explosion sync | flash 26.333 s, boom 26.300 s | flash 23.333 s, boom 23.300 s |

Colab units: 9.68 before v2 and 8.02 after, so v2 (test frames and render) used 1.66. The model's estimate was about 0.8 for the tests plus 0.8–1.0 for the render. For the whole day: 12.51 → 8.02, so 4.49 units.

What it got wrong in v2, from its log:
- the star generator crashed;
- the smoke did not render at first, then was invisible, then looked like a black ball;
- the logo's Mars was first a flat dark disc;
- the flame was first a white ball;
- the Drive mount failed on a fresh runtime until we approved access by hand;
- Drive refused symlinks during assembly;
- an ffmpeg timebase error broke the X cut on the first try.

## v3: the fireball back, soft smoke (final)

We found the v2 blast weaker than v1 (message 12): the flame looked like a white lump of cotton, the smoke like a small grey ball. We also asked for the faceted launch dust to go. Only the launch and blast shot was re-rendered: 72 frames (361–432), 662.3 s on the L4.

| | file |
|---|---|
| v3, X cut (31.0 s, 744 frames), **final** | [`worm_space_program_ep1_v3_x.mp4`](media/worm_space_program_ep1_v3_x.mp4) |
| blast peak (409), +0.5 s (421), launch dust (385) | [`v3_frames_409_421_385.jpg`](media/v3_frames_409_421_385.jpg) |
| render times | [`render_times_v3.csv`](files/render_times_v3.csv) |

- **Fireball:** v1's fireball, the one we approved on frame 409, restored with the same shader and timing. v2's sparks and flying junk stay.
- **Smoke:** a procedural volume instead of the Mantaflow sim. The density fades to zero well inside the mesh and the edge is warped by noise. It swells, drifts up and thins out over about 1.3 s. The first two tries were too thin, then a round fog ball.
- **Launch dust:** soft volume puffs instead of the faceted alpha spheres.
- **Measured:** full −16.09 LUFS and −2.22 dBTP; X cut −16.11 LUFS and −2.26 dBTP; no silences; flash and boom within a frame in both. Checked again on the PC with ffmpeg: 816 and 744 frames, 34.000 and 31.000 s.

Colab units: 8.02 before v3 and 7.94 after, so v3 (test frames, the 72-frame render and assembly) used 0.08. The runtime was up for about 20 minutes. For the whole day: 12.51 → 7.94, so 4.57 units.

## Reproduce

1. Open a new chat with the same model and effort, in a folder with the Colab MCP connected.
2. Paste [prompt.md](prompt.md) word for word: the stage 1 files come from `worm_space_program_code.zip` (`stage1/`).
3. Press continue at every stop and log the time.
