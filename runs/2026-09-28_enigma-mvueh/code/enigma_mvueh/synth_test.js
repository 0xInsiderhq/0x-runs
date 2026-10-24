'use strict';
// Build a synthetic 82-letter message with a known key containing ROSENOWROSENOW, to check the bombe finds it.
const E = require('./enigma.js');
const pt = 'ANXKOMMANDEURXABTXROSENOWROSENOWXFEINDXANGRIFFXUMXDREIXUHRXABGEWIESENXVERLUSTEXKEINE';
const key = { wo: ['IV', 'I', 'III'], ref: 'B', rings: 'KFS', pos: 'XUT', plugs: 'AQ BJ CW DK EZ FT GN HP IO LV' };
const c = E.machine(key.wo, key.ref, key.rings, key.pos, key.plugs, pt);
console.log(JSON.stringify({ pt, len: pt.length, ct: c.str, cribPos: pt.indexOf('ROSENOW'), windows: c.windows.slice(17, 32).join(' ') }));
// print expected core state at crib start
const p = pt.indexOf('ROSENOW'); const rs = E.enc(key.rings); const w = E.enc(c.windows[p]);
console.log('expected cores at crib start l,m,r =', w.map((x, i) => E.mod(x - rs[i])).join(','));
