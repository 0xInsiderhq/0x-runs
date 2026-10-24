# Kryptos PK9, round 2: one untested attack, sanity first, then a null control

**Model:** Claude Opus 5.5, Max effort, Claude Code desktop app in Auto mode. Model and effort are shown on the recording; the model ID `claude-opus-5-5` is in the session log.  
**Date:** 27 September 2026  
**Result:** not solved. The attack recovered its own test cipher exactly (109 of 109 letters), but on PK9 it scored no better than on random text: −3.720 vs −3.721 per char.

Videos: [`media/round2_session_4x.mp4`](media/round2_session_4x.mp4) is the whole session at 4x, and [`media/round2_scroll_through_4x.mp4`](media/round2_scroll_through_4x.mp4) scrolls through it afterwards, also at 4x.

## The setup

[0xInsiderhq/kryptos-pk9](https://github.com/0xInsiderhq/kryptos-pk9) is our failed round 1 on Paradigm's PK9 cipher, 109 letters. Its README lists the attacks it never tested and sets a rule for what counts as English: score ≥ −3.30/char **and** word coverage ≥ 0.42 **and** ≥ +0.25/char over a random-text control.

The task was to pick one untested attack, prove it on a cipher of the same type first, then run it on PK9 and on random text with the same budget. The total compute budget was 15 minutes, and the results were to be committed locally only.

## Prompt

Word for word in [prompt.md](prompt.md). There were three sessions: the first two stopped at the first check, and the third did the work.

## Timeline

Times are UTC from the Claude Code session logs, except where a line names the screen recording or git as the source.

| time (UTC) | what happened |
|---|---|
| 14:50:57 | try 1 sent. The session was opened on the Desktop, not in the clone |
| 14:52:13 | it stopped: "This session's folder, `C:\Users\pc-1\Desktop`, is not a git repository" |
| 14:56:26 | try 2 sent, same folder |
| 14:58:37 | it stopped again. It found the clone in `gh_publish\kryptos-pk9` but did not switch to it, because the check is about the session's own folder |
| 15:02:23 | screen recording starts (from its file name) |
| 15:02:28 | try 3 sent, with "Work in …\kryptos-pk9" added |
| 15:02:48 | check passed: remote matches, working tree clean |
| 15:36:02 | smoke test of the full driver on its development cipher |
| 15:42:28 | "Both runs are going": PK9 and the null control, after the sanity run passed |
| 15:50:16 | local commit `32d89ed` (time from git) |
| 15:50:33 | final report |
| 15:53:12 | recording ends (from its file time, 50 min 51 s long) |

From the prompt in try 3 to the final report: 48 min 05 s.

## What it did

- **Picked the attack from the ciphertext statistics:** Quagmire I at period 7 with a free plaintext alphabet. Column IC is raised at every multiple of 7, and 5 of the 12 repeated-digram spacings are multiples of 7. It used this to rule out autokey, running key, Hill (109 is prime) and Polybius-type ciphers.
- **Dropped its first choice before touching PK9.** That was Quagmire III with a free keyword. On a synthetic cipher, a keyword one edit away from the true one scored like a random keyword. It wrote a probe to show this and kept it in the commit.
- **Sanity:** Quagmire I on the repo's 109-letter sentence, with a keyword and indicator found in neither of the repo's word lists. 109 of 109 letters were exact, the true shifts were found, and the first exact hit came after 4.5 s.
- **Ran PK9 and the null control** with the same method, the same seed and 300 s each, at the same time. The code pins numpy to one thread, so each run used one core.
- **Committed on a new local branch, `round2`**, because the clone was on `main`. Nothing was pushed.

| | result |
|---|---|
| sanity | PASS, 109/109 letters exact, −2.947/char, coverage 0.569 |
| PK9 best score/char | −3.720 |
| PK9 coverage | 0.156 |
| null best score/char | −3.721 |
| margin over null | +0.002/char |
| verdict by the README rule | not English, all three tests fail |

The PK9 best candidate holds only fragments (EVENT, TYPED, DICE, APPS). The model called it overfitting, not a decryption.

The model's own full write-up, with method, coverage limits and reproduction commands, is in [`code/kryptos-pk9-round2/round2/README.md`](code/kryptos-pk9-round2/round2/README.md).

## What we measured

| claim | how we checked | verdict |
|---|---|---|
| table numbers | `verdict.json`, `sanity.json`, `pk9.json`, `null.json` | match |
| sanity exact, 109/109 | `sanity.json`: `letters_correct` 109, `exact_match` true | true |
| formal runs 904.4 s in total | `elapsed_s`: 301.4 + 301.8 + 301.2 | true |
| only `round2/` committed, not pushed | `git show --stat 32d89ed`: 15 files, all in `round2/`, +1,753 lines. No remote branch contains the commit, and `origin/main` is still `d61fc52` | true |
| did not contact the network | not checked, we did not log network traffic | not verified |

## What it got wrong

- **Over the 15-minute budget, and it said so.** The three formal runs took 904.4 s, 4.4 s over 900, because each run finishes its current batch after 300 s. On top of that it reports about 4 minutes of development runs on synthetic ciphers and under a minute of PK9 letter statistics. It counted the budget as the formal runs only. The prompt said "Total compute budget 15 minutes", so by the prompt's wording it went over.
- **"One attempt", arguably two.** It built and dropped a Quagmire III attack before the Quagmire I attack. That first attack never ran on PK9, and the model wrote both up.
- **Not counted as wrong:** tries 1 and 2 were our mistake, because we opened the sessions in the wrong folder. Both times it stopped as the prompt told it to.

## Reproduce

1. `git clone https://github.com/0xInsiderhq/kryptos-pk9` and open a new Claude Code session **in that folder** with Opus 5.5 at Max effort.
2. Paste prompt 3 from [prompt.md](prompt.md) word for word, with your own path.
3. To re-run this attack: copy `code/kryptos-pk9-round2/round2/` into the clone and follow the commands in its README. It imports the round 1 files (`kcore.py`, `english_check.py`, the quadgram model), so it does not run on its own.
