#!/usr/bin/env python3
"""Independent reference simulator of the Enigma I (Wehrmacht / Heer).

Three rotors chosen from I..V, reflector UKW-B or UKW-C, ring settings,
plugboard with up to 13 pairs.  Rotors are stepped BEFORE each letter is
enciphered, including the middle-rotor double step.

Ring settings are given as letters (A = ring 01) or as numbers ("02 21 12").

Usage:
  python enigma_ref.py --rotors II,IV,V --ref B --rings BUL --pos BLA \
         --plugs "AV BS CG" --text XXXX
  python enigma_ref.py --rotors ... --ref B --rings ... --plugs "..." \
         --ground GTA --enckey KCI --text <cipher>
  python enigma_ref.py --selftest
"""
import argparse
import random
import sys

ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

ROTORS = {
    'I':   ('EKMFLGDQVZNTOWYHXUSPAIBRCJ', 'Q'),
    'II':  ('AJDKSIRUXBLHWTMCQGZNPYFVOE', 'E'),
    'III': ('BDFHJLCPRTXVZNYEIWGAKMUSQO', 'V'),
    'IV':  ('ESOVPZJAYQUIRHXLNFTGKDCMWB', 'J'),
    'V':   ('VZBRGITYUPSDNHLWMXFCKQAEOJ', 'Z'),
}
REFLECTORS = {
    'B': 'YRUHQSLDPXNGOKMIEBFZCWVJAT',
    'C': 'FVPJIAOYEDRZXWGCTKUQSBNMHL',
}


def _check_tables():
    for name, (w, n) in ROTORS.items():
        assert sorted(w) == list(ALPHA), 'rotor %s not a permutation' % name
        assert n in ALPHA
    for name, w in REFLECTORS.items():
        assert sorted(w) == list(ALPHA), 'UKW %s not a permutation' % name
        for i, c in enumerate(w):
            j = ALPHA.index(c)
            assert j != i, 'UKW %s has fixed point' % name
            assert ALPHA.index(w[j]) == i, 'UKW %s not an involution' % name


_check_tables()


def _letters(s):
    return ''.join(ch for ch in s.upper() if ch in ALPHA)


def parse_triple(s, what='setting'):
    """Accept 'BUL', 'B U L', '02 21 12', '2,21,12' -> list of 3 ints 0..25."""
    s = s.strip()
    toks = [t for t in s.replace(',', ' ').replace('-', ' ').replace('.', ' ').split() if t]
    if len(toks) == 3 and all(t.isdigit() for t in toks):
        vals = [int(t) - 1 for t in toks]
        if not all(0 <= v < 26 for v in vals):
            raise ValueError('%s numbers must be 01..26: %r' % (what, s))
        return vals
    letters = _letters(s)
    if len(letters) != 3:
        raise ValueError('%s must be 3 letters or 3 numbers: %r' % (what, s))
    return [ALPHA.index(c) for c in letters]


def parse_plugs(s):
    """'AV BS CG' or 'AVBSCG' -> 26-entry swap table."""
    table = list(range(26))
    if not s:
        return table
    letters = _letters(s)
    if len(letters) % 2:
        raise ValueError('plugboard needs an even number of letters: %r' % s)
    if len(letters) // 2 > 13:
        raise ValueError('at most 13 plug pairs')
    if len(set(letters)) != len(letters):
        raise ValueError('a letter is used twice on the plugboard: %r' % s)
    for i in range(0, len(letters), 2):
        a, b = ALPHA.index(letters[i]), ALPHA.index(letters[i + 1])
        table[a], table[b] = b, a
    return table


