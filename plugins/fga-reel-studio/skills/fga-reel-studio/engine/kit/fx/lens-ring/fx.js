// lens-ring (layer: over, above everything). Two beats for a line about the shot and the captions:
//   lens      on the first cue word a lens barrel readout unfolds at the top (a dark plate, a knurled grip, a focal
//             scale drawn on a cylinder so the numerals compress as they turn away) and nudges; on the turn word the
//             ring spins from the first focal length to the last (back.out: the detent overshoots and seats), the
//             mark under the pointer turns to the accent, the plate takes a short press and folds shut
//   camera    with the spin the camera pulls out of a held zoom (HOLD to 1, expo.out): the shot gets wider on the word
//   panel     a dark panel unrolls over the caption band, a keyframe track draws across its top and the playhead runs
//   words     the next words build letter by letter on their spoken words, each letter its own move (drop, flip,
//             stretch, in turn) and an accent key drops on the track for each one; the first row in the text face,
//             the second in the display face in the accent; the last row takes a beat of weight
//   out       the letters sink, the panel rolls up and the track retracts, gone by B
// Reach for it on "wider shot", "animated captions", "zoom out", any line that names a lens or a caption style.
// edit.py: a CAMERA zoom that holds HOLD from the window start to the turn word, e.g.
//   CAMERA = dict(..., zooms=[(<A>, <turn word onset>, 1.35)])
// (this effect pulls it back to 1 on the word; HOLD = 1 leaves the camera alone), and a KARAOKE hide from the first
// panel word to B so the captions step aside under the panel. Supply: the focal lengths and the words.
// Change only these constants:
var MARKS = [85, 70, 50, 35, 24];           // the focal scale, from where the ring starts to where it lands (mm)
var OPEN = 'Wider';                         // the spoken word the readout opens on
var TURN = 'shot';                          // the spoken word the ring spins (and the camera pulls out) on
var ROWS = [['animated', 'animated', 'text'], ['captions.', 'captions', 'display']];   // [text, spoken word, face]
var ROW_Y = [1140, 1282];                   // the top of each row in the panel
var ROW_SIZE = [128, 156];                  // px per row (fitted down to 780px wide with the pack's faces)
var HOLD = 1.35;                            // the camera scale before the pull (match the CAMERA zoom); 1 = no pull
var AT = { open: 0.10, turn: 0.70, rows: [1.30, 1.90] };   // fallbacks (s after A) when a word isn't found
var STEP = [0.05, 0.028];                   // s between letters, per row
var OUT = 0.24;                             // everything starts leaving this long before B

function $(s) { return document.querySelector(s); }
function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
var C = { light: tok('--c-light'), accent: tok('--c-accent') };
function find(w, after, fb) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }

// ---- times
var tOpen = find(OPEN, A, AT.open);
var tTurn = Math.max(tOpen + 0.15, find(TURN, tOpen, AT.turn));
var tRow = [], prev = tTurn;
ROWS.forEach(function (r, i) { prev = find(r[1], prev, AT.rows[i] !== undefined ? AT.rows[i] : AT.rows[0] + 0.6 * i); tRow.push(prev); });
var tLensOut = Math.max(tTurn + 0.42, tRow[0] - 0.16);
var tOut = B - OUT;

// ---- build: numerals, rows of letters
var nums = $('#{{ID}}-nums');
MARKS.forEach(function (m, i) {
  var d = document.createElement('div'); d.className = '{{ID}}-n'; d.id = '{{ID}}-n' + i; d.textContent = m; nums.appendChild(d);
});
var host = $('#{{ID}}-rows');
ROWS.forEach(function (r, i) {
  var row = document.createElement('div');
  row.className = '{{ID}}-row {{ID}}-' + r[2];
  row.id = '{{ID}}-r' + i;
  row.style.top = ROW_Y[i] + 'px';
  row.style.fontSize = ROW_SIZE[i] + 'px';
  row.style.lineHeight = Math.round(ROW_SIZE[i] * 1.06) + 'px';
  Array.from(r[0]).forEach(function (ch) {
    var s = document.createElement('span'); s.className = '{{ID}}-l'; s.textContent = ch === ' ' ? ' ' : ch;
    s.setAttribute('data-layout-allow-overlap', '');
    row.appendChild(s);
  });
  host.appendChild(row);
});
$$('#{{ID}} .{{ID}}-n, #{{ID}}-mm').forEach(function (e) { e.setAttribute('data-layout-allow-overlap', ''); });
function fit() {                              // each row keeps its size unless wider than the panel allows
  ROWS.forEach(function (r, i) {
    var row = $('#{{ID}}-r' + i), w = 0;
    row.style.fontSize = ROW_SIZE[i] + 'px';
    $$('#{{ID}}-r' + i + ' span').forEach(function (s) { w += s.offsetWidth; });
    if (w > 780) row.style.fontSize = (ROW_SIZE[i] * 780 / w).toFixed(2) + 'px';
  });
}
fit();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

