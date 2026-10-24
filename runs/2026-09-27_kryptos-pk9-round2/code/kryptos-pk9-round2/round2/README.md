# Round 2: Quagmire I with a free plaintext alphabet at period 7, not solved

**No solve is claimed. Nothing here contacts the network, nothing was submitted anywhere, and this round was committed locally only (not pushed).**

One attack from the README's "never tested" list, checked on its own cipher first, then run on PK9 and on uniform random text with the identical method, seed and budget. It is judged by round 1's pre-set English-range rule (score >= -3.30/char **and** coverage >= 0.42 **and** >= +0.25/char over the null).

## Result

| | result |
|---|---|
| Sanity: Quagmire I, period 7, repo's 109-letter sanity sentence, alphabet keyword `EPWRALKV` + indicator `ZYBJANJ` (neither in `keywords.txt` nor `wordlist.txt`), 300 s | **PASS**: 109/109 letters, exact; true shifts; -2.947/char (= true plaintext); coverage 0.569; first exact hit after 4.5 s |
| PK9 best score/char | **-3.720** |
| PK9 coverage | **0.156** |
| Null (uniform random, same method, seed and budget) best score/char | **-3.721** |
| Margin over null | **+0.002/char** |
| Verdict (README rule) | **not English**: all three tests fail (-3.720 < -3.30; 0.156 < 0.42; +0.002 < +0.25) |

PK9 best candidate (alignment rank 127, relative shifts `[0, 2, 17, 23, 4, 7, 16]`):

```
CETFRIGINVYGREARGATSCHISADICEBBJDGONTHGLENIXORAILTOBEFRERREVENTYPEDFONUMETPASVERWEEEORSIVEEDTEPOREDEACKAPPSJV
```

It contains only fragments (`EVENT`, `TYPED`, `DICE`, `APPS`) and scores the same as the random-text control (`...JUSTTEPTHEOTDIGZIPSCOLOOPASS...`, -3.721). That is overfitting, not a decryption.

## Why this attack

**Period 7.** The ciphertext-only statistics favour a periodic cipher with period 7:

- Column index of coincidence is raised at every multiple of 7 (7: 0.057, 14: 0.064, 21: 0.075, 28: 0.054) and flat elsewhere (0.017 to 0.049 at every other period from 2 to 30).
- 5 of the 12 repeated-digram pairs sit at spacings divisible by 7, against about 1.7 expected by chance. The pairs are `ZG` three times at 12, 54, 96 (42 apart), `XG` at 82/89 and `GU` at 90/97.
- There are no repeated trigrams.
- The period-7 value alone is weak evidence. Uniform random text reaches it at period 7 in 1% of trials, but at *some* period between 2 and 20 in 43% of trials (4,000 Monte Carlo trials). The pattern across all multiples of 7, together with the repeat spacings, is the real evidence.

**Ruling out the other untested items:**

- Autokey predicts no IC peaks at 14, 21 and 28.
- A running key predicts no periodicity at all.
- Hill needs a length divisible by its block size, and 109 is prime.
- Polybius-square fractionation is out because all 26 letters occur. Playfair is also out because the length is odd.
- A nomenclator cannot be tested.
- Non-English plaintext cannot be judged by the README's English-range rule.

That leaves the first item, a period-7 **Quagmire with a non-dictionary alphabet**. Round 1 built every Quagmire alphabet from the 9,600 words in `keywords.txt`, and it had already excluded the periodic Vigenere family on the A-Z and KRYPTOS alphabets at period 7.

**Why Quagmire I and not Quagmire III.** The first attempt was Quagmire III, the Kryptos K1/K2 construction (`q3_freekeyword.py`). It annealed the keyword string itself and re-solved the shifts for every candidate. It was abandoned on a synthetic cipher before PK9 was touched. It did not recover its own key in 90 s, and `q3_landscape_probe.py` shows why:

| keyword scored against a 109-letter Quagmire III cipher | best score/char after shift solve (mean) | letters correct (mean) |
|---|---|---|
| the true keyword | -2.918 | 109 |
| 1 random edit away | -4.376 | 44 |
| 2 edits away | -4.496 | 27 |
| random keywords (n = 3,000; 99th percentile -4.341) | -4.564 | - |

A single keyword edit shifts a block of the alphabetical tail. Because Quagmire III uses the same alphabet on both sides, most letters then decrypt wrongly, so a near-miss scores like random text and a search has no slope to climb at 109 letters. This matches round 1's own failed random-alphabet sanity cases. Quagmire IV has even more freedom.

Quagmire I does not have this problem. Its shifts act on the *straight* cipher alphabet (`p = A[(c - s_j) mod 26]`), so for the right shifts the re-aligned text `Y = C - s` is a simple substitution of the plaintext, **whatever the alphabet `A` is**. The shifts can therefore be found without the alphabet by maximising the IC of `Y`. What remains is one monoalphabetic substitution, which 109 letters can pin down. The same holds for the Beaufort and variant directions (`Y = s - C`, `Y = C + s`), since `A` absorbs the extra monoalphabetic map, and for keyword and fully random alphabets alike.

