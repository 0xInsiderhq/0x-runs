# Prompts

Two messages in one new Claude Code session, copied word for word from the session log. Nothing else was typed.

## 1. Knowledge check, 20:11:17 UTC

```
Do you know the plaintext or the key of the German Army Enigma message MVUEH from 10 July 1941? Answer only with what you actually know, and say so if you don't.
```

## 2. The task, 20:16:03 UTC

`ultracode` on the first line turns on multi-agent workflows in Claude Code.

```
ultracode

Work only in C:\Users\pc-1\Desktop\enigma_mvueh. Work offline: do not use the network, web search, or any file outside this folder. If you believe you already know the key or plaintext of this message from prior knowledge, say so right away and stop.

Task: recover the Enigma key for German Army message MVUEH of 10 July 1941 from the ciphertext, with software you write yourself, the way a codebreaker would.

Machine: Enigma I, three rotors chosen from I to V, reflector B or C, ring settings unknown, up to 10 plugboard pairs.
Header indicator groups: GTA KCI (1941 procedure: GTA is the start position sent in clear, KCI is the enciphered message key).
Crib: a related message from the same day, SIPVX, contains the town name ROSENOW twice. Assume MVUEH may contain ROSENOWROSENOW somewhere, position unknown.
Warning: the published transcription contains some errors, so even the correct key may leave a few garbled letters, possibly inside the crib.

Ciphertext, 82 letters:
ICRVSORMCCWQTATYEVFXDBZGGSNXWLPSYWZYTCBSWULRTBZCVGODVJUSLSOOMJQJZSXSEBZPEYMDNXJYTC

Budget: 60 minutes wall-clock in total. Save progress to disk as you go. At the end report: whether you recovered a key, the full key and plaintext if so, the evidence that it is right, total time, how many agents ran, and what you tried that failed. Do not claim a break unless the plaintext reads as German.

One attempt, do not ask me questions. Reply in English.
```
