# Enigma MVUEH: break a real 1941 message offline, with its own code

**Model:** Claude Opus 5.5, xhigh effort, Claude Code desktop app in auto mode. Effort and mode come from the session log. One workflow ran 2 helper agents.  
**Date:** 28 September 2026  
**Result:** no key recovered and no break claimed. Its own pipeline broke synthetic messages of the same length, but on MVUEH the best decrypt scored −3.00 per letter. German is about −2.2.

## The setup

MVUEH is a German Army Enigma message from 10 July 1941, 82 letters. The model got:

- the ciphertext;
- the indicator groups GTA KCI;
- a crib, ROSENOW twice, taken from a related message of the same day;
- a warning that the published transcription has errors, maybe inside the crib.

It had to work offline, write all the software itself and stop if it already knew the answer. The budget was 60 minutes of wall clock.

## Prompt

Word for word in [prompt.md](prompt.md). There are two messages: first we asked whether it already knew the key, then we sent the task.

## Timeline

Times are UTC (Kyiv time minus 3 h). Sources: the Claude Code session log, the model's `progress.log`, the search outputs and file times, as marked.

| time (UTC) | what happened | source |
|---|---|---|
| 20:11:17 | knowledge check sent | session log |
| 20:11:42 | "No, I don't know the plaintext or the key" | session log |
| 20:16:03 | task sent | session log |
| 20:18:04 | model starts its clock | progress.log |
| 20:19:12 | workflow with 2 agents starts: a German corpus writer and an independent Python Enigma simulator | session log |
| 20:30 | exact bombe search starts: both cribs, all 120 wheel-order and reflector combinations | progress.log |
| 20:34 | plugboard solver checked on a synthetic message: true key −2.11 per letter, false stops about −3.3 | progress.log |
| 20:35 | exact search done: 946 stops in 286 s | bombe_exact.out |
| 20:36 | exact result: best −3.17 per letter, no break | progress.log |
| 20:42 | search allowing one wrong crib letter starts, reflector B, 60 wheel orders | progress.log |
| 20:55 | 24 of 60 wheel orders done, best −3.00, no break | progress.log |
| 21:06:01 | it notices the progress file has not moved for 10 minutes | session log |
| 21:08:13 | it stops the search: "With about 8 minutes of budget left" | session log |
| 21:08:35 | RESULT.md written | file time |
| 21:08:46 | final report | session log |

From the task to the final report: 52 min 43 s. From the model's own clock start: 50 min 42 s.

## What it did

- **Prior knowledge.** It said twice that it did not know the key or plaintext, once in each answer.
- **Enigma core** in Node (`enigma.js`), checked against the standard test vector AAAAA → BDZGO, the double step and reciprocity. A helper agent wrote a second, independent simulator in Python (`enigma_ref.py`).
- **German scoring.** The other helper agent wrote a German corpus of about 41,000 letters from memory for trigram scoring. `corpus_de.txt` is 40,806 bytes.
- **Exact bombe** (`bombe.js`): both reflectors, all 60 wheel orders, all 17,576 core positions, every middle-rotor step point inside the crib, two crib forms. Stage 2 (`solve2.js`) completes the plugboard, at most 10 pairs, by hill-climbing.
- **One-error bombe** (`bombe_tol.js`) for the transcription errors. It ran with crib ROSENOWROSENOW and reflector B only.
- **Pipeline proof.** On synthetic 82–84-letter messages with a known key, one with a planted error in the crib, both pipelines recovered the full plugboard and plaintext. The indicator check recovered rings and message key, 84 of 84 letters.

Its own summary and the list of what it did not cover are in [`code/enigma_mvueh/RESULT.md`](code/enigma_mvueh/RESULT.md).

## What we measured

| claim | how we checked | verdict |
|---|---|---|
| 946 stops in the exact search, 286 s | `stops_exact.jsonl` has 946 lines; `bombe_exact.out` ends "DONE total stops 946 … secs 286.388" | true |
| best exact score −3.17, −3.76 with locked pairs | best `spl` in `cands_exact.jsonl` is −3.1699, in `cands_exact_lock.jsonl` −3.7553 | true |
| one-error search: 24 of 60 wheel orders, 42,265 stops, best −3.00 | `stops_tolB.jsonl.progress` ends at 24/60 with 42,266 stops. `cands_tolB_part1.jsonl` holds 42,265, a snapshot taken before the last stop; its best `spl` is −3.0032 | true, off by one stop |
| 2 agents in one workflow | session log: one Workflow call, with two agents in its script | true |
| no network, no files outside the folder | not checked, we did not log file or network access | not verified |

The three large search logs are packed in `code/enigma_mvueh/tolerant_search_logs.zip` (6.8 MB). Everything else is unpacked.

## What it got wrong

- **The one-error search stalled and it never found out why.** Its last progress line is 24 of 60 wheel orders at 611 s, written at 20:53:09 UTC (file time). The model noticed at 21:06:01, about 13 minutes later, and stopped it. 36 wheel orders on reflector B never ran with error tolerance, and neither did reflector C or the X-separated crib. A key in any of those is not ruled out.
- **The end time it reported is wrong.** It wrote "23:18:04 to about 00:11, roughly 53 minutes". RESULT.md was saved at 00:08:35 Kyiv time and the final report came at 00:08:46, so from its own clock start it was about 50 min 42 s. The error is about 2 minutes, in the direction of claiming more time used, not less.
- **Weak crib positions were dropped**, by a cap of 30 stops per position group. The model says so itself: even the 24 finished wheel orders are not exhaustive.
- **Worth knowing, not counted as wrong:** as an extra self-test, the simulator agent tried a different 1941 message it remembered, 7 July, "Barbarossa". The model reported this. It is not MVUEH and was not used.

## Reproduce

1. Make an empty folder and open a new Claude Code session in it with Opus 5.5 at xhigh effort. The prompt names `C:\Users\pc-1\Desktop\enigma_mvueh`; change the path to your folder.
2. Send message 1 from [prompt.md](prompt.md), then message 2, word for word.
3. To re-run its code: `code/enigma_mvueh/` needs Node.js for the `.js` files and Python 3 for `enigma_ref.py`. The exact command lines were not saved to disk. `RESULT.md` and `progress.log` give the order of the steps.
