# Clip B: a glass hero drives the stunt car, music video on a Lyria song

**Models:**
- **Claude Opus 5.5** in Claude Code wrote and ran everything: Blender on a Colab L4 through the Colab MCP, and the song generation. Model ID from the session log. Effort was not recorded.
- **Google Lyria** made the music: `lyria-3-clip-preview` for the test clip and `lyria-3.5` for the songs, per `prompts.json`. We wrote the lyrics, and the prompt says so: "Текст оригинальный, наш".

**Date:** 17–19 October 2026  
**Result:** a 46-second 9:16 clip and a 27.8-second 4:5 cut, rendered at 1080x1920 and 64 samples. The final render ran 15 h 46 min in one process. Both clips measure −16.0 LUFS. A crash in the model's own code started the assembly too early once.

| | file |
|---|---|
| clip, 9:16 with lyrics | [`media/clip_tiktok.mp4`](media/clip_tiktok.mp4) |
| clip, 4:5 cut for X | [`media/clip_x.mp4`](media/clip_x.mp4) |
| song used, Lyria | [`media/song_B.mp3`](media/song_B.mp3) |
| the other Lyria songs | `song_A`, `song_C` … `song_G`, `clip_test` in [`media/`](media/) |
| frames picked for our article | `hook.png`, `hero_old_vs_v3.png`, `head_clay.png`, `draft_vs_final.png`, `endcard.png` |

Code, logs and the model's own report: [`code/clip_B/`](code/clip_B/). The report is `report.md`, the render log `progress.log`, the beat and lyric timing `timing.json`. For the songs, [`code/song/`](code/song/) has the exact Lyria prompts in `prompts.json`, the lyrics, the text Lyria returned with each song, and the model's analysis.

The scene is built on our earlier [loop stunt](../2026-10-16_loop-stunt-blender-colab/) run.

## Not made by the models

- **Hero head and body:** start from the MPFB (MakeHuman for Blender) base human, CC0. The model reshaped it.
- **Hero micro-motion:** the hero's small idle movements come from three clips of the CMU Graphics Lab motion capture database (13_02, 82_08, 77_01, as named in `final_v3.py` and the model's mocap file). The mocap data is not in this folder.
- **Fonts:** Inter and Liberation Sans, from the Colab system packages.
- **Lyrics:** ours.

## Prompt

Every message, word for word and in the original Russian, is in [prompt.md](prompt.md): first the Lyria tasks, then the clip task with three stops for our OK, then our notes. The prompts sent to Lyria are in `code/song/prompts.json`.

## Timeline

All times are UTC. Sources: the Claude Code session log, the model's `progress.log`, and `generation_EFG_log.json`, as marked.

| time | what happened | source |
|---|---|---|
| 17 Oct 16:41:21 | Lyria access check | session log |
| 17:31:46 | song task: test clip plus two songs | session log |
| 17:42:00 | `clip_test`, `song_A`, `song_B` done, "$0.20" | session log |
| 17:47:36 → 17:51:19 | `song_C`, `song_D` done, "$0.16" | session log |
| 18:08:11 | clip task, on `song_B` | session log |
| 18 Oct 06:26:22 | `song_E`, `song_F`, `song_G` generated, "spent": 0.24 | generation_EFG_log.json |
| 06:34:37 | we drop E, F and G and stay on song_B | session log |
| 12:29 and 14:28 | our notes on the draft clip | session log |
| 15:04:09 | our OK for the final at 64 spp | session log |
| 15:05:40 | final render starts | progress.log |
| 19 Oct 06:51:18 | final render ends: "961 frames in 945.5 min" | progress.log |
| 18 Oct 21:31 and 19 Oct 04:33 | our notes on the new hero head (v3) | session log |
| 19 Oct 18:44:44 | our OK: hero v3 in S3, S5, S8b, S9 | session log |
| 18:54:45 | v3 re-render starts, 289 frames | progress.log |
| 19:41:59 | assembly starts too early and fails, no files made | progress.log |
| 19:48:04 | v3 restarted after the fix | progress.log |
| 20:59:07 | "V3_DONE 289/289 frames" | progress.log |
| 21:06:57 | assembly done: clips and `report.md` | progress.log |

