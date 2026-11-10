// knockout-captions (layer: over, above everything; the effect carries the words). The captions come in huge:
//   grow      each word (or pair) arrives as the creator's caption box on its spoken word, from 0.55x with a
//             back.out, each box bigger than the last (SIZES), and the stack pushes up so the newest box always
//             sits on the caption band
//   slam      on the key word the boxes cut away, the frame goes to the light ground and the giant word slams down
//             from 2.6x to fill it (power4.out), cut out of the plate so the live footage plays through the letters
//   hold      the plate keeps growing a hair (1 to 1.035) until the hard out on B
// Reach for it on "the captions come in huge", "bigger captions", a payoff word (the giant-captions alternative).
// Give the window a KARAOKE hide (edit.py: KARAOKE = dict(hide=[(start, end)])) so the normal captions step aside.
// Supply: nothing but the words. The knockout is live: an SVG mask with the word set in the pack's display face,
// fitted to the frame, so nothing is generated and it follows the pack.
// Change only these constants:
var TILES = [['The', 'The'], ['captions', 'captions'], ['come', 'come'], ['in', 'in']];   // [box text, the spoken word it lands on]
var ROWS = ['HU', 'GE'];                    // the giant word, row by row (one row for a short word: ['YES'])
var KEY = 'huge';                           // the spoken word the plate slams on
var SIZES = [66, 104, 164, 260];            // px per box, in order (more boxes than sizes keep growing 1.5x)
var AT = { tiles: [0.10, 0.38, 0.66, 0.94], key: 1.22 };   // fallbacks (s after A) when a word isn't found
var LEAD = 0.02;                            // the plate slams this far ahead of its word
var BOTTOM = 1462;                          // the newest box sits with its foot on this y
var TRACK = -0.01;                          // the giant word's tracking (em)
var CENTER_Y = 850;                         // the giant word centres on this y; it fills MAXW wide or y 240-1460
var MAXW = 960;                             // px: the widest row's ink; with the 1.035 grow it keeps 35px+ from both frame edges

function $(s) { return document.querySelector(s); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

// ---- the boxes: sizes, heights and where each one sits in the stack
var st = $('#{{ID}}-st'), tops = [], hs = [], y = 0;
TILES.forEach(function (w, i) {
  var s = SIZES[i] !== undefined ? SIZES[i] : SIZES[SIZES.length - 1] * Math.pow(1.5, i - SIZES.length + 1);
  var pt = Math.round(s * 0.06), pb = Math.round(s * 0.135), h = Math.round(s * 1.08) + pt + pb;
  var row = document.createElement('div'), k = document.createElement('div');
  row.className = '{{ID}}-row';
  row.style.top = y + 'px';
  k.className = '{{ID}}-k';
  k.id = '{{ID}}-k' + i;
  k.textContent = w[0];
  k.style.fontSize = s + 'px';
  k.style.height = h + 'px';
  k.style.padding = pt + 'px ' + Math.round(s * 0.3) + 'px ' + pb + 'px';
  k.style.lineHeight = Math.round(s * 1.08) + 'px';
  k.setAttribute('data-layout-allow-overlap', '');
  k.setAttribute('data-layout-allow-overflow', '');
  row.appendChild(k);
  st.appendChild(row);
  tops.push(y); hs.push(h);
  y += h + 12;
});

// ---- the giant word: one <text> per row in the mask, fitted to the frame with the pack's display face
var word = $('#{{ID}}-word'), NS = 'http://www.w3.org/2000/svg', texts = [];
ROWS.forEach(function (r) {
  var t = document.createElementNS(NS, 'text');
  t.setAttribute('class', '{{ID}}-cut');
  t.setAttribute('x', '540');
  t.setAttribute('text-anchor', 'middle');
  t.textContent = r;
  word.appendChild(t);
  texts.push(t);
});
var fitted = { cy: CENTER_Y };
function fit() {
  var c = document.createElement('canvas').getContext('2d');
  var font = function (px) { return tok('--display-style') + ' ' + tok('--display-weight') + ' ' + px + 'px ' + tok('--font-display'); };
  c.font = font(200);
  var maxw = 1, cap = 1, shift = [];        // ink widths (an italic overhangs its advance) and how far to move each
  ROWS.forEach(function (r) {                // row so its ink, not its advance, centres on x 540
    var m = c.measureText(r), tr = TRACK * 200 * (r.length - 1);
    var L = m.actualBoundingBoxLeft || 0, R = m.actualBoundingBoxRight || m.width;
    maxw = Math.max(maxw, L + R + tr);
    shift.push((m.width + tr) / 2 - (R - L + tr) / 2);
    cap = Math.max(cap, m.actualBoundingBoxAscent || 145);
  });
  var n = ROWS.length, GAP = 0.09;          // row gap, in em
  var size = Math.min(MAXW * 200 / maxw, 1220 / (n * cap / 200 + (n - 1) * GAP));
  var capS = cap * size / 200, gap = GAP * size, top = CENTER_Y - (n * capS + (n - 1) * gap) / 2;
  texts.forEach(function (t, i) {
    t.setAttribute('font-size', size.toFixed(1));
    t.setAttribute('x', (540 + shift[i] * size / 200).toFixed(1));
    t.setAttribute('letter-spacing', (TRACK * size).toFixed(1));
    t.setAttribute('y', (top + capS * (i + 1) + gap * i).toFixed(1));
  });
}
fit();
if (document.fonts && document.fonts.load) {
  document.fonts.load(tok('--display-style') + ' ' + tok('--display-weight') + ' 100px ' + tok('--font-display'), ROWS.join('')).then(fit, fit);
  document.fonts.ready.then(fit);
}

// ---- times: each box on its word, searched in order from A; the slam on KEY
function find(w, after, fb) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }
var T = [], prev = A;
TILES.forEach(function (w, i) {
  prev = find(w[1], prev, AT.tiles[i] !== undefined ? AT.tiles[i] : AT.tiles[AT.tiles.length - 1] + 0.28 * (i - AT.tiles.length + 1));
  T.push(prev);
});
var TH = Math.max(A, find(KEY, prev, AT.key) - LEAD);

// ---- motion
function off_(i) { return BOTTOM - (tops[i] + hs[i]); }   // the stack's y with box i as the newest
gsap.set('#{{ID}} .{{ID}}-k', { opacity: 0 });
gsap.set('#{{ID}}-st', { y: off_(0) });
gsap.set('#{{ID}}-plate', { opacity: 0, transformOrigin: '540px ' + CENTER_Y + 'px' });
TILES.forEach(function (w, i) {
  tl.set('#{{ID}}-k' + i, { opacity: 1 }, q(T[i]));
  tl.fromTo('#{{ID}}-k' + i, { scale: 0.55 }, { scale: 1, duration: 0.24, ease: 'back.out(1.7)', immediateRender: false }, q(T[i]));
  if (i > 0) tl.fromTo('#{{ID}}-st', { y: off_(i - 1) }, { y: off_(i), duration: 0.22, ease: 'power3.out', immediateRender: false }, q(T[i]));
});
// the key word: the boxes cut away, the light plate slams down with the word cut out of it
off('#{{ID}}-st', TH);
on('#{{ID}}-plate', TH);
tl.fromTo('#{{ID}}-plate', { scale: 2.6 }, { scale: 1, duration: 0.2, ease: 'power4.out', immediateRender: false }, q(TH));
if (B - TH - 0.2 > 0.05) {
  tl.fromTo('#{{ID}}-plate', { scale: 1 }, { scale: 1.035, duration: B - TH - 0.2, ease: 'none', immediateRender: false }, q(TH + 0.2));
}
