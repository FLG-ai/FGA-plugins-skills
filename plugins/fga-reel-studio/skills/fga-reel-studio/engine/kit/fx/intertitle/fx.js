// intertitle (layer: top, above the speaker; the card carries the words, so the captions step aside). A silent-film
// title card for a quoted line:
//   iris      a ring of black closes on the speaker's face (fast, power3), holds tight on it for a frame or two and
//             snaps shut
//   card      the dark card irises open from the centre of the frame, its thin double rule frame draws in from its
//             corners, the small diamonds pop
//   line      the words set one by one on the spoken words (a short settle up, still like intertitle type); words
//             spoken before the card is open set in a quick run as it opens
//   key       a diamond rule draws open, then the key words land under it, larger, in the display italic when the
//             pack has one (the pack's own display style and weight when it has none)
//   film      grain swaps every two frames (g0..g3.png), the exposure flickers and the gate weaves, card only
//   out       a hole irises open from the face, done on the window end
// Reach for it on "like a movie", "it reads like a film", any line worth quoting. Give the window a KARAOKE hide
// (edit.py: KARAOKE = dict(hide=[(start, end)])) so the captions don't print over the card.
// Supply: the words and the face position in the shot. The grain frames are made by
//   PY fx/<id>/mkgrain.py <project> [<id>]
// (seeded, the pack's light and dark specks; the library ships the lab's set, so it works without running it).
// Change only these constants:
var LINES = [['It', 'reads'], ['like', 'a']];   // the line above the rule, row by row; each word sets on its spoken word
var KEY = ['movie.'];                       // the key words under the rule, on their spoken words
var AT = 0.10;                              // fallback (s after A) for the first word when it isn't found; later ones +0.3 each
var FACE_X = 540, FACE_Y = 720;             // the speaker's face on the 1080x1920 frame: the iris closes and opens on it
var CARD_IN = 0.27;                         // the card starts opening this long after A (the iris is shut by then)
var OUT_FRAMES = 6;                         // frames the out iris takes, ending on B

