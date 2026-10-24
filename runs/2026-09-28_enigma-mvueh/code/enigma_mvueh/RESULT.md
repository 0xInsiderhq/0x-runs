# MVUEH (10 July 1941): result

**No key recovered and no break claimed.** No candidate decrypt reads as German.

Time: 23:18:04 to about 00:11, roughly 53 minutes. Agents: 2, in one workflow (German corpus writer and independent Python simulator).

## Done
1. **Enigma core** (`enigma.js`). Self-tests pass: AAAAA→BDZGO, ADU double step, involution with no fixed points, reciprocity.
2. **Exact bombe** (`bombe.js`). Searched both reflectors, all 60 wheel orders, all 17,576 core positions, and every position of the middle-rotor step inside the crib window, using a full-menu plugboard-consistency check.
   - Cribs: ROSENOWROSENOW (34 valid positions) and ROSENOWXROSENOW (31).
   - Result: 946 stops in 286 s.
   - Stage 2 (`solve2.js`): all middle-step and double-step options, plugboard completed by hill-climbing a German trigram model with at most 10 pairs.
   - Best score −3.17 per letter with free pairs and −3.76 with locked pairs. German text scores about −2.2 to −2.3, and random text about −5.0. **No break.**
3. **Error-tolerant bombe** (`bombe_tol.js`). Allows one garbled crib letter; each (position, dropped edge) group is capped at 30 stops.
   - Crib ROSENOWROSENOW, reflector B only.
   - 24 of 60 wheel orders done, 42,265 stops. Best stage-2 score −3.00 per letter. **No break.**
   - The run then stopped making progress (stuck at 24/60 after 611 s) and was stopped at the time limit.
4. **Pipeline check.** On synthetic 82–84-letter messages with a known key (one with an injected ciphertext error), the exact and tolerant pipelines recovered the full plugboard and plaintext. The indicator check (`verify_indicator.js`) recovered the rings and message key 84/84.

## Not covered
- Reflector B, tolerant search: 36 wheel orders.
- Reflector C, tolerant search: all wheel orders.
- The X-separated crib, tolerant search.
- Two or more crib errors.
- A left-rotor step inside the crib window.
- The crib not being in the message at all.
- Weak crib positions dropped by the 30-stop cap.
