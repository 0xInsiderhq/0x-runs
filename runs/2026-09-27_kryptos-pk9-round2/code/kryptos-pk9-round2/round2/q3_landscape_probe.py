"""Why the Quagmire III keyword search was abandoned (synthetic cipher only, never PK9).

Encrypts a 109-letter development sentence with Quagmire III (keyword QZVHBMXW,
indicator JDOTRLE, period 7), then scores keywords at 0-4 random edits from the true
one, each with its shifts solved exactly as the search would (unigram top-3 +
quadgram coordinate ascent, then a full 26-value polish).  A search can only work if
near-miss keywords score clearly above random ones; they do not.

    python round2/q3_landscape_probe.py
"""
import os, random, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import q3_freekeyword as Q   # noqa: E402

K = Q.K
DEV = ("INTHELATEAFTERNOONTHETRAVELLERSREACHEDTHELITTLEVILLAGEATTHEFOOTOFTHEHILLS"
       "WHERETHEYHOPEDTOFINDFOODANDSHELTERFORTHENIGHTBEFORE")[:109]
KW, IND = "QZVHBMXW", "JDOTRLE"
astr = K.keyed_alphabet(KW, K.STD_S)
A = [ord(c) - 65 for c in astr]
Ainv = K.inverse_of(A)
ct = K.quag_encrypt(K.to_vals(DEV), Ainv, A, [Ainv[ord(c) - 65] for c in IND])
eng = Q.Engine(ct, 1, np.random.default_rng(0))
truth = np.array(K.to_vals(DEV))


def F(words):
    As = np.array([[ord(c) - 65 for c in K.keyed_alphabet(w, K.STD_S)] for w in words])
    D = eng.tables(As)
    s1, sc1 = eng.solve_shifts(D, np.matmul(Q.LOGF[D], eng.cntT).argmax(axis=1))
    s2, sc2 = eng.polish_full(D, s1, sweeps=3)
    corr = np.array([(p == truth).sum() for p in eng.plain(D, s2)])
    return sc1 / 109, sc2 / 109, corr


r = random.Random(5)
L26 = [chr(65 + i) for i in range(26)]


def edit(w, k):
    w = list(w)
    for _ in range(k):
        op = r.random()
        if op < 0.5:
            w[r.randrange(len(w))] = r.choice([c for c in L26 if c not in w])
        elif op < 0.75 and len(w) > 2:
            del w[r.randrange(len(w))]
        else:
            w.insert(r.randrange(len(w) + 1), r.choice([c for c in L26 if c not in w]))
    return "".join(w)


print("true keyword : solve %.3f  polish %.3f  correct %d" % tuple(x[0] for x in F([KW])))
for k in (1, 2, 3, 4):
    a, b, c = F([edit(KW, k) for _ in range(300)])
    print("%d edits (n=300): polish mean %.3f max %.3f | correct letters mean %.0f, "
          "share >= 100: %.2f" % (k, b.mean(), b.max(), c.mean(), (c >= 100).mean()))
a, b, c = F(["".join(r.sample(KW, len(KW))) for _ in range(300)])
print("same letters, permuted: polish mean %.3f max %.3f, correct mean %.0f"
      % (b.mean(), b.max(), c.mean()))
a, b, c = F(["".join(r.sample(L26, r.randint(4, 10))) for _ in range(3000)])
print("random keywords (n=3000): polish mean %.3f  p99 %.3f  max %.3f"
      % (b.mean(), np.percentile(b, 99), b.max()))