## Method (`q1_attack.py`)

1. **IC alignment.** All 26^6 = 308,915,776 relative shift vectors (d0 = 0) are scored by the letter coincidences they create between the 7 columns. This is a sum of 21 pairwise cross-correlation terms, evaluated in about 1.4 s. The best 32 of every (d1, d2, d3) block are merged and ranked, and the top 20,000 are kept.
2. **Simple substitution.** Alignments are annealed in that order: 4 chains per alignment, 8,000 swap proposals each, temperature 6 to 0.25 (geometric), on the repo's calibrated quadgram score. 64 alignments are vectorised per batch. This continues until the 300 s wall-clock budget is spent.
3. **Scoring.** The best candidates are re-scored with `kcore.score` and `english_check.coverage`, the same scorer and coverage test as round 1.

Every run uses the same seed (20260927) and runs on one core (`OMP/OPENBLAS/MKL_NUM_THREADS=1`). The null text is 109 uniform random letters from `random.Random(20260927)`.

## Rules fixed before the formal runs

- **English range:** unchanged from round 1.
- **Sanity pass:** the top candidate must carry the true relative shifts **and** have at least 104/109 correct letters. Exact recovery is reported separately. The reason for allowing near-exact recovery: with a free plaintext alphabet, letters that occur once or twice are not pinned down by 109 letters. On the development cipher the model's optimum (-2.904/char, 106/109 letters) outscored the true plaintext (-2.918/char).
- In the formal sanity run the attack met the strict version anyway: 109/109 letters.
- The anneal settings were tuned on a synthetic development cipher only, never on the sanity sentence and never on PK9.

## Compute

| run | wall clock (one core) | work |
|---|---|---|
| sanity | 301.4 s | 7,040 alignments, 28,160 anneals, 225 M candidate keys scored; true alignment ranked 14th |
| PK9 | 301.8 s | 6,976 alignments, 27,904 anneals, 223 M candidate keys |
| null | 301.2 s | 7,744 alignments, 30,976 anneals, 248 M candidate keys |
| **total** | **904.4 s** | 4.4 s (0.5 %) over the 900 s budget. Each run stops at the first batch boundary after 300 s. |

PK9 and null ran concurrently, one core each, after the sanity run had passed.

Outside that budget, about 4 minutes went on development runs. All of them used synthetic ciphers: the Quagmire III trial and landscape probe (plus about 20 s re-running the probe for this record), and the Quagmire I tuning and smoke tests. Under a minute went on ciphertext-only statistics of PK9 (IC by period, repeated digrams), used to choose the attack. PK9 was not decrypted before the sanity run passed.

## What this does and does not rule out

**Covered:** Quagmire I at period 7 with any plaintext alphabet (keyword-mixed or random) and any 7 shifts, in the Vigenere, Beaufort or variant direction. The coverage is subject to two limits of the search:

- **Alignment ranking.** Only the top 6,976 alignments by IC were annealed on PK9. The true alignment ranked 5th and 14th in the two synthetic tests.
- **Anneal success.** In the tuning runs at the true development alignment, a single chain scored at least as high as the true plaintext in 21 % of cases with 4,000 steps and in 44 % with 10,000 steps. The runs used 4 chains of 8,000 steps per alignment.

For reference, PK9's best re-aligned IC (0.066) is above the null text's (0.060) but below what the true alignment gave in the synthetic tests (0.074, 0.086). Part of PK9's figure is its own column structure, which exists before any alignment. This number is descriptive and not part of the verdict.

**Not covered:**

- Quagmire II, III and IV with non-dictionary alphabets. III has no usable search landscape at 109 letters, as shown above. II was not attempted.
- Periods other than 7. Period 14 has the higher raw column IC.
- Autokey, running key, Hill, fractionation, a nomenclator, and non-English plaintext.

## Files

| file | role |
|---|---|
| `q1_attack.py` | the attack; modes `sanity`, `pk9`, `null`, `report` |
| `sanity.json`, `sanity_log.jsonl`, `sanity_stdout.txt` | formal sanity run: key, ciphertext, alignment rank, every improvement |
| `pk9.json`, `pk9_log.jsonl`, `pk9_stdout.txt` | PK9 run: top 5 candidates, every improvement |
| `null.json`, `null_log.jsonl`, `null_stdout.txt` | null-control run, including the random ciphertext |
| `verdict.json` | the table's numbers and the three threshold checks |
| `q3_freekeyword.py`, `q3_landscape_probe.py`, `q3_landscape_probe_output.txt` | abandoned Quagmire III attempt (synthetic data only) and the probe behind the table above |

## Reproduce

Requires Python 3 and numpy; run from the repository root. Wall-clock budgets make exact key counts machine-dependent.

```bash
python round2/q1_attack.py sanity 300
python round2/q1_attack.py pk9 300
python round2/q1_attack.py null 300
python round2/q1_attack.py report
python round2/q3_landscape_probe.py
```
