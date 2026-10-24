"""Round 2 attack: Quagmire I at period 7 with an arbitrary (non-dictionary, even
fully random) plaintext alphabet, straight cipher alphabet, 7 free shifts.

Why this attack
---------------
README "Limitations" lists "Quagmire with a non-word alphabet or indicator" as never
tested: round 1 built every Quagmire alphabet from the 9 600 words of keywords.txt.
The ciphertext points at a period-7 polyalphabetic -- column IC is raised at every
multiple of 7 (7: .057, 14: .064, 21: .075, 28: .054) and flat elsewhere, and 5 of the
12 repeated-digram pairs sit at spacings divisible by 7 -- and round 1 excluded the
periodic Vigenere family on the A-Z and KRYPTOS alphabets at period 7, so the open
period-7 case is a mixed alphabet.

Of the Quagmire variants with a mixed alphabet, Quagmire III/IV cannot be recovered at
109 letters by annealing (round 1's own random-alphabet sanity cases failed, and a
round-2 keyword-string search failed for a structural reason, see README.md).
Quagmire I is different: its shifts act on the STRAIGHT cipher alphabet, so

    decrypt   p = A[(c - s_j) mod 26]          (A = keyed plaintext alphabet)

means Y = C - s is a monoalphabetic substitution of the plaintext for the right
shifts, whatever A is.  The relative shifts can therefore be found WITHOUT the
alphabet, by maximising the index of coincidence of the re-aligned text (an exact
search over all 26^6 relative shift vectors), and what is left is one simple
substitution, which is solvable at 109 letters.  The global shift is absorbed by A,
and the Beaufort and variant directions (Y = s - C, Y = C + s) are covered too,
because they differ from this only by a monoalphabetic map that A absorbs.

Search
------
1. Exhaustive IC alignment: every (d1..d6) with d0 = 0 is scored by the number of
   letter coincidences it creates between columns; alignments are then taken best
   first.
2. For each alignment in that order, Y = C - d is solved as a simple substitution by
   simulated annealing on the quadgram score (CHAINS independent chains per
   alignment, vectorised across alignments), until the wall-clock budget is spent.

Usage (from the repository root):
    python round2/q1_attack.py sanity <seconds>
    python round2/q1_attack.py pk9    <seconds>
    python round2/q1_attack.py null   <seconds>
    python round2/q1_attack.py report
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")          # one core per run: the budget is CPU time
import json, random, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import kcore as K                 # noqa: E402  quadgram model, cipher primitives, PK9
import english_check as E         # noqa: E402  dictionary word coverage

NAME = "quagmire1_freealphabet"
PERIOD = 7
KEEP = 20000                  # alignments kept from the exhaustive IC search
ALIGN_PER_BATCH = 64          # alignments annealed together
CHAINS = 4                    # simple-substitution anneals per alignment
STEPS = 8000                  # swap proposals per anneal
T0, T1 = 6.0, 0.25            # geometric temperature schedule, quadgram-score units
# Sanity pass rule, fixed before the formal sanity run: the top candidate must carry
# the true relative shifts and >= 104/109 correct letters.  Exact 109/109 is not
# required because, with a free plaintext alphabet, letters that occur once or twice
# are not pinned down by 109 letters of text: on the development cipher the model's
# optimum (-2.904/char, 106/109 letters) outscored the true plaintext (-2.918/char).
SANITY_MIN_LETTERS = 104
SEED = 20260927
ENG_ORDER = "ETAOINSHRDLCUMWFGYPBVKJXQZ"

QGF = np.load(os.path.join(ROOT, "quadgrams.npy")).astype(np.float32)


def qscore(P):
    """Calibrated quadgram score along the last axis of an int array of letters."""
    q = ((P[..., :-3] * 26 + P[..., 1:-2]) * 26 + P[..., 2:-1]) * 26 + P[..., 3:]
    return np.take(QGF, q).sum(axis=-1, dtype=np.float64)


# ------------------------------------------------------------ 1. alignment --
def column_counts(ct):
    n = np.zeros((PERIOD, 26))
    for j in range(PERIOD):
        np.add.at(n[j], ct[j::PERIOD], 1.0)
    return n


def align_rank(ct, keep=KEEP):
    """All 26^6 relative shift vectors (d0 = 0), best `keep` by cross-column letter
    coincidences of the re-aligned text Y_i = C_i - d_(i mod 7).

    coincidences(d) = sum_{j<l} M[j,l,(d_l - d_j) mod 26] + const,
    M[j,l,x] = sum_a n_j(a) * n_l(a + x).
    """
    n = column_counts(ct)
    M = np.zeros((PERIOD, PERIOD, 26))
    for j in range(PERIOD):
        for l in range(PERIOD):
            for x in range(26):
                M[j, l, x] = n[j] @ np.roll(n[l], -x)
    D = np.arange(26)
    # T[k,l][dk, dl] = M[k,l][(dl - dk) mod 26]
    T = {(k, l): M[k, l][(D[None, :] - D[:, None]) % 26]
         for k in range(PERIOD) for l in range(k + 1, PERIOD)}
    inner = (T[4, 5][:, :, None] + T[4, 6][:, None, :] + T[5, 6][None, :, :])  # (d4,d5,d6)
    per = 32                                  # keep this many from every 26^3 block
    vals = np.empty(26 ** 3 * per)
    idxs = np.empty((26 ** 3 * per, 6), dtype=np.int64)
    w = 0
    for d1 in range(26):
        for d2 in range(26):
            for d3 in range(26):
                base = (T[0, 1][0, d1] + T[0, 2][0, d2] + T[0, 3][0, d3]
                        + T[1, 2][d1, d2] + T[1, 3][d1, d3] + T[2, 3][d2, d3])
                u4 = T[0, 4][0] + T[1, 4][d1] + T[2, 4][d2] + T[3, 4][d3]
                u5 = T[0, 5][0] + T[1, 5][d1] + T[2, 5][d2] + T[3, 5][d3]
                u6 = T[0, 6][0] + T[1, 6][d1] + T[2, 6][d2] + T[3, 6][d3]
                tot = (inner + u4[:, None, None] + u5[None, :, None]
                       + u6[None, None, :]).ravel()
                top = np.argpartition(-tot, per)[:per]
                vals[w:w + per] = base + tot[top]
                idxs[w:w + per, 0] = d1
                idxs[w:w + per, 1] = d2
                idxs[w:w + per, 2] = d3
                idxs[w:w + per, 3] = top // 676
                idxs[w:w + per, 4] = (top // 26) % 26
                idxs[w:w + per, 5] = top % 26
                w += per
    order = np.argsort(-vals, kind="stable")[:keep]
    d = np.zeros((len(order), PERIOD), dtype=np.int64)
    d[:, 1:] = idxs[order]
    npairs = len(ct) * (len(ct) - 1) / 2
    same = sum((n[j] * (n[j] - 1) / 2).sum() for j in range(PERIOD))
    ic = (same + vals[order]) / npairs        # IC of the re-aligned text
    return d, ic


def align_score(ct, d):
    """IC of Y = C - d, for checking a single alignment."""
    y = [(c - d[i % PERIOD]) % 26 for i, c in enumerate(ct)]
    return K.ic(y)


# ------------------------------------------------ 2. simple substitution --
def anneal_mono(Y, rng):
    """Anneal B simple substitutions at once.  Y: (B, n) letters.  key[b, y] is the
    plaintext letter for intermediate letter y.  Returns best keys and scores."""
    B = Y.shape[0]
    r = np.arange(B)
    eng = np.array([ord(c) - 65 for c in ENG_ORDER])
    key = np.empty((B, 26), dtype=np.int64)
    for b in range(B):                        # frequency start + random perturbation
        cnt = np.bincount(Y[b], minlength=26) + rng.random(26) * 0.9
        key[b, np.argsort(-cnt)] = eng
        for _ in range(b % CHAINS * 3):
            i, j = rng.integers(0, 26, 2)
            key[b, i], key[b, j] = key[b, j], key[b, i]
    cur = qscore(np.take_along_axis(key, Y, axis=1))
    best, best_key = cur.copy(), key.copy()
    ratio = T1 / T0
    for i in range(STEPS):
        T = T0 * ratio ** (i / STEPS)
        a = rng.integers(0, 26, B)
        b = rng.integers(0, 26, B)
        ka, kb = key[r, a], key[r, b]
        key[r, a], key[r, b] = kb, ka
        sc = qscore(np.take_along_axis(key, Y, axis=1))
        dlt = sc - cur
        acc = (dlt >= 0) | (rng.random(B) < np.exp(np.minimum(dlt, 0.0) / T))
        rej = ~acc
        key[r[rej], a[rej]] = ka[rej]         # undo rejected swaps
        key[r[rej], b[rej]] = kb[rej]
        cur = np.where(acc, sc, cur)
        imp = cur > best
        best = np.where(imp, cur, best)
        best_key[imp] = key[imp]
    return best_key, best


# ------------------------------------------------------------------ driver --
def attack(ct_text, seconds, log_path, seed=SEED, target="", truth=None):
    """Spend `seconds` of wall clock (one core) and log every global improvement."""
    t0 = time.time()
    ct = np.asarray(K.to_vals(ct_text), dtype=np.int64)
    n = len(ct)
    rng = np.random.default_rng(seed)
    log = open(log_path, "w", encoding="utf-8")
    log.write(json.dumps({"event": "start", "method": NAME, "target": target,
                          "ciphertext": ct_text, "seconds": seconds, "seed": seed,
                          "keep": KEEP, "align_per_batch": ALIGN_PER_BATCH,
                          "chains": CHAINS, "steps": STEPS, "T0": T0, "T1": T1}) + "\n")
    dvec, ic = align_rank(ct)
    t_align = time.time() - t0
    info = {"event": "alignment", "t": round(t_align, 2),
            "top_ic": [round(float(x), 4) for x in ic[:5]],
            "top_d": dvec[:5].tolist(), "ic_at_rank_100": round(float(ic[99]), 4),
            "ic_at_rank_1000": round(float(ic[999]), 4)}
    if truth is not None:                     # sanity only: where is the true alignment?
        tv = np.array(truth, dtype=np.int64)
        rel = (tv - tv[0]) % 26
        hit = np.where((dvec == rel).all(axis=1))[0]
        info["true_rel_shifts"] = rel.tolist()
        info["true_alignment_rank"] = int(hit[0]) + 1 if len(hit) else None
        info["true_alignment_ic"] = round(align_score(ct.tolist(), rel), 4)
    log.write(json.dumps(info) + "\n")
    log.flush()

    t_end = t0 + seconds
    best = {"score": -1e18}
    seen = {}
    col = np.arange(n) % PERIOD
    done = 0
    while time.time() < t_end and done < len(dvec):
        dd = dvec[done:done + ALIGN_PER_BATCH]
        Yb = (ct[None, :] - dd[:, col]) % 26                   # (a, n)
        Y = np.repeat(Yb, CHAINS, axis=0)                      # (a*CHAINS, n)
        keys, sc = anneal_mono(Y, rng)
        for i in np.argsort(-sc)[:8]:
            a = int(i) // CHAINS
            s = float(sc[i])
            P = keys[i][Y[i]]
            text = K.to_text(P.tolist())
            rank = done + a + 1
            if text not in seen or seen[text]["score"] < s:
                seen[text] = {"plaintext": text, "score": round(s, 3),
                              "align_rank": rank, "align_ic": round(float(ic[rank - 1]), 4),
                              "rel_shifts": dd[a].tolist(),
                              "plain_alphabet": K.to_text(keys[i].tolist())}
            if s > best["score"] + 1e-6:
                best = dict(seen[text])
                best.update({"t": round(time.time() - t0, 2),
                             "per_char_fast": round(s / n, 4)})
                log.write(json.dumps(best) + "\n")
                log.flush()
        done += len(dd)

    elapsed = time.time() - t0
    top = sorted(seen.values(), key=lambda d: -d["score"])[:5]
    for d in top:                             # the repo's own scorer and coverage test
        v = K.to_vals(d["plaintext"])
        d["per_char"] = round(K.score(v) / len(v), 4)
        d["coverage"] = round(E.coverage(d["plaintext"]), 4)
        d["words"] = E.longest_words(d["plaintext"])
    top.sort(key=lambda d: -d["per_char"])
    summary = {"event": "end", "elapsed_s": round(elapsed, 1),
               "alignment_s": round(t_align, 1), "alignments_annealed": done,
               "anneals": done * CHAINS, "candidates_scored": done * CHAINS * (STEPS + 1),
               "alignment": info, "best": top[0], "top5": top}
    log.write(json.dumps(summary) + "\n")
    log.close()
    return summary


# ------------------------------------------------------------------- modes --
def _dictionary():
    kw = {w.strip() for w in open(os.path.join(ROOT, "keywords.txt"), encoding="ascii")}
    kw |= {w.strip() for w in open(os.path.join(ROOT, "wordlist.txt"), encoding="ascii")}
    return kw


def sanity_key(seed=4711):
    """A genuine Quagmire I key whose alphabet keyword and indicator are NOT
    dictionary words: random letter strings checked against keywords.txt and
    wordlist.txt."""
    r = random.Random(seed)
    words = _dictionary()
    while True:
        kw = "".join(chr(65 + r.randrange(26)) for _ in range(8))
        ind = "".join(chr(65 + r.randrange(26)) for _ in range(PERIOD))
        if kw not in words and ind not in words and len(set(kw)) >= 6:
            return kw, ind


def run_sanity(seconds):
    kw, ind = sanity_key()
    astr = K.keyed_alphabet(kw, K.STD_S)                 # keyed PLAINTEXT alphabet
    A = [ord(c) - 65 for c in astr]
    Ainv = K.inverse_of(A)
    shifts = [ord(c) - 65 for c in ind]                  # indicator on the straight alphabet
    pt = K.to_vals(K.SANITY_PT)
    ct = K.quag_encrypt(pt, Ainv, K.STD, shifts)         # c = (Ainv[p] + s) mod 26
    assert K.quag_decrypt(ct, A, K.STD_INV, shifts) == pt
    ct_text = K.to_text(ct)
    s = attack(ct_text, seconds, os.path.join(HERE, "sanity_log.jsonl"),
               target="SANITY", truth=shifts)
    got = s["best"]["plaintext"]
    exact = got == K.SANITY_PT
    letters = sum(a == b for a, b in zip(got, K.SANITY_PT))
    rel_true = [(x - shifts[0]) % 26 for x in shifts]
    shifts_ok = s["best"]["rel_shifts"] == rel_true
    ok = shifts_ok and letters >= SANITY_MIN_LETTERS
    first = None
    for line in open(os.path.join(HERE, "sanity_log.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        if d.get("plaintext") == K.SANITY_PT:
            first = d["t"]
            break
    res = {"mode": "sanity", "cipher": "Quagmire I, period 7",
           "alphabet_keyword": kw, "plain_alphabet": astr, "indicator": ind,
           "shifts": shifts, "ciphertext": ct_text, "plaintext": K.SANITY_PT,
           "true_per_char": round(K.score(pt) / len(pt), 4), "recovered": ok,
           "pass_rule": f"true relative shifts and >= {SANITY_MIN_LETTERS}/109 letters",
           "true_rel_shifts": rel_true, "shifts_correct": shifts_ok,
           "exact_match": exact, "letters_correct": letters,
           "first_recovered_t": first, **{k: s[k] for k in s if k != "event"}}
    json.dump(res, open(os.path.join(HERE, "sanity.json"), "w"), indent=2)
    al = s["alignment"]
    print(f"[sanity] alphabet keyword={kw} ({astr}) indicator={ind} shifts={shifts}")
    print(f"[sanity] true alignment rank={al['true_alignment_rank']} ic={al['true_alignment_ic']} "
          f"(top ic {al['top_ic'][0]}); alignments annealed={s['alignments_annealed']:,}")
    print(f"[sanity] shifts_correct={shifts_ok} letters={letters}/109 exact={exact} "
          f"best={s['best']['per_char']:+.3f}/char true={res['true_per_char']:+.3f}/char "
          f"coverage={s['best']['coverage']:.3f} first_exact_t={first}s elapsed={s['elapsed_s']}s")
    print(f"[sanity] got: {got}")
    print("SANITY", "PASS" if ok else "FAIL")
    return ok


def run_target(mode, seconds):
    if mode == "pk9":
        ct_text, target = K.PK9, "PK9"
    else:
        r = random.Random(20260927)
        ct_text = "".join(chr(65 + r.randrange(26)) for _ in range(len(K.PK9)))
        target = "NULL-UNIFORM-RANDOM"
    s = attack(ct_text, seconds, os.path.join(HERE, f"{mode}_log.jsonl"), target=target)
    res = {"mode": mode, "target": target, "ciphertext": ct_text,
           **{k: s[k] for k in s if k != "event"}}
    json.dump(res, open(os.path.join(HERE, f"{mode}.json"), "w"), indent=2)
    b = s["best"]
    print(f"[{mode}] best={b['per_char']:+.4f}/char coverage={b['coverage']:.3f} "
          f"align_rank={b['align_rank']} rel_shifts={b['rel_shifts']} "
          f"alignments annealed={s['alignments_annealed']:,} elapsed={s['elapsed_s']}s")
    print(f"[{mode}] top alignment IC={s['alignment']['top_ic'][0]}")
    print(f"[{mode}] {b['plaintext']}")


def report():
    san = json.load(open(os.path.join(HERE, "sanity.json")))
    pk9 = json.load(open(os.path.join(HERE, "pk9.json")))
    nul = json.load(open(os.path.join(HERE, "null.json")))
    b, nb = pk9["best"], nul["best"]
    margin = b["per_char"] - nb["per_char"]
    checks = {"score >= -3.30/char": b["per_char"] >= -3.30,
              "coverage >= 0.42": b["coverage"] >= 0.42,
              "margin >= +0.25/char over null": margin >= 0.25}
    english = all(checks.values())
    verdict = ("ENGLISH RANGE (all three thresholds pass)" if english else
               "not English (" + "; ".join(k for k, v in checks.items() if not v) + " failed)")
    out = {"sanity_recovered": san["recovered"], "sanity_rule": san["pass_rule"],
           "sanity_letters": san["letters_correct"], "sanity_exact": san["exact_match"],
           "sanity_per_char": san["best"]["per_char"],
           "sanity_coverage": san["best"]["coverage"],
           "pk9_per_char": b["per_char"],
           "pk9_coverage": b["coverage"], "null_per_char": nb["per_char"],
           "null_coverage": nb["coverage"], "margin": round(margin, 4),
           "checks": checks, "english_range": english, "verdict": verdict}
    json.dump(out, open(os.path.join(HERE, "verdict.json"), "w"), indent=2)
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    if mode == "sanity":
        sys.exit(0 if run_sanity(float(sys.argv[2])) else 1)
    elif mode in ("pk9", "null"):
        run_target(mode, float(sys.argv[2]))
    else:
        report()
