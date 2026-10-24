'use strict';
// For the top-N distinct stage-2 candidates, run the GTA/KCI indicator check (all 17,576 ring settings).
// Usage: node check_top.js cands.jsonl CIPHER [N]
const fs = require('fs'); const { execFileSync } = require('child_process');
const [file, cipher, N] = process.argv.slice(2);
const cands = fs.readFileSync(file, 'utf8').trim().split('\n').map(JSON.parse);
const seen = new Set(); const top = [];
for (const c of cands) { const k = c.wo + c.ref + c.plugs + c.core0 + c.s0 + c.dbl; if (seen.has(k)) continue; seen.add(k); top.push(c); if (top.length >= +(N || 5)) break; }
for (const c of top) {
  console.log(`== ${c.spl} ${c.wo} ${c.ref} [${c.plugs}] core0=${c.core0} s0=${c.s0} dbl=${c.dbl}\n   ${c.pt}`);
  const out = execFileSync('node', ['verify_indicator.js', '--wo', c.wo, '--ref', c.ref, '--plugs', c.plugs, '--ground', 'GTA', '--enckey', 'KCI', '--cipher', cipher, '--pt', c.pt, '--top', '3'], { cwd: __dirname }).toString();
  console.log(out.split('\n').map(l => '   ' + l).join('\n'));
}
