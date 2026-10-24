'use strict';
// Error-tolerant bombe: like bombe.js, but accepts a stop if the crib menu is consistent after dropping
// at most ONE crib edge (one garbled letter in the crib or in the ciphertext under it).
// Positions with exactly one self-encipherment conflict are tested with that edge forcibly dropped.
// Usage: node bombe_tol.js --cipher X --cribs ROSENOWROSENOW --out stops_tol.jsonl [--refs B] [--workers 12]
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');
const fs = require('fs');
const E = require('./enigma.js');

function buildMenus(C, cribStr) {
  const pt = Array.from(cribStr, ch => (ch === '.' ? -1 : ch.charCodeAt(0) - 65));
  const L = pt.length; const menus = [];
  for (let p = 0; p + L <= C.length; p++) {
    const conflicts = [];
    for (let j = 0; j < L; j++) if (pt[j] >= 0 && pt[j] === C[p + j]) conflicts.push(j);
    if (conflicts.length > 1) continue;
    const forced = conflicts.length ? conflicts[0] : -1;
    const adj = Array.from({ length: 26 }, () => []);
    for (let j = 0; j < L; j++) if (pt[j] >= 0 && j !== forced) { adj[pt[j]].push([C[p + j], j]); adj[C[p + j]].push([pt[j], j]); }
    let T = 0; for (let x = 0; x < 26; x++) if (adj[x].length > adj[T].length) T = x;
    const start = new Int32Array(27); const nb = []; const jj = [];
    for (let x = 0; x < 26; x++) { start[x] = nb.length; for (const [y, j] of adj[x]) { nb.push(y); jj.push(j); } }
    start[26] = nb.length;
    const comp = new Int32Array(26).fill(-1); const reps = []; let nc = 0;
    const order = Array.from({ length: 26 }, (_, i) => i).sort((a, b) => adj[b].length - adj[a].length);
    for (const s of order) {
      if (!adj[s].length || comp[s] >= 0) continue;
      const st = [s]; comp[s] = nc; let edges = 0;
      while (st.length) { const x = st.pop(); edges += adj[x].length; for (const [y] of adj[x]) if (comp[y] < 0) { comp[y] = nc; st.push(y); } }
      if (comp[T] !== nc && edges / 2 >= 2) reps.push(s);
      nc++;
    }
    menus.push({ p, T, reps, forced, start, nb: Int32Array.from(nb), jj: Int32Array.from(jj) });
  }
  return { cribStr, L, menus };
}

const stamp = new Int32Array(26), val = new Int32Array(26), q = new Int32Array(64); let gen = 0;
// hypothesis S(Tl)=a with edge 'drop' removed; returns 0 on success (state in stamp/val/gen) else bitmask of edges used (+1<<20)
function prop(mn, Tl, a, drop, off, T) {
  gen++;
  const start = mn.start, nb = mn.nb, jj = mn.jj;
  stamp[Tl] = gen; val[Tl] = a; let qh = 0, qt = 0; q[qt++] = Tl;
  if (a !== Tl) { stamp[a] = gen; val[a] = Tl; q[qt++] = a; }
  let used = 0;
  while (qh < qt) {
    const x = q[qh++]; const y = val[x];
    for (let e = start[x], ee = start[x + 1]; e < ee; e++) {
      const j = jj[e]; if (j === drop) continue;
      used |= 1 << j;
      const z = nb[e]; const w = T[off[j] + y];
      if (stamp[z] === gen) { if (val[z] !== w) return used | (1 << 20); continue; }
      if (stamp[w] === gen) return used | (1 << 20);
      stamp[z] = gen; val[z] = w; q[qt++] = z;
      if (w !== z) { stamp[w] = gen; val[w] = z; q[qt++] = w; }
    }
  }
  return 0;
}
function propP(P0, U, b, mn, drop, off, T) {
  const start = mn.start, nb = mn.nb, jj = mn.jj;
  const P = Int32Array.from(P0);
  if (P[U] >= 0 || (P[b] >= 0 && P[b] !== U)) return null;
  P[U] = b; P[b] = U; const qq = [U]; if (b !== U) qq.push(b);
  while (qq.length) {
    const x = qq.pop(); const y = P[x];
    for (let e = start[x], ee = start[x + 1]; e < ee; e++) {
      const j = jj[e]; if (j === drop) continue;
      const z = nb[e]; const w = T[off[j] + y];
      if (P[z] >= 0) { if (P[z] !== w) return null; continue; }
      if (P[w] >= 0) return null;
      P[z] = w; P[w] = z; qq.push(z); if (w !== z) qq.push(w);
    }
  }
  return P;
}
// after a successful prop(): check other components; returns {P, amb} or null
function fullCheck(mn, drop, off, T) {
  const P = new Int32Array(26).fill(-1);
  for (let x = 0; x < 26; x++) if (stamp[x] === gen) P[x] = val[x];
  let amb = 0;
  for (const U of mn.reps) {
    if (P[U] >= 0) continue;
    let cnt = 0, keep = null;
    for (let b = 0; b < 26; b++) { const R = propP(P, U, b, mn, drop, off, T); if (R) { cnt++; keep = R; } }
    if (cnt === 0) return null;
    if (cnt === 1) P.set(keep); else amb++;
  }
  return { P, amb };
}

