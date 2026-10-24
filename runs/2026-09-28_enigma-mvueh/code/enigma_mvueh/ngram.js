'use strict';
// Interpolated trigram model over A-Z from corpus_de.txt (Enigma-style German, X = space).
const fs = require('fs');
const path = require('path');
function loadModel(file) {
  file = file || process.env.CORPUS || path.join(__dirname, 'corpus_de.txt');
  const txt = fs.readFileSync(file, 'utf8').toUpperCase().replace(/[^A-Z]/g, '');
  const c1 = new Float64Array(26), c2 = new Float64Array(676), c3 = new Float64Array(17576);
  const a = Array.from(txt, ch => ch.charCodeAt(0) - 65);
  for (let i = 0; i < a.length; i++) {
    c1[a[i]]++;
    if (i >= 1) c2[a[i - 1] * 26 + a[i]]++;
    if (i >= 2) c3[(a[i - 2] * 26 + a[i - 1]) * 26 + a[i]]++;
  }
  const N = a.length; const ctx2 = new Float64Array(676); // count of bigram as trigram context
  for (let i = 0; i < 676; i++) ctx2[i] = c2[i];
  const L3 = 0.55, L2 = 0.3, L1 = 0.15;
  const tri = new Float32Array(17576), bi = new Float32Array(676), uni = new Float32Array(26);
  for (let z = 0; z < 26; z++) uni[z] = Math.log((c1[z] + 0.5) / (N + 13));
  for (let y = 0; y < 26; y++) for (let z = 0; z < 26; z++) {
    const p2 = c1[y] ? c2[y * 26 + z] / c1[y] : 0; const p1 = (c1[z] + 0.5) / (N + 13);
    bi[y * 26 + z] = Math.log(0.75 * p2 + 0.25 * p1);
  }
  for (let x = 0; x < 26; x++) for (let y = 0; y < 26; y++) for (let z = 0; z < 26; z++) {
    const i3 = (x * 26 + y) * 26 + z;
    const p3 = ctx2[x * 26 + y] ? c3[i3] / ctx2[x * 26 + y] : 0;
    const p2 = c1[y] ? c2[y * 26 + z] / c1[y] : 0; const p1 = (c1[z] + 0.5) / (N + 13);
    tri[i3] = Math.log(L3 * p3 + L2 * p2 + L1 * p1);
  }
  return { tri, bi, uni, N };
}
function scoreArr(M, pt, n) {
  let s = M.uni[pt[0]] + M.bi[pt[0] * 26 + pt[1]];
  for (let i = 2; i < n; i++) s += M.tri[(pt[i - 2] * 26 + pt[i - 1]) * 26 + pt[i]];
  return s;
}
module.exports = { loadModel, scoreArr };
if (require.main === module) {
  const M = loadModel(); const E = require('./enigma.js');
  const t = s => { const a = E.enc(s); return (scoreArr(M, a, a.length) / a.length).toFixed(3); };
  console.log('corpus letters', M.N);
  console.log('german  ', t('AUFKLXABTEILUNGXVONXKURTINOWAXNORDWESTLXSEBEZXANGRIFFXINFXRGTXUMXDREIXUHR'));
  console.log('german2 ', t('FEINDXHATXROSENOWXROSENOWXBESETZTXEIGENEXVERLUSTEXGERING'));
  console.log('random  ', t('ICRVSORMCCWQTATYEVFXDBZGGSNXWLPSYWZYTCBSWULRTBZCVGODVJUSLSOOMJQJZSXSEB'));
}