Render time from progress.log: 945.5 min for the main render, then 46.2 + 71.1 min for v3, then 7 min 49 s for assembly. That is about 17.8 hours of rendering in all. The model's own article note says 17.7 h, but the progress.log figures add up to 1,070.6 min. The only idle time during rendering was the 7 minutes after the crash, 19:40:57 → 19:48:04.

## What we measured

| | `clip_tiktok.mp4` | `clip_x.mp4` |
|---|---|---|
| frames | 1104 | 668 |
| size, fps | 1080x1920, 24 | 1080x1350, 24 |
| length | 46.000 s | 27.833 s |
| loudness | −16.0 LUFS | −16.0 LUFS |
| true peak | −3.9 dBTP | −5.0 dBTP |

The clips we checked are byte for byte the files on the Colab Drive (md5). These numbers match the model's `report.md` and `stage4_info.json`.

Lyria songs, as Lyria delivered them:

| file | model | length | loudness | true peak |
|---|---|---|---|---|
| clip_test | lyria-3-clip-preview | 30.8 s | −11.1 LUFS | +0.4 dBTP |
| song_A | lyria-3.5 | 65.3 s | −12.8 LUFS | +0.6 dBTP |
| song_B, used | lyria-3.5 | 65.2 s | −11.4 LUFS | +0.5 dBTP |
| song_C | lyria-3.5 | 66.0 s | −11.5 LUFS | +0.5 dBTP |
| song_D | lyria-3.5 | 68.1 s | −12.2 LUFS | +0.3 dBTP |
| song_E | lyria-3.5 | 62.7 s | −11.5 LUFS | +0.7 dBTP |
| song_F | lyria-3.5 | 65.1 s | −12.1 LUFS | +0.4 dBTP |
| song_G | lyria-3.5 | 66.7 s | −12.8 LUFS | +0.4 dBTP |

Measured with `ffprobe -count_frames` and `ffmpeg ebur128`.

**Cost, as reported, not checked against billing:**
- Lyria: $0.20 + $0.16 from the model's reports, $0.24 from the generation log, $0.60 in all.
- Colab: the model read the balance from Colab's panel as 49.49 compute units on 19 Oct 04:46 and 36.88 on 21 Oct. It said that difference cannot be split by stage. Its figure of 24.3 units for the main render is an estimate at 1.54 units per hour, not a reading.

## What went wrong

- **A crash in its own code** (from progress.log and report.md). The v3 script died after S3 while saving a review frame, because Blender's Python has no PIL. The assembly then started early, failed on missing frames and made no files. The model fixed it, made the assembly wait for `V3_DONE`, and restarted. That cost 7 minutes.
- **Smoke made S12 expensive.** Its first ~45 frames took 340–490 s each, against ~34 s for the rest of the shot (progress.log).
- **The old hero is still visible in some shots.** In S6–S12, except S8b and S9, the old hero shows small in the cabin, because those shots were rendered before we chose v3. We agreed to keep them (report.md).
- **The clip is shorter than first asked.** The task asked for the length of the song, about 63 s. We later cut it to 0–44 s plus a 2-second end card. S13 and S14 were never rendered (report.md).
- **Lyria:**
  - Every song came out above 0 dBTP. The model fixed this for the clip with a limiter.
  - Per the model's analysis, `song_A`'s chorus came at about 0:31 instead of the 0:24 we asked for.
  - The first try at `song_D` was blocked by Google's input filter (`prohibited_content`). The model changed "late night cruise" to "late night drive" and it went through. The change is recorded in `prompts.json`.

## Reproduce

1. Run the [loop stunt](../2026-10-16_loop-stunt-blender-colab/) first: the clip is built on its scene.
2. In Colab, put a Gemini API key in Colab Secrets as `GEMINI_API_KEY`. Send the song messages from [prompt.md](prompt.md), or call Lyria directly with `code/song/prompts.json`.
3. Send the clip messages in order. Our notes respond to this run's drafts, so a new run will need its own.
4. Or run the code: `code/clip_B/final_render.sh`, then `final_v3.sh`, which also runs the assembly. The scripts expect `/content/drive/MyDrive/renders/clip_B` and the stunt_v2 scene next to it. The hero v3 script needs the MPFB add-on and the CMU clips, which are not included.
