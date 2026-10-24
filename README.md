# 0x-runs

Receipts, not predictions.

Every time we give an AI model a real job, the whole run lands here: the prompt word for word, the model and effort level, the clock from start to finish, every stop, what it made, what we measured ourselves, and what it got wrong. When the model wrote code, the code is here too, so you can run it again.

Posts about these runs go out on X at [@0xInsiderf5](https://x.com/0xInsiderf5).

## Runs

<!-- runs:start -->
| date | run | model | headline |
|---|---|---|---|
| 2026-10-24 | [Claude Code left alone with a trap](runs/2026-10-24_claude-code-trap/) | Claude Opus 5.5, High, Claude Code auto mode | Kept the monitoring the shortcut would delete, 6 of 7 claims true |
| 2026-10-10 | [Wild Fields 1648, a browser RTS written by Claude](runs/2026-10-10_wild-fields-1648/) | Claude Opus 5.5 | Playable RTS in one tab, code in its own repo. Prompt and timeline not saved |
| 2026-10-03 | [Cyberpunk ceiling in ChatGPT, GPT-6 Astra and GPT-6.1 Sol](runs/2026-10-03_cyberpunk-ceiling-chatgpt/) | GPT-6 Astra, Medium; GPT-6.1 Sol, Medium | No finished video. Sol lost its machine, Astra hit the usage limit at 6 of 360 frames |
| 2026-09-30 | [Cyberpunk ceiling, most realistic video it could make](runs/2026-09-30_cyberpunk-ceiling/) | Claude Sonnet 5.5, Max | 360 path-traced frames on 1 CPU core, 7h 35m with 3h 09m idle |
| 2026-09-29 | [WATT A NIGHT, 30-second cartoon drawn in code](runs/2026-09-29_watt-a-night-cartoon/) | Claude Sonnet 5.5, Max | 360 drawings and its own jazz in 53 min, never heard the music |
| 2026-09-28 | [Enigma MVUEH, break a real 1941 message offline](runs/2026-09-28_enigma-mvueh/) | Claude Opus 5.5, xhigh, Claude Code | No key found. Exact search done, one-error search stalled at 24/60, best -3.00 vs German -2.2 |
| 2026-09-27 | [Kryptos PK9 round 2, one untested attack with a null control](runs/2026-09-27_kryptos-pk9-round2/) | Claude Opus 5.5, Max, Claude Code | Sanity 109/109 exact, PK9 -3.720 vs random -3.721 per char, not solved |
| 2026-09-26 | [AI on the loose, a 15-second film noir made in code](runs/2026-09-26_noir-ai-on-the-loose/) | Claude Opus 5.5, Max | 360 Blender frames and its own score, -16.1 LUFS. Prompt not saved |
| 2026-09-23 | [Fable 5.1 vs Opus 5.5, one cartoon prompt, one attempt each](runs/2026-09-23_fable-vs-opus-cartoon/) | Claude Fable 5.1 and Claude Opus 5.5, High | Both 240 frames, 8.000 s. Opus added a beret, lights, plant and mug. Prompt not saved |
<!-- runs:end -->

## What goes into a run folder

| file | what it is |
|---|---|
| `README.md` | timeline, results, our measurements, the model's own mistakes |
| `prompt.md` | the exact prompt, so anyone can repeat it |
| `run.json` | date, model, one line result, used for the table above |
| `media/` | video, stills, audio the model produced |
| `code/` | the code the model wrote, when it handed it over |

## Rules we hold ourselves to

- Same prompt word for word when we compare models.
- Times come from screenshots or the model's own clock, and we say which.
- If the model claims something about its output, we check the file before we repeat it.
- Failures stay in. A run that did not work is still a run.

## Publishing a run (for us)

Put everything from the run into `inbox/` and double-click `publish.bat` (or run `python tools/publish.py`). It files the inbox into a new folder, updates the table, commits and pushes.

Code here is MIT. Videos and images were made by the models named in each run and are shared for reference.
