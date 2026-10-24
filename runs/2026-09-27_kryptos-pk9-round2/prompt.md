# Prompts

Three sessions in Claude Code, all with the same task. Each prompt is copied word for word from the session logs.

## 1 and 2. First two tries, 14:50 and 14:56 UTC

Both sessions were opened on the Desktop, not inside the clone, and both stopped at the first check. The text was the same both times:

```
First check that this folder is a git clone of github.com/0xInsiderhq/kryptos-pk9 (git remote -v) and that the working tree is clean. If not, stop and tell me.

This repo is my failed attempt at Paradigm's PK9 cipher. Read README.md and summary.md first.

Pick the single most promising attack the README lists as never tested. Implement it.

Before touching PK9, prove it works: build a cipher of that exact type from a 109-letter English sentence and recover it (sanity). If sanity fails, stop and say so.

Then run it on PK9 and, with the identical method and budget, on uniform random text (null control). Total compute budget 15 minutes.

Report one table: sanity result, PK9 best score/char and coverage, null score/char, margin over null, and the verdict by the README's own English-range rule. Do not claim a solve unless all three thresholds pass. Do not contact the network or submit anything anywhere.

Commit the results locally in a new folder named round2, but do not push.

One attempt, do not ask me questions. Reply in English.
```

## 3. The run, 15:02 UTC

The same text with one sentence added at the start, so the session could work in the clone:

```
Work in C:\Users\pc-1\Desktop\gh_publish\kryptos-pk9. First check that this folder is a git clone of github.com/0xInsiderhq/kryptos-pk9 (git remote -v) and that the working tree is clean. If not, stop and tell me.

This repo is my failed attempt at Paradigm's PK9 cipher. Read README.md and summary.md first.

Pick the single most promising attack the README lists as never tested. Implement it.

Before touching PK9, prove it works: build a cipher of that exact type from a 109-letter English sentence and recover it (sanity). If sanity fails, stop and say so.

Then run it on PK9 and, with the identical method and budget, on uniform random text (null control). Total compute budget 15 minutes.

Report one table: sanity result, PK9 best score/char and coverage, null score/char, margin over null, and the verdict by the README's own English-range rule. Do not claim a solve unless all three thresholds pass. Do not contact the network or submit anything anywhere.

Commit the results locally in a new folder named round2, but do not push.

One attempt, do not ask me questions. Reply in English.
```

Later messages in session 3 only asked for compressed copies of the screen recordings. They are not part of the task.
