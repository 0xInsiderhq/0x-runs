"""ABANDONED before touching PK9 -- kept only as the record of why round 2 attacks
Quagmire I instead.  Never run on PK9 or on the null text.  On a synthetic
109-letter cipher it did not recover its own key in 90 s, and
q3_landscape_probe.py shows why: one edit away from the true keyword the
shift-solved score is already indistinguishable from a random keyword, so a
keyword search has no slope to follow at 109 letters (see README.md).

Original design notes follow.

Round 2 attack: Quagmire III, period 7, keyword-mixed alphabet built from an
ARBITRARY keyword (any letter string, not limited to keywords.txt), 7 free shifts.

Why this attack
---------------
README "Limitations" lists "Quagmire with a non-word alphabet or indicator" as never
tested.  Round 1 built Quagmire alphabets only from the 9 600 words in keywords.txt
(its free indicator phase already covered non-word shifts for those alphabets); its
only other alphabet test was a random 26-letter permutation, which it could not
recover even on its own sanity cipher.

The ciphertext points at a period-7 polyalphabetic: column IC is raised at every
multiple of 7 (7: .057, 14: .064, 21: .075, 28: .054) and flat elsewhere, and 5 of the
12 repeated-digram pairs sit at spacings divisible by 7 (ZG three times, 42 apart).
Periodic Vigenere/Beaufort/variant on the A-Z and KRYPTOS alphabets at period 7 was
searched to convergence in round 1, so the open period-7 case is a mixed alphabet.

Model (same convention as kcore.quag_*, Quagmire III: P alphabet is C alphabet):
    alphabet A = keyword letters (deduplicated) + remaining letters in A-Z order
    decrypt   p = A[(Ainv[c] - s_j) mod 26],  j = position mod 7
Keywords over the KRYPTOS base are covered too, because
    keyed_alphabet(W, KRYPTOS base) == keyed_alphabet(W + "KRYPTOS", A-Z base).

Search
------
Simulated annealing over the keyword string (replace / move / insert / delete a
letter), B chains vectorised in numpy.  Round 1's joint (26-letter permutation,
shifts) annealing failed because a wrong shift vector hides every alphabet move, so
here the shifts are never annealed blindly: for every proposed alphabet each column's
shift is re-solved by coordinate ascent on the quadgram score over its 3 best
shifts by English unigram likelihood plus its current shift.  The best chains get a
full 26-value shift polish at the end of each anneal.

Usage (from the repository root):
    python round2/q3_freekeyword.py sanity <seconds>
    python round2/q3_freekeyword.py pk9    <seconds>
    python round2/q3_freekeyword.py null   <seconds>
    python round2/q3_freekeyword.py report
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

NAME = "quagmire3_freekeyword"
PERIOD = 7
LMIN, LMAX = 1, 15            # distinct keyword letters (15 covers W+KRYPTOS for |W| <= 8)
B_CHAINS = 128
STEPS = 4000                  # SA steps per anneal; all chains restart together
T0, T1 = 25.0, 1.0            # geometric temperature schedule, in quadgram-score units
TOPK = 3                      # unigram-best shifts tried per column (plus the current one)
P_MOVES = (0.55, 0.15, 0.15, 0.15)   # replace/swap, move, insert, delete
SEED = 20260927

QGF = np.load(os.path.join(ROOT, "quadgrams.npy")).astype(np.float32)
LOGF = np.log(np.asarray(K.ENG_FREQ, dtype=np.float64)).astype(np.float32)
V26 = np.arange(26)


def qscore(P):
    """Calibrated quadgram score along the last axis of an int array of letters."""
    q = ((P[..., :-3] * 26 + P[..., 1:-2]) * 26 + P[..., 2:-1]) * 26 + P[..., 3:]
    return np.take(QGF, q).sum(axis=-1, dtype=np.float64)


class Engine:
    """B annealing chains over (keyword, shifts).

    A keyword is stored as a sort key per letter: key[b, x] = position of x in the
    keyword, or 26 + x if x is in the tail, so argsort(key) is the alphabet and the
    tail is automatically in A-Z order.
    """

    def __init__(self, ct_vals, B, rng):
        self.ct = np.asarray(ct_vals, dtype=np.int64)
        self.n = len(self.ct)
        self.col = np.arange(self.n) % PERIOD
        self.B, self.rng = B, rng
        self.rows = np.arange(B)
        cnt = np.zeros((PERIOD, 26), dtype=np.float32)
        for j in range(PERIOD):
            np.add.at(cnt[j], self.ct[j::PERIOD], 1.0)
        self.cntT = np.ascontiguousarray(cnt.T)          # (26 cipher letters, 7 columns)
        self.key = np.zeros((B, 26))
        self.sh = np.zeros((B, PERIOD), dtype=np.int64)
        self.cur = np.full(B, -1e18)
        self.evals = 0

    # ------------------------------------------------------------ alphabets --
    @staticmethod
    def renorm(key):
        """Re-number keyword sort keys to 0..L-1 after a move."""
        A = np.argsort(key, axis=1, kind="stable")
        L = (key < 26).sum(axis=1)
        out = 26.0 + np.broadcast_to(V26, key.shape).astype(np.float64)
        pos = np.broadcast_to(V26, key.shape)
        inkw = pos < L[:, None]
        rr = np.broadcast_to(np.arange(key.shape[0])[:, None], key.shape)
        out[rr[inkw], A[inkw]] = pos[inkw]
        return out

    @staticmethod
    def tables(A):
        """D[b, v, c]: plaintext letter for cipher letter c under shift v."""
        Bn = A.shape[0]
        Ainv = np.empty_like(A)
        np.put_along_axis(Ainv, A, np.broadcast_to(V26, A.shape), axis=1)
        idx = (Ainv[:, None, :] - V26[None, :, None]) % 26
        return A[np.arange(Bn)[:, None, None], idx]

    def plain(self, D, sh):
        """Decrypt: sh (Bn, 7) -> (Bn, n);  sh (Bn, K, 7) -> (Bn, K, n)."""
        Bn = D.shape[0]
        if sh.ndim == 2:
            idx = sh[:, self.col] * 26 + self.ct[None, :] + (np.arange(Bn) * 676)[:, None]
        else:
            idx = (sh[:, :, self.col] * 26 + self.ct[None, None, :]
                   + (np.arange(Bn) * 676)[:, None, None])
        return np.take(D.reshape(-1), idx)

    # --------------------------------------------------------------- shifts --
    def solve_shifts(self, D, sh0):
        """Per-column coordinate ascent on the quadgram score.  Candidates for each
        column: its current shift plus its TOPK best shifts by unigram likelihood."""
        Bn = D.shape[0]
        r = np.arange(Bn)
        U = np.matmul(LOGF[D], self.cntT)                        # (Bn, 26 shifts, 7)
        top = np.argpartition(-U, TOPK - 1, axis=1)[:, :TOPK, :]
        top1 = U.argmax(axis=1)
        cand = np.concatenate([sh0[:, None, :], top], axis=1)    # (Bn, K, 7)
        s_a = qscore(self.plain(D, sh0))
        s_b = qscore(self.plain(D, top1))
        use_b = s_b > s_a
        sh = np.where(use_b[:, None], top1, sh0)
        best = np.maximum(s_a, s_b)
        Kc = cand.shape[1]
        for j in range(PERIOD):
            S = np.repeat(sh[:, None, :], Kc, axis=1)
            S[:, :, j] = cand[:, :, j]
            sc = qscore(self.plain(D, S))                        # (Bn, K)
            k = sc.argmax(axis=1)
            v = sc[r, k]
            better = v > best
            sh[better, j] = cand[r[better], k[better], j]
            best = np.where(better, v, best)
        self.evals += Bn * (2 + PERIOD * Kc)
        return sh, best

    def polish_full(self, D, sh, sweeps=2):
        """Coordinate ascent over all 26 values of every shift."""
        Bn = D.shape[0]
        r = np.arange(Bn)
        sh = sh.copy()
        best = qscore(self.plain(D, sh))
        for _ in range(sweeps):
            for j in range(PERIOD):
                S = np.repeat(sh[:, None, :], 26, axis=1)
                S[:, :, j] = V26[None, :]
                sc = qscore(self.plain(D, S))
                k = sc.argmax(axis=1)
                v = sc[r, k]
                better = v > best + 1e-9
                sh[better, j] = k[better]
                best = np.where(better, v, best)
        self.evals += Bn * (1 + sweeps * PERIOD * 26)
        return sh, best

    # ---------------------------------------------------------------- moves --
    def reset(self):
        """Every chain restarts from a random keyword of 4..10 distinct letters."""
        B, rng = self.B, self.rng
        key = 26.0 + np.tile(V26, (B, 1)).astype(np.float64)
        L = rng.integers(4, 11, B)
        perm = np.argsort(rng.random((B, 26)), axis=1)
        pos = np.broadcast_to(V26, (B, 26))
        inkw = pos < L[:, None]
        rr = np.broadcast_to(self.rows[:, None], (B, 26))
        key[rr[inkw], perm[inkw]] = pos[inkw]
        A = np.argsort(key, axis=1, kind="stable")
        D = self.tables(A)
        U = np.matmul(LOGF[D], self.cntT)
        self.sh, self.cur = self.solve_shifts(D, U.argmax(axis=1))
        self.key = key

    def propose(self):
        B, rng, r = self.B, self.rng, self.rows
        key = self.key.copy()
        A = np.argsort(key, axis=1, kind="stable")
        L = (key < 26).sum(axis=1)
        mt = rng.choice(4, size=B, p=P_MOVES)
        mt = np.where((mt == 2) & (L >= LMAX), 0, mt)
        mt = np.where((mt == 3) & (L <= LMIN), 0, mt)
        u = rng.random((B, 3))
        ipos = np.minimum((u[:, 0] * L).astype(np.int64), L - 1)
        y = A[r, ipos]                                   # a keyword letter
        m = mt == 0                                      # replace y by random x
        if m.any():                                      # (swap if x is in the keyword)
            x = rng.integers(0, 26, B)
            kx, ky = key[r, x].copy(), key[r, y].copy()
            sw = m & (kx < 26)
            key[r[sw], x[sw]] = ky[sw]
            key[r[sw], y[sw]] = kx[sw]
            rp = m & (kx >= 26)
            key[r[rp], x[rp]] = ky[rp]
            key[r[rp], y[rp]] = 26.0 + y[rp]
        m = mt == 1                                      # move y within the keyword
        if m.any():
            jpos = np.minimum((u[:, 1] * L).astype(np.int64), L - 1)
            newk = np.where(jpos > ipos, jpos + 0.5, jpos - 0.5)
            key[r[m], y[m]] = newk[m]
        m = mt == 2                                      # insert a tail letter
        if m.any():
            tpos = L + np.minimum((u[:, 1] * (26 - L)).astype(np.int64), 25 - L)
            xt = A[r, tpos]
            jpos = np.minimum((u[:, 2] * (L + 1)).astype(np.int64), L)
            key[r[m], xt[m]] = jpos[m] - 0.5
        m = mt == 3                                      # delete y
        if m.any():
            key[r[m], y[m]] = 26.0 + y[m]
        return self.renorm(key)

    def step(self, T):
        newkey = self.propose()
        D = self.tables(np.argsort(newkey, axis=1, kind="stable"))
        sh, sc = self.solve_shifts(D, self.sh)
        d = sc - self.cur
        acc = (d >= 0) | (self.rng.random(self.B) < np.exp(np.minimum(d, 0.0) / T))
        self.key[acc] = newkey[acc]
        self.sh[acc] = sh[acc]
        self.cur[acc] = sc[acc]

    def polish_top(self, m=16):
        top = np.argsort(-self.cur)[:m]
        D = self.tables(np.argsort(self.key[top], axis=1, kind="stable"))
        sh, sc = self.polish_full(D, self.sh[top])
        self.sh[top] = sh
        self.cur[top] = sc

    def describe(self, b):
        key = self.key[b]
        A = np.argsort(key, kind="stable")
        L = int((key < 26).sum())
        P = self.plain(self.tables(A[None, :]), self.sh[b:b + 1])[0]
        return {"plaintext": K.to_text(P.tolist()),
                "keyword": K.to_text(A[:L].tolist()),
                "alphabet": K.to_text(A.tolist()),
                "shifts": [int(s) for s in self.sh[b]],
                "indicator": K.to_text([int(A[s]) for s in self.sh[b]])}


# ------------------------------------------------------------------ driver --
def attack(ct_text, seconds, log_path, seed=SEED, target=""):
    """Anneal for `seconds` of wall clock on one core; log every global improvement."""
    ct = K.to_vals(ct_text)
    rng = np.random.default_rng(seed)
    eng = Engine(ct, B_CHAINS, rng)
    log = open(log_path, "w", encoding="utf-8")
    t0 = time.time()
    t_end = t0 + seconds
    log.write(json.dumps({"event": "start", "method": NAME, "target": target,
                          "ciphertext": ct_text, "seconds": seconds, "seed": seed,
                          "chains": B_CHAINS, "steps_per_anneal": STEPS,
                          "T0": T0, "T1": T1, "topk": TOPK}) + "\n")
    best = {"score": -1e18}
    seen = {}                                   # plaintext -> best record, for a top list
    anneals = steps = 0
    ratio = T1 / T0

    def consider(b, stage):
        nonlocal best
        s = float(eng.cur[b])
        if s <= best["score"] + 1e-6:
            return
        rec = eng.describe(b)
        rec.update({"t": round(time.time() - t0, 2), "evals": int(eng.evals),
                    "anneal": anneals, "stage": stage, "score": round(s, 3),
                    "per_char": round(s / len(ct), 4)})
        best = rec
        log.write(json.dumps(rec) + "\n")
        log.flush()
        if rec["plaintext"] not in seen or seen[rec["plaintext"]]["score"] < s:
            seen[rec["plaintext"]] = rec

    while time.time() < t_end:
        eng.reset()
        anneals += 1
        for i in range(STEPS):
            eng.step(T0 * ratio ** (i / STEPS))
            steps += 1
            consider(int(np.argmax(eng.cur)), "anneal")
            if time.time() >= t_end:
                break
        eng.polish_top()
        for b in np.argsort(-eng.cur)[:16]:
            d = eng.describe(int(b))
            s = float(eng.cur[b])
            if d["plaintext"] not in seen or seen[d["plaintext"]]["score"] < s:
                d.update({"score": round(s, 3), "anneal": anneals, "stage": "polish"})
                seen[d["plaintext"]] = d
        consider(int(np.argmax(eng.cur)), "polish")

    elapsed = time.time() - t0
    # final judgement uses the repo's own scorer (float64) and coverage test
    top = sorted(seen.values(), key=lambda d: -d["score"])[:5]
    for d in top:
        v = K.to_vals(d["plaintext"])
        d["per_char"] = round(K.score(v) / len(v), 4)
        d["coverage"] = round(E.coverage(d["plaintext"]), 4)
        d["words"] = E.longest_words(d["plaintext"])
    top.sort(key=lambda d: -d["per_char"])
    summary = {"event": "end", "elapsed_s": round(elapsed, 1), "anneals": anneals,
               "sa_steps_per_chain": steps, "candidates_scored": int(eng.evals),
               "best": top[0], "top5": top}
    log.write(json.dumps(summary) + "\n")
    log.close()
    return summary


# ------------------------------------------------------------------- modes --
def _words():
    kw = {w.strip() for w in open(os.path.join(ROOT, "keywords.txt"), encoding="ascii")}
    kw |= {w.strip() for w in open(os.path.join(ROOT, "wordlist.txt"), encoding="ascii")}
    return kw


def sanity_key(seed=4711):
    """A genuine Quagmire III key whose keyword and indicator are NOT dictionary
    words: random letter strings, checked against keywords.txt and wordlist.txt."""
    r = random.Random(seed)
    words = _words()
    while True:
        kw = "".join(chr(65 + r.randrange(26)) for _ in range(8))
        ind = "".join(chr(65 + r.randrange(26)) for _ in range(PERIOD))
        if kw not in words and ind not in words and len(set(kw)) >= 6:
            return kw, ind


def run_sanity(seconds):
    kw, ind = sanity_key()
    astr = K.keyed_alphabet(kw, K.STD_S)
    A = [ord(c) - 65 for c in astr]
    Ainv = K.inverse_of(A)
    shifts = [Ainv[ord(c) - 65] for c in ind]
    pt = K.to_vals(K.SANITY_PT)
    ct = K.quag_encrypt(pt, Ainv, A, shifts)
    assert K.quag_decrypt(ct, A, Ainv, shifts) == pt
    ct_text = K.to_text(ct)
    s = attack(ct_text, seconds, os.path.join(HERE, "sanity_log.jsonl"), target="SANITY")
    got = s["best"]["plaintext"]
    ok = got == K.SANITY_PT
    res = {"mode": "sanity", "keyword": kw, "alphabet": astr, "indicator": ind,
           "shifts": shifts, "ciphertext": ct_text, "plaintext": K.SANITY_PT,
           "true_per_char": round(K.score(pt) / len(pt), 4),
           "recovered": ok,
           "letters_correct": sum(a == b for a, b in zip(got, K.SANITY_PT)),
           "first_recovered_t": None, **{k: s[k] for k in s if k != "event"}}
    for line in open(os.path.join(HERE, "sanity_log.jsonl"), encoding="utf-8"):
        d = json.loads(line)
        if d.get("plaintext") == K.SANITY_PT:
            res["first_recovered_t"] = d["t"]
            break
    json.dump(res, open(os.path.join(HERE, "sanity.json"), "w"), indent=2)
    print(f"[sanity] keyword={kw} alphabet={astr} indicator={ind} shifts={shifts}")
    print(f"[sanity] recovered={ok} letters={res['letters_correct']}/109 "
          f"best={s['best']['per_char']:+.3f}/char true={res['true_per_char']:+.3f}/char "
          f"first_recovered_t={res['first_recovered_t']} "
          f"candidates={s['candidates_scored']:,}")
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
          f"keyword={b['keyword']} indicator={b['indicator']} "
          f"candidates={s['candidates_scored']:,} elapsed={s['elapsed_s']}s")
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
    verdict = "ENGLISH RANGE (all three thresholds pass)" if english else \
        "not English (" + ", ".join(k for k, v in checks.items() if not v) + " failed)"
    out = {"sanity_recovered": san["recovered"], "pk9_per_char": b["per_char"],
           "pk9_coverage": b["coverage"], "null_per_char": nb["per_char"],
           "margin": round(margin, 4), "checks": checks, "english_range": english,
           "verdict": verdict}
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
