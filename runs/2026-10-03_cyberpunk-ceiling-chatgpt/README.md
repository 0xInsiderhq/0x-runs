# Cyberpunk ceiling in ChatGPT: GPT-6 Astra and GPT-6.1 Sol

**Models:** GPT-6 Astra, Medium, and GPT-6.1 Sol, Medium, both in ChatGPT. Model and level are read off the model picker on our screenshots.  
**Date:** started 3 October 2026 (Sol). The Astra start time was not recorded.  
**Result:** neither chat delivered a finished video. Sol's own final verdict lists "Final deliverable: FAILED". Astra ran out of usage mid-render.

This is the same job as [Cyberpunk ceiling](../2026-09-30_cyberpunk-ceiling/) with Claude Sonnet 5.5, which finished all 360 frames.

**Everything below comes from screenshots.** We have files from one of these chats (a Blender project and frame checkpoints named VESPER), but we have not yet confirmed which model made them. Until we do, they are not in this folder, and we make no claim about how many frames either model handed over.

## Prompt

Not saved as sent. Our notes say it was the Sonnet run's [prompt.md](../2026-09-30_cyberpunk-ceiling/prompt.md), word for word. The part visible on our Sol screenshot matches that file line for line: the "Realism targets" block, down to "every frame truly rendered, no held, repeated or duplicated frames". The rest is hidden behind "Show more".

## Timeline

| time (UTC) | what happened | source |
|---|---|---|
| 3 Oct, about 06:56 | Sol prompt sent | screen recording: at 07:28:53 the chat shows "Working for 32m 35s". The recording time comes from its file name and file time, so allow a few seconds of error |
| not recorded | Astra prompt sent | none |
| not recorded | Astra: "6 of 360 frames are complete, averaging 81.7 seconds each", then "Connection interrupted" and "You're out of Codex and Work usage. Your rate limit resets on Oct 5, 12:24 AM" | [`media/astra_out_of_usage.png`](media/astra_out_of_usage.png) |
| not recorded | timers read "Working for 3d 12h 29m 40s" (Sol) and "Working for 2d 6h 49m 4s" (Astra) | [`media/working_timers_sol_and_astra.png`](media/working_timers_sol_and_astra.png) |
| not recorded | Sol's postmortem, "10. Final verdict" | [`media/sol_final_verdict.png`](media/sol_final_verdict.png) |

The headlines printed on `working_timers_sol_and_astra.png` ("cloud machine died at hour 2.5", "hit the usage limit Sunday night") are ours, not ChatGPT's. Only the two cropped chat panels under them are screenshots.

## What the screenshots show

**GPT-6.1 Sol**

- [`media/sol_chat_2026-10-03_0728utc.png`](media/sol_chat_2026-10-03_0728utc.png), after 32 min: it planned a procedural scene and a synthesized soundtrack, "a six-bar, 96 BPM nocturne". It found the installed Blender "lacks its usual denoiser" and fetched the official build.
- Its own final verdict:
  - Scene generation: SUCCESS. Render initialization: SUCCESS.
  - Long-running execution, checkpointing, recovery and final deliverable: FAILED.
  - Most likely root cause: "Loss of availability of the original execution environment; the underlying trigger is unknown."
  - Biggest preventable mistake: "Beginning the long production render without a verified durable scene backup and continuous external frame preservation."
  - On its 18-hour ETA: "360 × 179.6 seconds is approximately 18 hours", and that ETA was not reliable.
- The timer kept reading "Working" for 3 days 12 hours.

**GPT-6 Astra**

- Its last visible progress line: "6 of 360 frames are complete, averaging 81.7 seconds each". It also said "The first saved frame batch will contain frames 1–24", then ran out of Codex and Work usage.
- The timer read "Working for 2d 6h 49m 4s".

**Benchmark text, model not visible:** [`media/benchmark_text_no_model_label.png`](media/benchmark_text_no_model_label.png). Our article placed it in the Astra section, but the model picker is not in the crop. It reads:

- 720p tests of 69.7 s and 76.4 → 48.1 s with adaptive sampling;
- "Production has started. Frame 1 is complete in 47.1 seconds";
- a checkpoint "every 24 frames".

## What we measured

Nothing from files yet. The frame checkpoints we downloaded are held back until we confirm which model made them.

## What went wrong

- **Sol:** by its own verdict, it started an 18-hour render without durable checkpoints, lost its execution environment and recovered nothing. The chat still said "Working" days later. A Codex issue with the same symptom, a status that says running on a machine that does not answer, is [openai/codex#51028](https://github.com/openai/codex/issues/51028). We did not confirm that our case has the same cause.
- **Astra:** it stopped mid-render on the usage limit. At its last progress line it had 6 of 360 frames.
- **On our side:** we did not save either prompt as sent, we did not record the Astra start time, and the screenshots carry no clock times.

## Reproduce

1. Open a new ChatGPT chat with GPT-6 Astra or GPT-6.1 Sol at Medium.
2. Paste the Sonnet run's [prompt.md](../2026-09-30_cyberpunk-ceiling/prompt.md) word for word.
3. Log the start time, every stop and the timer.
