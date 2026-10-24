'use strict';
// Bombe-style crib search. For every wheel order x reflector x rotor core state at the crib start
// x index of the middle-rotor step inside the crib window, test every crib position with a
// plugboard-consistency (diagonal-board style) propagation from the most-connected menu letter.
// Usage: node bombe.js --cipher X --cribs ROSENOWROSENOW,ROSENOWXROSENOW --out stops.jsonl [--refs B,C] [--workers 12] [--wo I,II,III;...]
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');
const fs = require('fs');
const E = require('./enigma.js');

function buildMenus(C, cribStr) {
  const pt = Array.from(cribStr, ch => (ch === '.' ? -1 : ch.charCodeAt(0) - 65));
  const L = pt.length; const menus = [];
  for (let p = 0; p + L <= C.length; p++) {
    let ok = true;
    for (let j = 0; j < L; j++) if (pt[j] >= 0 && pt[j] === C[p + j]) { ok = false; break; }
    if (!ok) continue;
    const adj = Array.from({ length: 26 }, () => []);
    for (let j = 0; j < L; j++) if (pt[j] >= 0) { adj[pt[j]].push([C[p + j], j]); adj[C[p + j]].push([pt[j], j]); }
    let T = 0; for (let x = 0; x < 26; x++) if (adj[x].length > adj[T].length) T = x;
    const start = new Int32Array(27); const nb = []; const jj = [];
    for (let x = 0; x < 26; x++) { start[x] = nb.length; for (const [y, j] of adj[x]) { nb.push(y); jj.push(j); } }
    start[26] = nb.length;
    // other connected components (by menu graph), represented by their most-connected letter
    const comp = new Int32Array(26).fill(-1); const reps = []; let nc = 0;
    const order = Array.from({ length: 26 }, (_, i) => i).sort((a, b) => adj[b].length - adj[a].length);
    for (const s of order) {
      if (!adj[s].length || comp[s] >= 0) continue;
      const st = [s]; comp[s] = nc; let edges = 0;
      while (st.length) { const x = st.pop(); edges += adj[x].length; for (const [y] of adj[x]) if (comp[y] < 0) { comp[y] = nc; st.push(y); } }
      if (comp[T] !== nc && edges / 2 >= 2) reps.push(s);
      nc++;
    }
    menus.push({ p, T, reps, start, nb: Int32Array.from(nb), jj: Int32Array.from(jj) });
  }
  return { cribStr, L, menus };
}

// propagate hypothesis S(U)=b on top of partial plugboard P (copy); returns new array or null
function propagate(P0, U, b, start, nb, jj, off, T) {
  const P = Int32Array.from(P0);
  if (P[U] >= 0 || (P[b] >= 0 && P[b] !== U)) return null;
  P[U] = b; P[b] = U; const q = [U]; if (b !== U) q.push(b);
  while (q.length) {
    const x = q.pop(); const y = P[x];
    for (let e = start[x], ee = start[x + 1]; e < ee; e++) {
      const z = nb[e]; const w = T[off[jj[e]] + y];
      if (P[z] >= 0) { if (P[z] !== w) return null; continue; }
      if (P[w] >= 0) return null;
      P[z] = w; P[w] = z; q.push(z); if (w !== z) q.push(w);
    }
  }
  return P;
}

function runJob(names, ref, C, cribs) {
  const T = E.makeTable(names, ref);
  const Lmax = Math.max(...cribs.map(c => c.L));
  const off = new Int32Array(Lmax);
  const stamp = new Int32Array(26); const val = new Int32Array(26); const q = new Int32Array(64);
  let gen = 0; const stops = []; let tests = 0;
  for (let l = 0; l < 26; l++) for (let m = 0; m < 26; m++) for (let r = 0; r < 26; r++) {
    for (let kk = 0; kk < Lmax; kk++) { // kk=0: no middle step inside window; kk>=1: middle steps at window index kk
      for (let j = 0; j < Lmax; j++) {
        const mm = (kk > 0 && j >= kk) ? (m + 1) % 26 : m;
        off[j] = ((l * 26 + mm) * 26 + (r + j) % 26) * 26;
      }
      for (let ci = 0; ci < cribs.length; ci++) {
        const cr = cribs[ci]; if (kk >= cr.L) continue;
        const menus = cr.menus;
        for (let mi = 0; mi < menus.length; mi++) {
          const mn = menus[mi]; const start = mn.start, nb = mn.nb, jj = mn.jj, Tl = mn.T;
          tests++;
          for (let a = 0; a < 26; a++) {
            gen++;
            // assign(Tl, a)
            stamp[Tl] = gen; val[Tl] = a; let qh = 0, qt = 0; q[qt++] = Tl;
            if (a !== Tl) { stamp[a] = gen; val[a] = Tl; q[qt++] = a; }
            let bad = false;
            while (qh < qt && !bad) {
              const x = q[qh++]; const y = val[x];
              for (let e = start[x], ee = start[x + 1]; e < ee; e++) {
                const z = nb[e]; const w = T[off[jj[e]] + y];
                if (stamp[z] === gen) { if (val[z] !== w) { bad = true; break; } continue; }
                if (stamp[w] === gen) { bad = true; break; } // w already paired with something else
                stamp[z] = gen; val[z] = w; q[qt++] = z;
                if (w !== z) { stamp[w] = gen; val[w] = z; q[qt++] = w; }
              }
            }
            if (!bad) {
              // full-menu check: every other component (>=2 edges) must have a consistent hypothesis
              const P = new Int32Array(26).fill(-1);
              for (let x = 0; x < 26; x++) if (stamp[x] === gen) P[x] = val[x];
              let amb = 0, reject = false;
              for (const U of mn.reps) {
                if (P[U] >= 0) continue;
                let cnt = 0, keep = null;
                for (let b = 0; b < 26; b++) {
                  const R = propagate(P, U, b, start, nb, jj, off, T);
                  if (R) { cnt++; keep = R; }
                }
                if (cnt === 0) { reject = true; break; }
                if (cnt === 1) P.set(keep); else amb++;
              }
              if (reject) continue;
              const pairs = [];
              for (let x = 0; x < 26; x++) if (P[x] >= x) pairs.push(E.A[x] + E.A[P[x]]);
              stops.push({ wo: names.join(','), ref, crib: cr.cribStr, p: mn.p, l, m, r, k: kk, T: E.A[Tl], a: E.A[a], pairs: pairs.join(' '), n: pairs.length, amb });
            }
          }
        }
      }
    }
  }
  return { stops, tests };
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
  console.log('cribs:', cribInfo.map(c => `${c.cribStr} L=${c.L} positions=${c.menus.length}`).join(' | '));
  let next = 0;
  for (let w = 0; w < nW; w++) {
    const wk = new Worker(__filename, { workerData: { C, cribStrs } });
    const feed = () => { if (next < jobs.length) wk.postMessage(jobs[next++]); else wk.postMessage(null); };
    wk.on('message', msg => {
      done++; nStops += msg.stops.length; totalTests += msg.tests;
      for (const s of msg.stops) out.write(JSON.stringify(s) + '\n');
      const line = `[${((Date.now() - t0) / 1000).toFixed(0)}s] ${done}/${jobs.length} ${msg.job} stops=${msg.stops.length} total=${nStops}`;
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
    const { stops, tests } = runJob(names, ref, C, cribs);
    parentPort.postMessage({ job: names.join(',') + '/' + ref, stops, tests });
  });
}
