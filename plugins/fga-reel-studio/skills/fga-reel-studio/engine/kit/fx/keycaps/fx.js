// keycaps (layer: top), for "I know nothing about editing", complexity, overwhelm.
//   each wave   on its spoken word a handful of editing-shortcut keycaps (J K L, the blade, ripple delete...) land
//               from above the frame with real gravity (constant acceleration), each on the highest thing under it,
//               so they heap into a real pile on the speaker's head, and bounce once
//   BROOM_ON    a push broom sweeps left to right and flings every key off as its edge reaches it, gone by B
// Supply: nothing, it is all type and tokens. Measure FLOOR on a still of your shot: the line the pile rests on
// (about the eyebrows, so the pile buries the top of the head). The pile rises about 3 key rows above it with 16
// keys: keep it under y 220 with fewer keys or a lower FLOOR. Every key is placed by a seeded random, so the same
// constants always give the same pile.
// Change only these constants. A cue word finds the first matching spoken word at or after the previous beat
// (wordAt); when it is missing, its fallback in T (s after A) is used.

var WAVES = ['know', 'nothing', 'about', 'editing'];   // the spoken word each wave of keys lands on, one row of KEYS each
var KEYS = [                                            // [legend, what it does, width in key units, dark?]
  [['J', 'REVERSE', 1, 0], ['K', 'STOP', 1, 0], ['L', 'PLAY', 1, 0], ['⌘K', 'ADD EDIT', 1.5, 0]],
  [['B', 'BLADE', 1, 0], ['⌘Z', 'UNDO', 1.5, 0], ['⇧', 'SHIFT', 1, 1], ['space', 'PLAY', 2.6, 0]],
  [['⇧⌘D', 'AUDIO XFADE', 2, 0], ['Q', 'RIPPLE', 1, 0], ['⌘', 'COMMAND', 1.5, 1], ['R', 'RATE', 1, 0]],
  [['⌘D', 'TRANSITION', 1.5, 0], ['W', 'RIPPLE', 1, 0], ['⇧⌫', 'RIPPLE DEL', 2, 1], ['=', 'ZOOM IN', 1, 0]]
];
var BROOM_ON = '';                                      // the broom sweeps on this word; '' = T.broom before B
var FLOOR = 690;                                        // frame px: the line the pile rests on (measured on the shot)
var CENTER_X = 540;                                     // the pile heaps around this x (the head)
var SPREAD = 470;                                       // how far either side of CENTER_X a key may land
var T = { waves: [0.40, 0.70, 1.00, 1.30], broom: 0.26 };   // fallbacks (s after A); broom: s before B

var R = '#{{ID}} ', U = 128, H = 120, G = 16000, SWEEP = 0.18;   // key unit and height (px), gravity (px/s2), broom pass (s)
var BX0 = -320, BX1 = 1420, BEDGE = 300;                // broom x from / to; its leading edge sits 300px into the svg
function rnd(i) { var x = Math.sin(i * 12.9898 + 4.1) * 43758.5453; return x - Math.floor(x); }
function word(w, after, fallback) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? fallback : t; }

// ---- wave times, each on its word
var WT = [], prev = A;
WAVES.forEach(function (w, i) {
  var t = word(w, prev, A + (T.waves[i] !== undefined ? T.waves[i] : T.waves[T.waves.length - 1] + 0.3 * i));
  WT.push(t); prev = t + 0.01;
});
var TB = Math.min(B - 0.20, Math.max(prev + 0.1, BROOM_ON ? word(BROOM_ON, prev, B - T.broom) : B - T.broom));