class Enigma:
    def __init__(self, rotors=('I', 'II', 'III'), reflector='B', rings='AAA',
                 pos='AAA', plugs=''):
        if isinstance(rotors, str):
            rotors = tuple(r.strip().upper() for r in rotors.split(','))
        rotors = tuple(r.upper() for r in rotors)
        if len(rotors) != 3:
            raise ValueError('need exactly 3 rotors')
        if len(set(rotors)) != 3:
            raise ValueError('rotors must be distinct')
        for r in rotors:
            if r not in ROTORS:
                raise ValueError('unknown rotor %r' % r)
        reflector = reflector.upper().replace('UKW', '').replace('-', '').strip()
        if reflector not in REFLECTORS:
            raise ValueError('unknown reflector %r' % reflector)
        self.names = rotors                      # left, middle, right
        self.fwd = [[ALPHA.index(c) for c in ROTORS[r][0]] for r in rotors]
        self.bwd = []
        for f in self.fwd:
            inv = [0] * 26
            for i, o in enumerate(f):
                inv[o] = i
            self.bwd.append(inv)
        self.notch = [ALPHA.index(ROTORS[r][1]) for r in rotors]
        self.ukw = [ALPHA.index(c) for c in REFLECTORS[reflector]]
        self.rings = parse_triple(rings, 'rings') if isinstance(rings, str) else list(rings)
        self.pos = parse_triple(pos, 'position') if isinstance(pos, str) else list(pos)
        self.plug = parse_plugs(plugs) if isinstance(plugs, str) else list(plugs)

    def windows(self):
        return ''.join(ALPHA[p] for p in self.pos)

    def step(self):
        p = self.pos
        if p[1] == self.notch[1]:          # middle at notch: double step
            p[0] = (p[0] + 1) % 26
            p[1] = (p[1] + 1) % 26
        elif p[2] == self.notch[2]:        # right at notch: carry to middle
            p[1] = (p[1] + 1) % 26
        p[2] = (p[2] + 1) % 26

    def _through(self, table, i, c):
        sh = (self.pos[i] - self.rings[i]) % 26
        return (table[(c + sh) % 26] - sh) % 26

    def press(self, ch):
        self.step()
        c = self.plug[ALPHA.index(ch)]
        for i in (2, 1, 0):
            c = self._through(self.fwd[i], i, c)
        c = self.ukw[c]
        for i in (0, 1, 2):
            c = self._through(self.bwd[i], i, c)
        return ALPHA[self.plug[c]]

    def run(self, text):
        return ''.join(self.press(ch) for ch in _letters(text))


def enigma(text, rotors=('I', 'II', 'III'), reflector='B', rings='AAA',
           pos='AAA', plugs=''):
    return Enigma(rotors, reflector, rings, pos, plugs).run(text)


def decrypt_indicator(ground, enckey, text, rotors, reflector, rings, plugs):
    """1941 procedure: encipher/decipher the 3-letter key at the ground
    setting (sent in clear), then use the result as the message key."""
    msgkey = enigma(enckey, rotors, reflector, rings, ground, plugs)
    return msgkey, enigma(text, rotors, reflector, rings, msgkey, plugs)


def groups(s, n=5):
    return ' '.join(s[i:i + n] for i in range(0, len(s), n))


# ---------------------------------------------------------------- self-tests

