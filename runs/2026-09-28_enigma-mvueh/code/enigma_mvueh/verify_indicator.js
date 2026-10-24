'use strict';
// Indicator check: for all ring settings, decrypt the enciphered message key at the clear ground setting,
// then decrypt the whole message on a real (window/ring/notch) machine and compare with the candidate plaintext.
// Usage: node verify_indicator.js --wo II,IV,V --ref B --plugs "AB CD" --ground GTA --enckey KCI --cipher X --pt Y
const E = require('./enigma.js');
const args = {}; const av = process.argv.slice(2);
for (let i = 0; i < av.length; i += 2) args[av[i].replace(/^--/, '')] = av[i + 1];
const wo = args.wo.split(','); const C = E.enc(args.cipher); const PT = E.enc(args.pt);
const T = E.makeTable(wo, args.ref); const P = E.plugArr(args.plugs || '');
const notch = wo.map(n => E.rotor(n).notch);
function run(rings, pos, inp) {
  const w = pos.slice(); const out = new Array(inp.length);
  for (let i = 0; i < inp.length; i++) {
    if (w[1] === notch[1]) { w[0] = (w[0] + 1) % 26; w[1] = (w[1] + 1) % 26; }
    else if (w[2] === notch[2]) w[1] = (w[1] + 1) % 26;
    w[2] = (w[2] + 1) % 26;
    const l = E.mod(w[0] - rings[0]), m = E.mod(w[1] - rings[1]), r = E.mod(w[2] - rings[2]);
    out[i] = P[T[((l * 26 + m) * 26 + r) * 26 + P[inp[i]]]];
  }
  return out;
}
const G = E.enc(args.ground || 'GTA'), K = E.enc(args.enckey || 'KCI');
const res = [];
for (let a = 0; a < 26; a++) for (let b = 0; b < 26; b++) for (let c = 0; c < 26; c++) {
  const R = [a, b, c]; const M = run(R, G, K); const pt = run(R, M, C);
  let match = 0; for (let i = 0; i < C.length; i++) if (pt[i] === PT[i]) match++;
  res.push({ rings: E.dec(R), ringsNum: R.map(x => String(x + 1).padStart(2, '0')).join(' '), key: E.dec(M), match, pt: E.dec(pt) });
}
res.sort((x, y) => y.match - x.match);
console.log('best ring settings by agreement with candidate plaintext (' + C.length + ' letters):');
for (const r of res.slice(0, +(args.top || 8))) console.log(r.match, 'rings', r.rings, '(' + r.ringsNum + ')', 'msgkey', r.key, r.pt);
const hist = {}; for (const r of res) hist[r.match] = (hist[r.match] || 0) + 1;
console.log('match-count histogram (top 10 levels):', Object.entries(hist).sort((x, y) => y[0] - x[0]).slice(0, 10).map(([k, v]) => k + ':' + v).join(' '));
