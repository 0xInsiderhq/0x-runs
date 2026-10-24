'use strict';
// Stage 2: expand each bombe stop to full-message stepping hypotheses, complete the plugboard by
// hill-climbing a German trigram score (<=10 pairs), rank. Usage:
// node solve2.js --cipher X --stops stops.jsonl --out cands.jsonl [--workers 12] [--top 50] [--lock 0|1]
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');
const fs = require('fs');
const E = require('./enigma.js');
const G = require('./ngram.js');

function stepOptions(st, N) {
  const L = st.crib.length; const opts = [];
  let classes = [];
  if (st.k > 0) classes = [E.mod(st.p + st.k)];
  else { const ex = new Set(); for (let j = 1; j < L; j++) ex.add(E.mod(st.p + j)); for (let s = 0; s < 26; s++) if (!ex.has(s)) classes.push(s); }
  for (const s0 of classes) {
    opts.push({ s0, dbl: -1 });
    for (let s = 0; s <= N - 2; s++) if (E.mod(s - s0) === 0) {
      const d = s + 1; if (d > st.p && d < st.p + L) continue; // bombe assumed no left step inside crib window
      opts.push({ s0, dbl: d });
    }
  }
  return opts;
}

function coreOffsets(st, N, o) {
  const stepM = new Int8Array(N), stepL = new Int8Array(N);
  for (let i = 0; i < N; i++) if (E.mod(i - o.s0) === 0) stepM[i] = 1;
  if (o.dbl >= 0) { stepM[o.dbl] += 1; stepL[o.dbl] = 1; }
  const l = new Int32Array(N), m = new Int32Array(N), r = new Int32Array(N);
  l[st.p] = st.l; m[st.p] = st.m; r[st.p] = st.r;
  for (let i = st.p + 1; i < N; i++) { r[i] = E.mod(r[i - 1] + 1); m[i] = E.mod(m[i - 1] + stepM[i]); l[i] = E.mod(l[i - 1] + stepL[i]); }
  for (let i = st.p - 1; i >= 0; i--) { r[i] = E.mod(r[i + 1] - 1); m[i] = E.mod(m[i + 1] - stepM[i + 1]); l[i] = E.mod(l[i + 1] - stepL[i + 1]); }
  const off = new Int32Array(N);
  for (let i = 0; i < N; i++) off[i] = ((l[i] * 26 + m[i]) * 26 + r[i]) * 26;
  return { off, cores: Array.from({ length: N }, (_, i) => [l[i], m[i], r[i]]) };
}

function climb(M, T, off, C, P0, lockSet) {
  const N = C.length; const P = Int32Array.from(P0); const pt = new Int32Array(N);
  const decr = Q => { for (let i = 0; i < N; i++) pt[i] = Q[T[off[i] + Q[C[i]]]]; return G.scoreArr(M, pt, N); };
  const npairs = Q => { let n = 0; for (let x = 0; x < 26; x++) if (Q[x] > x) n++; return n; };
  let best = decr(P); let improved = true; const Q = new Int32Array(26);
  while (improved) {
    improved = false;
    for (let a = 0; a < 26; a++) for (let b = a; b < 26; b++) {
      if (lockSet[a] || lockSet[b]) continue;
      Q.set(P);
      if (a === b) { if (Q[a] === a) continue; const pa = Q[a]; Q[pa] = pa; Q[a] = a; }
      else {
        if (Q[a] === b) continue;
        if (lockSet[Q[a]] || lockSet[Q[b]]) continue;
        const pa = Q[a], pb = Q[b]; Q[pa] = pa; Q[pb] = pb; Q[a] = b; Q[b] = a;
        if (npairs(Q) > 10) continue;
      }
      const s = decr(Q);
      if (s > best + 1e-9) { best = s; P.set(Q); improved = true; }
    }
  }
  decr(P);
  return { score: best, P, pt: E.dec(pt) };
}

function plugStr(P) { const o = []; for (let x = 0; x < 26; x++) if (P[x] > x) o.push(E.A[x] + E.A[P[x]]); return o.join(' '); }

function work(stops, C, lock) {
  const M = G.loadModel(); const tables = {}; const res = [];
  for (const st of stops) {
    const key = st.wo + '/' + st.ref;
    if (!tables[key]) tables[key] = E.makeTable(st.wo.split(','), st.ref);
    const T = tables[key];
    const P0 = new Int32Array(26); for (let x = 0; x < 26; x++) P0[x] = x;
    const lockSet = new Uint8Array(26);
    for (const pr of st.pairs.split(' ').filter(Boolean)) { const a = pr.charCodeAt(0) - 65, b = pr.charCodeAt(1) - 65; P0[a] = b; P0[b] = a; if (lock) { lockSet[a] = 1; lockSet[b] = 1; } }
    // if bombe produced >10 non-self pairs it is impossible under 10-pair rule, but keep (transcription errors)
    let bestC = null;
    for (const o of stepOptions(st, C.length)) {
      const { off, cores } = coreOffsets(st, C.length, o);
      const r = climb(M, T, off, C, P0, lockSet);
      if (!bestC || r.score > bestC.score) bestC = { score: r.score, pt: r.pt, plugs: plugStr(r.P), s0: o.s0, dbl: o.dbl, core0: E.dec(cores[0]) };
    }
    res.push(Object.assign({}, st, { spl: +(bestC.score / C.length).toFixed(4), pt: bestC.pt, plugs: bestC.plugs, s0: bestC.s0, dbl: bestC.dbl, core0: bestC.core0 }));
  }
  return res;
}

if (isMainThread) {
  const args = {}; const av = process.argv.slice(2);
  for (let i = 0; i < av.length; i += 2) args[av[i].replace(/^--/, '')] = av[i + 1];
  const C = E.enc(args.cipher);
  const stops = fs.readFileSync(args.stops, 'utf8').split('\n').filter(Boolean).map(JSON.parse);
  const nW = Math.min(+(args.workers || 12), stops.length) || 1;
  const chunks = Array.from({ length: nW }, () => []);
  // group by wheel order so each worker builds few tables
  stops.sort((a, b) => (a.wo + a.ref).localeCompare(b.wo + b.ref)).forEach((s, i) => chunks[Math.floor(i * nW / stops.length)].push(s));
  const t0 = Date.now(); let fin = 0; const all = [];
  console.log('stops', stops.length, 'workers', nW);
  for (const ch of chunks) {
    const w = new Worker(__filename, { workerData: { stops: ch, C, lock: args.lock === '1' } });
    w.on('message', r => {
      all.push(...r); fin++;
      if (fin === nW) {
        all.sort((a, b) => b.spl - a.spl);
        fs.writeFileSync(args.out, all.map(x => JSON.stringify(x)).join('\n') + '\n');
        console.log('done in', (Date.now() - t0) / 1000, 's');
        for (const x of all.slice(0, +(args.top || 25))) console.log(x.spl, x.wo, x.ref, x.crib, 'p=' + x.p, 'core0=' + x.core0, 's0=' + x.s0, 'dbl=' + x.dbl, '[' + x.plugs + ']', x.pt);
      }
    });
  }
} else {
  const { stops, C, lock } = workerData;
  parentPort.postMessage(work(stops, C, lock));
}
