# Fable 5.1 vs Opus 5.5: one cartoon prompt, one attempt each

**Models:** Claude Fable 5.1 and Claude Opus 5.5, both at High effort. The effort is printed on our post video ("HIGH EFFORT") and in its script ("both on high effort"). We did not record which app or interface the runs used.  
**Date:** 23 September 2026, from the post video's header  
**Result:** both delivered an 8-second MP4 that matches the format lines we can still read. Fable's has no extras. Opus added things the visible prompt does not ask for: a beret, string lights, a plant, a coffee mug and bigger text.

| | video |
|---|---|
| Fable 5.1 output | [`media/fable_5.1_output.mp4`](media/fable_5.1_output.mp4) |
| Opus 5.5 output | [`media/opus_5.5_output.mp4`](media/opus_5.5_output.mp4) |
| both side by side, labelled | [`media/side_by_side.mp4`](media/side_by_side.mp4) |
| our post video with voice-over | [`media/post_video_with_voiceover.mp4`](media/post_video_with_voiceover.mp4) |

## Prompt

Not saved. We found it neither in our files nor in our Claude Code logs.

Part of it scrolls past in our post video, between about 0:20 and 0:24. This is what can be read off those frames. It is a fragment, not the whole prompt:

```
Make an 8-second animated cartoon video and give me the final MP4.
One attempt, do not ask me questions, make every decision
yourself.

Format: 16:9, 1920x1080, 30 fps, exactly 8 seconds, H.264 MP4, no
sound.

Scene: a rooftop at golden hour. Soft sunset sky in peach, pink
and lilac, a calm city skyline in silhouette, warm light on
everything. A small round robot with one big glowing eye sits at a
```

The panel above it reads "PROMPT · IDENTICAL FOR BOTH MODELS · 1 ATTEMPT".

## Timeline

Not recorded. The only times we have are file times (Kyiv time, 23 September):

| file | saved |
|---|---|
| Fable 5.1 output | 22:44 |
| Opus 5.5 output | 22:48 |
| side-by-side video | 22:58 |
| post video | 00:21 on 24 September |

## What we measured

| what | Fable 5.1 | Opus 5.5 | how |
|---|---|---|---|
| frames | 240 | 240 | `ffprobe -count_frames` |
| length | 8.000 s | 8.000 s | `ffprobe` |
| size, frame rate | 1920x1080, 30 fps | 1920x1080, 30 fps | `ffprobe` |
| codec | H.264 High, yuv420p | H.264 High, yuv420p | `ffprobe` |
| sound | none | none | `ffprobe`: no audio stream |
| file size | 1.46 MB | 3.79 MB | file |
| additions not in the visible prompt | none seen | beret, string lights, potted plant, coffee mug, larger text on the page | frames of both outputs |

Both meet every format line of the prompt fragment above. We cannot check the rest of the prompt, because we do not have it.

## Not checked by us

- The post video's header lists each model's steps: Fable "pycairo, draw frames, ffmpeg, 14 commands, 12 files read"; Opus "build, render, ffprobe check". These come from our notes at the time, and we cannot re-check them without the chats.
- The post video quotes API prices ("Opus 60% less per token") and benchmark scores "as published by Anthropic". We did not re-check them for this record.
- In the post video the Fable clip is shown at 1.5x speed, as its label says. The output files here run at normal speed.

## What they got wrong

- **Fable 5.1:** nothing we could see against the visible part of the prompt.
- **Opus 5.5:** it added things the prompt did not ask for. Whether that counts against it depends on the part of the prompt we no longer have.
- **On our side:** we kept neither prompt nor timeline, and N = 1, as the video itself says.

## Notes on the media

- The voice-over in `post_video_with_voiceover.mp4` is a Microsoft edge-tts neural voice reading our own script. Neither model made it. There is no music under it: the audio drops below −50 dB in about 1-second gaps between the sentences.
- The two output files were saved as `robot_delve_rooftop.mp4` (Fable) and `delve_robot.mp4` (Opus) and renamed here. Which is which comes from the labelled side-by-side video: the Fable robot has no beret. We believe they are the MP4s as the models delivered them, since both have 240 frames and no audio as the prompt asks, but we cannot prove they were never re-encoded.

## Reproduce

Not possible word for word, because the full prompt was not saved. With the fragment above, give both models the same text in one message each at High effort, allow one attempt, and do not reply until each hands over its MP4.