// ================================================================ the lens readout
// a cylinder: every mark sits at an angle on a barrel of radius RAD, x = RAD sin(a), so it compresses as it turns away
var RAD = 360, CX = 380, DEG = 30, LAST = MARKS.length - 1;   // 30 degrees between focal lengths
function rad(d) { return d * Math.PI / 180; }
function lensFrame(p, t) {                    // p = scale position, 0 = the first mark ... LAST = the last
  var knurl = '', ticks = '', k, a, x;
  for (k = -40; k <= 30 + LAST * 8; k++) {   // grip ridges every 4 degrees, turning with the ring
    a = k * 4 - p * DEG;
    if (Math.abs(a) > 84) continue;
    x = CX + RAD * Math.sin(rad(a));
    knurl += 'M' + x.toFixed(1) + ' 8 V44 ';
  }
  for (k = -12; k <= LAST * 4 + 12; k++) {   // scale ticks: 4 per step, a long one under each numeral
    a = (k / 4 - p) * DEG;
    if (Math.abs(a) > 84) continue;
    x = CX + RAD * Math.sin(rad(a));
    var major = k % 4 === 0 && k >= 0 && k <= LAST * 4;
    ticks += 'M' + x.toFixed(1) + ' 78 V' + (major ? 100 : 89) + ' ';
  }
  tl.set('#{{ID}}-knurl', { attr: { d: knurl } }, q(t));
  tl.set('#{{ID}}-ticks', { attr: { d: ticks } }, q(t));
  for (var i = 0; i <= LAST; i++) {
    a = (i - p) * DEG;
    var c = Math.cos(rad(Math.max(-89, Math.min(89, a))));
    tl.set('#{{ID}}-n' + i, {
      x: RAD * Math.sin(rad(Math.max(-90, Math.min(90, a)))), scaleX: Math.max(0.02, c),
      opacity: Math.max(0, Math.min(1, (c - 0.12) / 0.45)),
      color: Math.abs(a) < 9 ? C.accent : C.light
    }, q(t));
  }
}
gsap.set('#{{ID}}-lens', { opacity: 0 });
tl.set('#{{ID}}-lens', { opacity: 1 }, q(tOpen));
tl.fromTo('#{{ID}}-plate', { scaleY: 0.18, scaleX: 0.9, opacity: 0 },
  { scaleY: 1, scaleX: 1, opacity: 1, duration: 0.2, ease: 'power3.out', immediateRender: false }, q(tOpen));
// frame by frame: a small nudge on the open word, then the spin to the last mark on the turn word
function backOut(u, s) { u -= 1; return 1 + (s + 1) * u * u * u + s * u * u; }
for (var f = 0; f <= Math.round((tLensOut + 0.14 - tOpen) * 30); f++) {
  var t = tOpen + f / 30, p;
  if (t < tTurn) p = 0.12 * (1 - Math.pow(1 - (t - tOpen) / (tTurn - tOpen), 3));
  else p = 0.12 + (LAST - 0.12) * backOut(Math.min(1, (t - tTurn) / 0.3), 1.1);
  lensFrame(p, t);
}
// the camera pulls out of the held zoom with the ring
if (HOLD !== 1) tl.fromTo('#cam', { scale: HOLD }, { scale: 1, duration: 0.42, ease: 'expo.out', immediateRender: false }, q(tTurn));
// the last mark seats: a short press on the plate, then the readout folds shut
tl.fromTo('#{{ID}}-plate', { scale: 1 }, { scale: 0.97, duration: 0.06, ease: 'power2.out', yoyo: true, repeat: 1, immediateRender: false }, q(tTurn + 0.28));
tl.fromTo('#{{ID}}-plate', { scaleY: 1, opacity: 1 }, { scaleY: 0.1, opacity: 0, duration: 0.12, ease: 'power3.in', immediateRender: false }, q(tLensOut));
tl.set('#{{ID}}-lens', { opacity: 0 }, q(tLensOut + 0.14));