function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
function rnd(i) { var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
var F = 1 / 30;

// ---- the words in, one span per word
var all = [];
var host = document.getElementById('{{ID}}-lines');
LINES.forEach(function (row) {
  var d = document.createElement('div');
  d.className = '{{ID}}-l';
  row.forEach(function (w, i) {
    if (i) d.appendChild(document.createTextNode(' '));
    var s = document.createElement('span'); s.textContent = w; d.appendChild(s); all.push([s, w]);
  });
  host.appendChild(d);
});
var key = document.getElementById('{{ID}}-key');
KEY.forEach(function (w, i) {
  if (i) key.appendChild(document.createTextNode(' '));
  var s = document.createElement('span'); s.textContent = w; key.appendChild(s); all.push([s, w]);
});
$$('#{{ID}} .{{ID}}-l span').forEach(function (e) { e.setAttribute('data-layout-allow-overlap', ''); });

// ---- the key words in the display italic when the pack has one, else in the pack's own display style and weight
function hasItalic() {
  var fam = tok('--font-display').split(',')[0].replace(/['"]/g, '').trim(), yes = false;
  if (document.fonts && document.fonts.forEach) document.fonts.forEach(function (f) {
    if (f.family.replace(/['"]/g, '').trim() === fam && f.style === 'italic') yes = true;
  });
  return yes;
}
if (hasItalic()) { key.style.fontStyle = 'italic'; key.style.fontWeight = '400'; }
else { key.style.fontStyle = 'var(--display-style)'; key.style.fontWeight = 'var(--display-weight)'; }

// ---- every row keeps its fx.html size unless it is wider than the card (820px) with the pack's face
function fit() {
  $$('#{{ID}} .{{ID}}-l').forEach(function (row) {
    if (!row.dataset.max) row.dataset.max = parseFloat(getComputedStyle(row).fontSize);
    var max = +row.dataset.max;
    row.style.fontSize = max + 'px';
    var w = row.scrollWidth;
    if (w > 800) row.style.fontSize = (max * 800 / w).toFixed(2) + 'px';
  });
}
fit();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

// ---- times: each word on its spoken word, searched in order from A
var CIN = A + CARD_IN, OPEN = CIN + 0.06;   // words can set once the card is this far open
var times = [], prev = A, run = 0;
all.forEach(function (w, i) {
  var t = wordAt(w[1], prev);
  if (t === null || t >= B) t = (i ? times[i - 1] + 0.3 : A + AT);
  prev = t;
  times.push(t);
});
times = times.map(function (t) { return t < OPEN ? OPEN + 0.045 * (run++) : t; });
var tKey = times[all.length - KEY.length];

// 1. the ink iris: closes fast, holds tight on the face, snaps shut
function hole(cx, cy, r) {                   // the full frame minus a circle (evenodd): an iris you can see through
  return "path(evenodd, 'M0 0 H1080 V1920 H0 Z M" + (cx - r).toFixed(1) + " " + cy + " a" + r.toFixed(1) + " " + r.toFixed(1) +
    " 0 1 0 " + (2 * r).toFixed(1) + " 0 a" + r.toFixed(1) + " " + r.toFixed(1) + " 0 1 0 " + (-2 * r).toFixed(1) + " 0 Z')";
}
function e3o(x) { return 1 - Math.pow(1 - x, 3); }
function e2i(x) { return x * x; }
var R0 = 1500, RT = 210;                     // open radius (past every corner), the tight hold on the face
gsap.set('#{{ID}}-ink', { clipPath: hole(FACE_X, FACE_Y, R0) });
gsap.set('#{{ID}}-card', { opacity: 0 });
for (var f = 0; ; f++) {
  var t = A + f * F, r;
  if (t > A + 0.32) break;
  if (t <= A + 0.167) r = R0 - (R0 - RT) * e3o(Math.min(1, (t - A) / 0.167));
  else if (t <= A + 0.20) r = RT;
  else r = Math.max(0, RT * (1 - e2i(Math.min(1, (t - A - 0.20) / 0.1))));
  tl.set('#{{ID}}-ink', { clipPath: r > 0.5 ? hole(FACE_X, FACE_Y, r) : 'none' }, q(t));
}

// 2. the card irises in from the centre of the frame
tl.set('#{{ID}}-card', { opacity: 1 }, q(CIN));
tl.fromTo('#{{ID}}-card', { clipPath: 'circle(0px at 540px 870px)' },
  { clipPath: 'circle(1160px at 540px 870px)', duration: 0.27, ease: 'power2.inOut', immediateRender: false }, q(CIN));
tl.set('#{{ID}}-card', { clipPath: 'none' }, q(CIN + 0.30));
tl.set('#{{ID}}-ink', { opacity: 0 }, q(CIN + 0.30));     // under the card from here; the out hole shows the footage
// the frame draws in, the diamonds pop
gsap.set('#{{ID}} .{{ID}}-r', { attr: { 'stroke-dasharray': '1 1', 'stroke-dashoffset': 1 } });
gsap.set('#{{ID}}-orn path', { opacity: 0 });
tl.fromTo('#{{ID}} .{{ID}}-r', { attr: { 'stroke-dashoffset': 1 } },
  { attr: { 'stroke-dashoffset': 0 }, duration: 0.5, ease: 'power2.inOut', stagger: 0.06, immediateRender: false }, q(CIN + 0.04));
tl.fromTo('#{{ID}}-orn path', { opacity: 0 }, { opacity: 1, duration: 0.12, stagger: 0.03, immediateRender: false }, q(CIN + 0.40));

// 3. the line, word by word (intertitle type: still, it just appears with a short settle up)
gsap.set('#{{ID}} .{{ID}}-l span', { opacity: 0 });
all.forEach(function (w, i) {
  tl.fromTo(w[0], { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.14, ease: 'power2.out', immediateRender: false }, q(times[i]));
});
// the diamond rule draws open just ahead of the key words
gsap.set(['#{{ID}}-dl', '#{{ID}}-dr'], { scaleX: 0 });
gsap.set('#{{ID}}-div b', { opacity: 0 });
var tDiv = Math.max(OPEN, tKey - 0.12);
tl.set('#{{ID}}-div b', { opacity: 1 }, q(tDiv));
tl.fromTo(['#{{ID}}-dl', '#{{ID}}-dr'], { scaleX: 0 }, { scaleX: 1, duration: 0.22, ease: 'power3.out', immediateRender: false }, q(tDiv + 0.02));

// 4. the projector: grain swaps, flicker and gate weave every 2 frames, card only
var k = 0;
for (var t = CIN; t < B; t += 2 * F, k++) {
  var g = k % 4, p = (k + 3) % 4;
  tl.set('#{{ID}}-g' + g, { opacity: 1 }, q(t));
  tl.set('#{{ID}}-g' + p, { opacity: 0 }, q(t));
  tl.set('#{{ID}}-flick', { opacity: 0.015 + 0.075 * rnd(k + 11) }, q(t));
  tl.set('#{{ID}}-weave', { x: (rnd(k + 31) - 0.5) * 2.4, y: (rnd(k + 57) - 0.5) * 4 }, q(t));
}

// 5. out: a hole irises open from the face, done on B
var o0 = B - OUT_FRAMES * F;
for (var f = 0; f < OUT_FRAMES; f++) {
  var x = (f + 1) / OUT_FRAMES;
  tl.set('#{{ID}}-card', { clipPath: hole(FACE_X, FACE_Y, 30 + R0 * e2i(x)) }, q(o0 + f * F));
}
