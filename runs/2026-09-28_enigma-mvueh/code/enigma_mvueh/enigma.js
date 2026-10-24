'use strict';
// Enigma I core: rotors I-V, UKW B/C. Letters are 0..25.
const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const ROT = {
  I:   ['EKMFLGDQVZNTOWYHXUSPAIBRCJ', 'Q'],
  II:  ['AJDKSIRUXBLHWTMCQGZNPYFVOE', 'E'],
  III: ['BDFHJLCPRTXVZNYEIWGAKMUSQO', 'V'],
  IV:  ['ESOVPZJAYQUIRHXLNFTGKDCMWB', 'J'],
  V:   ['VZBRGITYUPSDNHLWMXFCKQAEOJ', 'Z'],
};
const REF = { B: 'YRUHQSLDPXNGOKMIEBFZCWVJAT', C: 'FVPJIAOYEDRZXWGCTKUQSBNMHL' };
const ROTN = ['I', 'II', 'III', 'IV', 'V'];

const enc = s => Array.from(s.toUpperCase().replace(/[^A-Z]/g, ''), c => c.charCodeAt(0) - 65);
const dec = a => Array.from(a, x => A[x]).join('');
const mod = x => ((x % 26) + 26) % 26;

function rotor(name) {
  const f = enc(ROT[name][0]); const b = new Array(26);
  f.forEach((y, x) => { b[y] = x; });
  return { f, b, notch: ROT[name][1].charCodeAt(0) - 65 };
}

// scrambler (no plugboard) at core offsets l,m,r (core = window - ring)
function makeScr(names, refName) {
  const [L, M, R] = names.map(rotor); const rf = enc(REF[refName]);
  return function (x, l, m, r) {
    x = mod(R.f[mod(x + r)] - r);
    x = mod(M.f[mod(x + m)] - m);
    x = mod(L.f[mod(x + l)] - l);
    x = rf[x];
    x = mod(L.b[mod(x + l)] - l);
    x = mod(M.b[mod(x + m)] - m);
    x = mod(R.b[mod(x + r)] - r);
    return x;
  };
}

// full table: idx ((l*26+m)*26+r)*26 + x
function makeTable(names, refName) {
  const s = makeScr(names, refName); const T = new Uint8Array(17576 * 26);
  for (let l = 0; l < 26; l++) for (let m = 0; m < 26; m++) for (let r = 0; r < 26; r++) {
    const base = ((l * 26 + m) * 26 + r) * 26;
    for (let x = 0; x < 26; x++) T[base + x] = s(x, l, m, r);
  }
  return T;
}

function plugArr(pairs) { // pairs: 'AV BS' or array of [a,b]
  const P = Array.from({ length: 26 }, (_, i) => i);
  const list = typeof pairs === 'string' ? pairs.trim().split(/\s+/).filter(Boolean).map(p => enc(p)) : pairs;
  for (const [a, b] of list) { P[a] = b; P[b] = a; }
  return P;
}

// real machine with window positions and rings (letters or numbers 0..25). Returns {out, windows}
function machine(names, refName, rings, pos, plugs, text) {
  const rs = typeof rings === 'string' ? enc(rings) : rings;
  const w = typeof pos === 'string' ? enc(pos) : pos.slice();
  const rots = names.map(rotor); const s = makeScr(names, refName); const P = plugArr(plugs || []);
  const inp = typeof text === 'string' ? enc(text) : text; const out = []; const wins = [];
  for (const c of inp) {
    if (w[1] === rots[1].notch) { w[0] = mod(w[0] + 1); w[1] = mod(w[1] + 1); }
    else if (w[2] === rots[2].notch) { w[1] = mod(w[1] + 1); }
    w[2] = mod(w[2] + 1);
    wins.push(dec(w));
    out.push(P[s(P[c], mod(w[0] - rs[0]), mod(w[1] - rs[1]), mod(w[2] - rs[2]))]);
  }
  return { out, str: dec(out), windows: wins, final: dec(w) };
}

const WHEEL_ORDERS = [];
for (const a of ROTN) for (const b of ROTN) for (const c of ROTN) if (a !== b && b !== c && a !== c) WHEEL_ORDERS.push([a, b, c]);

module.exports = { A, ROT, REF, ROTN, enc, dec, mod, rotor, makeScr, makeTable, plugArr, machine, WHEEL_ORDERS };

if (require.main === module) {
  const t1 = machine(['I', 'II', 'III'], 'B', 'AAA', 'AAA', '', 'AAAAA').str;
  const t2 = machine(['I', 'II', 'III'], 'B', 'AAA', 'ADU', '', 'AAAA').windows.join(',');
  console.log('AAAAA ->', t1, t1 === 'BDZGO' ? 'OK' : 'FAIL');
  console.log('double step ADU ->', t2, t2 === 'ADV,AEW,BFX,BFY' ? 'OK' : 'FAIL');
  const T = makeTable(['I', 'II', 'III'], 'B'); let inv = true;
  for (let i = 0; i < 17576; i++) for (let x = 0; x < 26; x++) { const y = T[i * 26 + x]; if (y === x || T[i * 26 + y] !== x) inv = false; }
  console.log('table involution & no fixed points:', inv ? 'OK' : 'FAIL');
  const pt = 'DASISTEINTESTXROSENOWXROSENOW';
  const c = machine(['II', 'IV', 'V'], 'C', 'BUL', 'QWE', 'AV BS CG DL', pt).str;
  const back = machine(['II', 'IV', 'V'], 'C', 'BUL', 'QWE', 'AV BS CG DL', c).str;
  console.log('reciprocity:', back === pt ? 'OK' : 'FAIL', c);
}
