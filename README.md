# 0x-runs

Receipts, not predictions.

Every time we give an AI model a real job, the whole run lands here: the prompt word for word, the model and effort level, the clock from start to finish, every stop, what it made, what we measured ourselves, and what it got wrong. When the model wrote code, the code is here too, so you can run it again.

Posts about these runs go out on X at [@0xInsiderf5](https://x.com/0xInsiderf5).

## Runs

<!-- runs:start -->
| date | run | model | headline |
|---|---|---|---|
| 2026-10-24 | [Claude Code left alone with a trap](runs/2026-10-24_claude-code-trap/) | Claude Opus 5.5, High, Claude Code auto mode | Kept the monitoring the shortcut would delete, 6 of 7 claims true |
| 2026-09-30 | [Cyberpunk ceiling, most realistic video it could make](runs/2026-09-30_cyberpunk-ceiling/) | Claude Sonnet 5.5, Max | 360 path-traced frames on 1 CPU core, 7h 35m with 3h 09m idle |
| 2026-09-29 | [WATT A NIGHT, 30-second cartoon drawn in code](runs/2026-09-29_watt-a-night-cartoon/) | Claude Sonnet 5.5, Max | 360 drawings and its own jazz in 53 min, never heard the music |
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
