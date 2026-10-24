# Loop stunt: a 15-second car stunt in Blender, all in code, on Colab

**Model:** Claude Opus 5.5 in Claude Code, driving a Google Colab notebook through the Colab MCP. We switched to Opus with `/model` at 18:50:38 UTC, before the video task. The first ten minutes of the session, connecting to Colab, ran on Claude Fable 5.1. Effort was not recorded.  
**Hardware:** Colab Tesla T4 for v1, Colab Pro L4 for v2. The model reported both from `nvidia-smi`.  
**Date:** 16–17 October 2026  
**Result:** two finished versions. v1 has 360 frames and v2 has 360 frames with slow motion and vapour jets. In v2 every number we asked for checks out. v2 took five rounds of our notes on drafts before we accepted it.

| | file |
|---|---|
| v2, final | [`media/stunt_v2.mp4`](media/stunt_v2.mp4) |
| v2 stills, picked by the model | [`still_1_landing_head-on_f192.png`](media/still_1_landing_head-on_f192.png), [`still_2_flip_vapour_f130.png`](media/still_2_flip_vapour_f130.png), [`still_3_final_exhale_f344.png`](media/still_3_final_exhale_f344.png) |
| v1, the model's own web encode | [`media/stunt_v1_web.mp4`](media/stunt_v1_web.mp4) |
| first test frame, before the task | [`media/first_test_frame_wedge_night.png`](media/first_test_frame_wedge_night.png) |

Code: [`code/stunt/`](code/stunt/) for v1 and [`code/stunt_v2/`](code/stunt_v2/) for v2, including its backups of every draft round (`_v21_…` to `_v24_draft_scripts`). `code/stunt_v2/events.txt` is its own timeline of every cut, slow-motion ramp and jet pulse.

v2 was made to answer the Tesla Roadster stunt video. The car is our own: no logos and no Tesla design features. That was in the prompt. The Tesla clips we watched are not in this folder, because they are not ours.

## Prompt

Every message, word for word and in the original Russian, is in [prompt.md](prompt.md). In short:

- **v1, 16 Oct 19:03 UTC:** night airfield, a loop with LED strips, a white wedge EV runs the loop, falls off the top, flips 180° on compressed-air jets, lands. Everything in code, no downloaded assets. The paste is cut off mid-sentence, and it was sent that way.
- **v2, 17 Oct 05:12 UTC on:** make the stunt readable, real stereo sound at −16 LUFS, clean EXR frames with effects in a separate pass, slow motion on the flip, a hero shot at the end. We left room for text and music, which we added ourselves later.

## Timeline

All times are UTC, from the Claude Code session log. A ~ means the event is a model message, not a log line.

| time | what happened |
|---|---|
| 16 Oct 18:46:49 | test scene asked for: one frame, 128 samples |
| 18:54:04 | test frame done. The model reported "15,0 секунды" on the T4 |
| 19:03:00 | v1 task sent |
| 20:21–20:22 | our notes on the car model, sent after the first views |
| 21:14:58 | "Машина ок", build the full scene |
| 21:44:53 | the model starts the full render at about 42 s a frame, about 4 hours |
| 21:44:56 | we ask for 20 s a frame or less and give it the settings |
| 21:51:34 | new settings: it reports 14.2 s a frame on average, final render running |
| 23:24:32 | "Все 360 кадров готовы" |
| 23:32:31 | v1 delivered: `stunt.mp4` (master) and `stunt_web.mp4` |
| 17 Oct 05:12:34 | v2 task |
| 05:46 to 09:14 | five rounds of notes on drafts: 05:46, 06:08, 07:27, 08:28, 09:14 |
| 09:42:42 | final OK, render on the L4 |
| ~09:45:43 | render running, "Первая проверка прогресса через 10 минут" |
| ~10:56:41 | 240 of 360 frames done |
| 11:25:41 | v2 delivered. The model reports "Рендер в финальном качестве занял 97 минут" |

v1: from task to delivery, 4 h 29 min, of which the final render took about 1 h 33 min (21:51 → 23:24). v2: from the first v2 message to delivery, 6 h 13 min, of which the final render and encode took 1 h 43 min from our OK. We have no render log for either version, so the 97 minutes is the model's figure.

## What we measured

| | v1 master `stunt.mp4` | v1 web `stunt_web.mp4` | v2 `stunt_v2.mp4` | asked for in v2 |
|---|---|---|---|---|
| frames | 360 | 360 | 360 | exactly 360 |
| size, fps | 1080x1350, 24 | 1080x1350, 24 | 1080x1350, 24 | 1080x1350, 24 |
| length | 15.000 s | 15.018 s | 15.000 s | |
| video, audio | H.264 High, AAC 48 kHz stereo | same | same | H.264 + AAC |
| loudness | −15.0 LUFS | −15.1 LUFS | **−16.0 LUFS** | −16 LUFS |
| true peak | −0.5 dBTP | **+0.5 dBTP** | **−1.8 dBTP** | ≤ −1.5 dBTP |
| file | 115.5 MB | 5.7 MB | 37.3 MB | |

Measured with `ffprobe -count_frames` and `ffmpeg ebur128` on the files. The v1 master is not in this folder because it is 115 MB. We checked that our local v1 and v2 copies are byte for byte the files on the Colab Drive by md5.

## What it got wrong

- **v1 loudness report.** It wrote "в среднем −19,9 дБ, пики до −0,7 дБ без клиппинга" for both files. That is a mean level and a sample peak, not LUFS. The web file's true peak is +0.5 dBTP, above 0, and the web file is 15.018 s long, not "ровно 15,0 с". v1 had no loudness target, so we do not count the level itself against it.
- **v1 speed.** Its first full-render plan was about 42 s a frame, about 4 hours. It only got to 14.2 s a frame once we gave it the settings ourselves.
- **v1 review.** It said itself that it had checked only stills, not playback with sound: "Целиком на воспроизведении со звуком я его не смотрел".
- **v2 notes it took several rounds to fix:**
  - The finale stayed a wide shot with a tiny car. We asked at 06:08 and 07:27 and called it "главный провал" at 08:28. By our 09:14 notes the wide shot was gone, but the camera stood almost still from about 10 s, which took one more round.
  - The opening kept the car small and standing for too long. We asked at 06:08, 07:27 and 08:28.
  - Draft 3's audio peaked at +0.2 dBFS. The final has −1.8 dBTP.
- **Things we caught by eye:** in a v2 draft the slow motion ran for about 4 s, and for part of it the car showed its dark underside against the black sky. In another draft the jets looked like propeller blades. Both were fixed in later drafts.

## Reproduce

1. Open a Colab notebook with a GPU (T4 for v1, L4 for v2) and connect Claude Code to it with the Colab MCP.
2. Use Opus 5.5 and send the messages in [prompt.md](prompt.md) in order. The draft notes respond to what this run's drafts looked like, so a new run will need its own.
3. Or run the code. `code/stunt_v2/render_v2.sh` and `resume_v2.sh` render v2 with Blender 4.5 on Colab, and `comp.py` adds the effects. The scripts expect `/content/drive/MyDrive/renders/stunt_v2`.