// ================================================================ the panel and the keyframe track
var TW = 700, TR0 = tRow[0], TR1 = Math.max(TR0 + 0.3, tOut - 0.06);
function tx(t) { return Math.max(0, Math.min(TW, (t - TR0) / (TR1 - TR0) * TW)); }
var tPanel = tRow[0] - 0.14;
gsap.set('#{{ID}}-panel', { opacity: 0, clipPath: 'inset(0% 0% 100% 0%)' });
tl.set('#{{ID}}-panel', { opacity: 1 }, q(tPanel));
tl.fromTo('#{{ID}}-panel', { clipPath: 'inset(0% 0% 100% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: 0.2, ease: 'power3.out', immediateRender: false }, q(tPanel));
gsap.set('#{{ID}}-track', { opacity: 0 });
tl.set('#{{ID}}-track', { opacity: 1 }, q(TR0));
tl.fromTo('#{{ID}}-line', { scaleX: 0 }, { scaleX: 1, duration: 0.3, ease: 'power3.out', immediateRender: false }, q(TR0));
tl.fromTo('#{{ID}}-head', { x: 0 }, { x: TW, duration: TR1 - TR0, ease: 'none', immediateRender: false }, q(TR0));
var keys = $('#{{ID}}-keys');
function key(t) {                             // an accent key drops on the track at the time it animates
  var k = document.createElement('div');
  k.className = '{{ID}}-k'; k.style.left = tx(t).toFixed(1) + 'px';
  k.appendChild(document.createElement('i'));
  keys.appendChild(k);
  gsap.set(k, { opacity: 0 });
  tl.fromTo(k, { opacity: 1, scale: 0 }, { opacity: 1, scale: 1, duration: 0.16, ease: 'back.out(3)', immediateRender: false }, q(t));
}

// ================================================================ the words, letter by letter, a different move each
// moves cycle: drop (falls in and bounces), flip (turns down off its top edge), stretch (grows up off the baseline)
function move(el, kind, t) {
  if (kind === 0) {
    gsap.set(el, { transformOrigin: '50% 100%' });
    tl.fromTo(el, { y: -120, opacity: 0 }, { y: 0, opacity: 1, duration: 0.26, ease: 'back.out(1.9)', immediateRender: false }, q(t));
    tl.fromTo(el, { scaleY: 1 }, { scaleY: 0.86, duration: 0.05, ease: 'power2.out', yoyo: true, repeat: 1, immediateRender: false }, q(t + 0.14));
  } else if (kind === 1) {
    gsap.set(el, { transformOrigin: '50% 0%', transformPerspective: 700 });
    tl.fromTo(el, { rotationX: -95, opacity: 0 }, { rotationX: 0, opacity: 1, duration: 0.3, ease: 'back.out(1.7)', immediateRender: false }, q(t));
  } else {
    gsap.set(el, { transformOrigin: '50% 100%' });
    tl.fromTo(el, { scaleY: 0, scaleX: 1.5, opacity: 1 }, { scaleY: 1, scaleX: 1, opacity: 1, duration: 0.28, ease: 'back.out(2.6)', immediateRender: false }, q(t));
  }
}
ROWS.forEach(function (r, i) {
  var ls = $$('#{{ID}}-r' + i + ' span');
  gsap.set(ls, { opacity: 0 });
  var st = Math.min(STEP[i] || 0.03, Math.max(0.012, (tOut - 0.3 - tRow[i]) / Math.max(1, ls.length)));
  ls.forEach(function (el, j) { var t = tRow[i] + j * st; move(el, (j + 2 * i) % 3, t); key(t); });
});
// the landing: the last row takes a single beat of weight once it is built
var last = ROWS.length - 1, tLand = tRow[last] + 0.38;
if (tLand + 0.27 < tOut) {
  tl.fromTo('#{{ID}}-r' + last, { y: 0 }, { y: 12, duration: 0.05, ease: 'power2.out', immediateRender: false }, q(tLand));
  tl.fromTo('#{{ID}}-r' + last, { y: 12 }, { y: 0, duration: 0.22, ease: 'back.out(3)', immediateRender: false }, q(tLand + 0.05));
}

// ================================================================ out: letters sink, the panel rolls up, the track retracts
ROWS.forEach(function (r, i) {
  $$('#{{ID}}-r' + i + ' span').forEach(function (el, j) {
    tl.fromTo(el, { y: 0, opacity: 1 }, { y: 50, opacity: 0, duration: 0.08, ease: 'power3.in', immediateRender: false }, q(tOut + 0.01 * i + j * 0.005));
  });
});
tl.fromTo('#{{ID}}-panel', { clipPath: 'inset(0% 0% 0% 0%)' }, { clipPath: 'inset(0% 0% 100% 0%)', duration: 0.18, ease: 'power3.in', immediateRender: false }, q(tOut + 0.04));
tl.set('#{{ID}}-line', { transformOrigin: '100% 50%' }, q(tOut));
tl.fromTo('#{{ID}}-line', { scaleX: 1 }, { scaleX: 0, duration: 0.16, ease: 'power3.in', immediateRender: false }, q(tOut));
tl.fromTo(['#{{ID}}-keys', '#{{ID}}-head'], { opacity: 1 }, { opacity: 0, duration: 0.1, ease: 'power2.in', immediateRender: false }, q(tOut + 0.02));
tl.set('#{{ID}}-track', { opacity: 0 }, q(tOut + 0.18));