// ---- the pile: each key lands on the highest thing under it (a heightmap); of a few seeded spots, the lowest wins,
// so the heap settles wide like a real one
var hm = [], keys = [], n = 0;
for (var x = 0; x < 1080; x++) hm.push(FLOOR);
KEYS.forEach(function (row, wi) {
  if (wi >= WT.length) return;
  row.forEach(function (k, ki) {
    var w = Math.round(k[2] * U), best = null;
    for (var j = 0; j < 6; j++) {
      var c = CENTER_X + (rnd(n * 3 + j * 101 + 1) - 0.5) * 2 * SPREAD;
      var xc = Math.round(Math.max(40, Math.min(1040 - w, c - w / 2))), lo = Infinity;
      for (var xx = xc + 6; xx < xc + w - 6; xx++) lo = Math.min(lo, hm[xx]);
      if (best === null || lo > best[1] + 1) best = [xc, lo];
    }
    var kx = best[0], yl = best[1] - H + 4;               // rests on the highest thing under it (a hair of overlap reads as contact)
    for (var xx2 = Math.max(0, kx - 4); xx2 < Math.min(1080, kx + w + 4); xx2++) hm[xx2] = Math.min(hm[xx2], yl + 8);
    var land = WT[wi] + ki * 0.022 + rnd(n * 7 + 3) * 0.015;  // each key LANDS on its word, a frame or so apart
    var y0 = -H - 30 - rnd(n * 11 + 5) * 160, tf = Math.sqrt(2 * (yl - y0) / G), t0 = land - tf;
    if (t0 < A) { t0 = A; tf = land - A; y0 = yl - 0.5 * G * tf * tf; }   // too early for a full fall: a shorter drop
    var rot = (rnd(n * 5 + 7) - 0.5) * 16;
    keys.push({ n: n, k: k, w: w, x: kx, yl: yl, y0: y0, rot: rot, r0: rot + (rnd(n * 13 + 9) - 0.5) * 30, t0: t0, tf: tf });
    n++;
  });
});

// ---- build the keys
(function () {
  var box = document.querySelector(R + '.kc-keys');
  if (box.childNodes.length) return;
  keys.forEach(function (k) {
    var d = document.createElement('div');
    d.className = 'kc-k kc-k' + k.n + (k.k[3] ? ' kc-d' : '');
    d.setAttribute('data-layout-allow-overlap', '');
    d.style.left = k.x + 'px';
    d.style.width = k.w + 'px';
    d.innerHTML = '<div class="kc-f"><b' + (k.k[0].length > 2 ? ' class="kc-s"' : '') + ' data-layout-allow-overlap></b><i data-layout-allow-overlap></i></div>';
    d.querySelector('b').textContent = k.k[0];
    d.querySelector('i').textContent = k.k[1];
    box.appendChild(d);
  });
})();
gsap.set(R + '.kc-k', { opacity: 0 });
gsap.set(R + '.kc-broom', { x: BX0, y: FLOOR - 740 });

// fall (power2.in from rest is exactly constant acceleration), one bounce, then the broom flings it off
keys.forEach(function (k) {
  var s = R + '.kc-k' + k.n, tland = k.t0 + k.tf, b = 10 + rnd(k.n * 17 + 2) * 14;
  tl.set(s, { opacity: 1 }, q(k.t0));
  tl.fromTo(s, { y: k.y0, rotation: k.r0 }, { y: k.yl, rotation: k.rot, duration: k.tf, ease: 'power2.in', immediateRender: false }, q(k.t0));
  tl.to(s, { keyframes: [{ y: k.yl - b, duration: 0.06, ease: 'power2.out' }, { y: k.yl, duration: 0.07, ease: 'power2.in' }] }, q(tland));
  var th = Math.max(TB + SWEEP * (k.x - (BX0 + BEDGE)) / (BX1 - BX0), tland + 0.06);
  tl.to(s, { x: 1160 - k.x + rnd(k.n * 19 + 1) * 160, y: k.yl - 60 - rnd(k.n * 23 + 4) * 220,
    rotation: k.rot + 50 + rnd(k.n * 29) * 90, duration: Math.max(0.08, Math.min(0.2, B - th - 0.02)), ease: 'power2.out' }, q(th));   // off frame by B
});
tl.to(R + '.kc-broom', { x: BX1, duration: SWEEP, ease: 'none' }, q(TB));