function runJob(names, ref, C, cribs) {
  const T = E.makeTable(names, ref);
  const Lmax = Math.max(...cribs.map(c => c.L));
  const off = new Int32Array(Lmax); const stops = []; let tests = 0;
  const GCAP = +(process.env.GCAP || 30); const MM = 128; // group = (crib, menu, drop); weak groups (> GCAP stops) are discarded
  const gcnt = new Int32Array(cribs.length * MM * 17); const groups = new Map();
  const gid = (ci, mi, d) => (ci * MM + mi) * 17 + d + 1;
  const dead = (ci, mi, d) => gcnt[gid(ci, mi, d)] > GCAP;
  const emit = (ci, mi, cr, mn, l, m, r, kk, a, drop, res) => {
    const g = gid(ci, mi, drop); if (gcnt[g] > GCAP) return;
    if (++gcnt[g] > GCAP) { groups.delete(g); return; }
    const pairs = []; for (let x = 0; x < 26; x++) if (res.P[x] >= x) pairs.push(E.A[x] + E.A[res.P[x]]);
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push({ wo: names.join(','), ref, crib: cr.cribStr, p: mn.p, l, m, r, k: kk, T: E.A[mn.T], a: E.A[a], drop, pairs: pairs.join(' '), n: pairs.length, amb: res.amb });
  };
  for (let l = 0; l < 26; l++) for (let m = 0; m < 26; m++) for (let r = 0; r < 26; r++) {
    for (let kk = 0; kk < Lmax; kk++) {
      for (let j = 0; j < Lmax; j++) { const mm = (kk > 0 && j >= kk) ? (m + 1) % 26 : m; off[j] = ((l * 26 + mm) * 26 + (r + j) % 26) * 26; }
      for (let ci = 0; ci < cribs.length; ci++) {
        const cr = cribs[ci]; if (kk >= cr.L) continue;
        for (let mi = 0; mi < cr.menus.length; mi++) {
          const mn = cr.menus[mi];
          tests++; const Tl = mn.T;
          if (mn.forced >= 0 && dead(ci, mi, mn.forced)) continue;
          for (let a = 0; a < 26; a++) {
            if (mn.forced >= 0) { // one edge already dropped (self-encipherment conflict): exact test only
              if (prop(mn, Tl, a, -1, off, T) === 0) { const res = fullCheck(mn, -1, off, T); if (res) emit(ci, mi, cr, mn, l, m, r, kk, a, mn.forced, res); }
              continue;
            }
            const u = prop(mn, Tl, a, -1, off, T);
            if (u === 0) {
              const res = fullCheck(mn, -1, off, T);
              if (res) { emit(ci, mi, cr, mn, l, m, r, kk, a, -1, res); continue; }
              for (let d = 0; d < cr.L; d++) { // failure in another component: try each drop
                if (dead(ci, mi, d)) continue;
                if (prop(mn, Tl, a, d, off, T) !== 0) continue;
                const r2 = fullCheck(mn, d, off, T); if (r2) { emit(ci, mi, cr, mn, l, m, r, kk, a, d, r2); break; }
              }
              continue;
            }
            const mask = u & 0xFFFFF;
            for (let d = 0; d < cr.L; d++) {
              if (!(mask & (1 << d)) || dead(ci, mi, d)) continue;
              if (prop(mn, Tl, a, d, off, T) !== 0) continue;
              const r2 = fullCheck(mn, d, off, T); if (r2) emit(ci, mi, cr, mn, l, m, r, kk, a, d, r2);
            }
          }
        }
      }
    }
  }
  let deadN = 0; for (let g = 0; g < gcnt.length; g++) if (gcnt[g] > GCAP) deadN++;
  for (const arr of groups.values()) stops.push(...arr);
  return { stops, tests, deadN };
}

if (isMainThread) {
  const args = {}; const av = process.argv.slice(2);
  for (let i = 0; i < av.length; i += 2) args[av[i].replace(/^--/, '')] = av[i + 1];
  const C = E.enc(args.cipher);
  const cribStrs = args.cribs.split(',');
  const refs = (args.refs || 'B,C').split(',');
  const wos = args.wo ? args.wo.split(';').map(s => s.split(',')) : E.WHEEL_ORDERS;
  const jobs = []; for (const ref of refs) for (const wo of wos) jobs.push([wo, ref]);
  const nW = Math.min(+(args.workers || 12), jobs.length);
  const out = fs.createWriteStream(args.out);
  const t0 = Date.now(); let done = 0, nStops = 0, totalTests = 0;
  const cribInfo = cribStrs.map(s => buildMenus(C, s));
  console.log('cribs:', cribInfo.map(c => `${c.cribStr} L=${c.L} positions=${c.menus.length} (forced-drop ${c.menus.filter(m => m.forced >= 0).length})`).join(' | '));
  let next = 0;
  for (let w = 0; w < nW; w++) {
    const wk = new Worker(__filename, { workerData: { C, cribStrs } });
    const feed = () => { if (next < jobs.length) wk.postMessage(jobs[next++]); else wk.postMessage(null); };
    wk.on('message', msg => {
      done++; nStops += msg.stops.length; totalTests += msg.tests;
      for (const s of msg.stops) out.write(JSON.stringify(s) + '\n');
      const line = `[${((Date.now() - t0) / 1000).toFixed(0)}s] ${done}/${jobs.length} ${msg.job} stops=${msg.stops.length} deadGroups=${msg.deadN} total=${nStops}`;
      console.log(line); fs.appendFileSync(args.out + '.progress', line + '\n');
      feed();
    });
    wk.on('exit', () => { if (done === jobs.length && !out.closed) { out.end(); console.log('DONE total stops', nStops, 'tests', totalTests, 'secs', (Date.now() - t0) / 1000); } });
    feed();
  }
} else {
  const { C, cribStrs } = workerData;
  const cribs = cribStrs.map(s => buildMenus(C, s));
  parentPort.on('message', job => {
    if (!job) { process.exit(0); }
    const [names, ref] = job;
    const { stops, tests, deadN } = runJob(names, ref, C, cribs);
    parentPort.postMessage({ job: names.join(',') + '/' + ref, stops, tests, deadN });
  });
}