def selftest(verbose=True):
    ok_all = True

    def report(name, ok, detail=''):
        nonlocal ok_all
        ok_all = ok_all and ok
        if verbose:
            print('[%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                                 (' -- ' + detail) if detail else ''))

    # (1) basic vector
    out = enigma('AAAAA', ('I', 'II', 'III'), 'B', 'AAA', 'AAA', '')
    report('1 I-II-III UKW-B rings AAA pos AAA: AAAAA -> ' + out,
           out == 'BDZGO', 'expected BDZGO')

    # (2) double step
    m = Enigma(('I', 'II', 'III'), 'B', 'AAA', 'ADU', '')
    seen = []
    for _ in range(4):
        m.press('A')
        seen.append(m.windows())
    report('2 double step from ADU: ' + ' '.join(seen),
           seen == ['ADV', 'AEW', 'BFX', 'BFY'], 'expected ADV AEW BFX BFY')

    # (3) reciprocity + no self-encipherment, random settings
    rng = random.Random(12345)
    trials, letters, bad_recip, bad_fixed = 500, 0, 0, 0
    names = list(ROTORS)
    for _ in range(trials):
        rot = tuple(rng.sample(names, 3))
        ref = rng.choice('BC')
        rings = ''.join(rng.choice(ALPHA) for _ in range(3))
        pos = ''.join(rng.choice(ALPHA) for _ in range(3))
        np_ = rng.randint(0, 13)
        perm = rng.sample(ALPHA, 2 * np_)
        plugs = ' '.join(perm[i] + perm[i + 1] for i in range(0, 2 * np_, 2))
        pt = ''.join(rng.choice(ALPHA) for _ in range(rng.randint(1, 700)))
        ct = enigma(pt, rot, ref, rings, pos, plugs)
        back = enigma(ct, rot, ref, rings, pos, plugs)
        letters += len(pt)
        if back != pt:
            bad_recip += 1
        if any(a == b for a, b in zip(pt, ct)):
            bad_fixed += 1
    report('3 reciprocity (%d random settings, %d letters)' % (trials, letters),
           bad_recip == 0, '%d failures' % bad_recip)
    report('3 no letter enciphers to itself', bad_fixed == 0,
           '%d settings with a fixed point' % bad_fixed)

    # extra: rotor period with double stepping is 26*25*26 = 16900
    m = Enigma(('I', 'II', 'III'), 'B', 'AAA', 'AAA', '')
    start = m.windows()
    n = 0
    while True:
        m.step()
        n += 1
        if m.windows() == start or n > 20000:
            break
    report('extra stepping period = %d' % n, n == 16900, 'expected 16900')

    # extra: ring setting equals shifting position and input/output
    # (ring +1 and pos +1 on right rotor gives same core substitution)
    a = Enigma(('I', 'II', 'III'), 'B', 'AAB', 'AAB', '')
    b = Enigma(('I', 'II', 'III'), 'B', 'AAA', 'AAA', '')
    # these differ in notch timing only after 21 letters; compare first 20
    ta = a.run('HELLOWORLDTESTABCDEF')
    tb = b.run('HELLOWORLDTESTABCDEF')
    report('extra ring/pos offset invariance (first 20 letters)', ta == tb,
           '%s vs %s' % (ta, tb))

    # extra: ring-setting convention vector (I,II,III, B, rings BBB, pos AAA)
    out = enigma('AAAAA', ('I', 'II', 'III'), 'B', 'BBB', 'AAA', '')
    report('extra rings BBB pos AAA: AAAAA -> ' + out, out == 'EWTYX',
           'expected EWTYX')

    # informational (from memory; not a MUST-pass): 1941 Barbarossa sample,
    # II IV V, UKW-B, rings 02 21 12, plugs AV BS CG DL FU HZ IN KM OW RX,
    # message key BLA.
    ct = ('EDPUDNRGYSZRCXNUYTPOMRMBOFKTBZREZKMLXLVEFGUEYSIOZVEQMIKUBPMMYLKLTTDEIS'
          'MDICAGYKUACTCDOMOHWXMUUIAUBSTSLRNBZSZWNRFXWFYSSXJZVIJHIDISHPRKLKAYUPAD'
          'TXQSPINQMATLPIFSVKDASCTACDPBOPVHJK')
    pt = enigma(ct, ('II', 'IV', 'V'), 'B', '02 21 12', 'BLA',
                'AV BS CG DL FU HZ IN KM OW RX')
    if verbose:
        print('[INFO] Barbarossa sample (memory) decrypts to: ' + pt[:60] + '...')
    return ok_all


def main(argv=None):
    ap = argparse.ArgumentParser(description='Enigma I reference simulator')
    ap.add_argument('--rotors', default='I,II,III', help='left,middle,right e.g. II,IV,V')
    ap.add_argument('--ref', default='B', help='B or C')
    ap.add_argument('--rings', default='AAA', help="letters (A=01) or '02 21 12'")
    ap.add_argument('--pos', default='AAA', help='start position (window letters)')
    ap.add_argument('--plugs', default='', help="e.g. 'AV BS CG'")
    ap.add_argument('--text', default=None)
    ap.add_argument('--ground', default=None, help='ground setting (indicator mode)')
    ap.add_argument('--enckey', default=None, help='enciphered message key (indicator mode)')
    ap.add_argument('--groups', action='store_true', help='print in 5-letter groups')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args(argv)

    if a.selftest:
        ok = selftest()
        print('SELFTEST: %s' % ('ALL PASS' if ok else 'FAILURES'))
        return 0 if ok else 1

    rotors = tuple(r.strip().upper() for r in a.rotors.split(','))
    fmt = groups if a.groups else (lambda s: s)
    if a.ground or a.enckey:
        if not (a.ground and a.enckey):
            ap.error('--ground and --enckey must be given together')
        msgkey = enigma(a.enckey, rotors, a.ref, a.rings, a.ground, a.plugs)
        print('message key: %s' % msgkey)
        if a.text:
            print(fmt(enigma(a.text, rotors, a.ref, a.rings, msgkey, a.plugs)))
        return 0
    if a.text is None:
        ap.error('--text required')
    print(fmt(enigma(a.text, rotors, a.ref, a.rings, a.pos, a.plugs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
