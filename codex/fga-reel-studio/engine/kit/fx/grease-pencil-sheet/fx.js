// grease-pencil-sheet (layer: top, above the speaker, under the captions). The raw take, bad takes still in it:
//   drop      a flat contact sheet of the raw take falls in from above the frame (gravity, power2.in) and lands on
//             its word with one small bounce: two film strips of six frames, a timecode under each, the raw file's
//             name, length and size in the footer
//   develop   the frames develop in reading order, paper-bright to the picture, 0.02s apart
//   mark      on each cue word a grease pencil in the negative colour circles (the first and last) or X's (the
//             others) the next frame the edit really cut; its timecode turns negative and the frame dims; the
//             first two marks in the top strip get a short handwritten label above them
//   out       the sheet lifts off the top, flat, the way it came in
// Reach for it on "the raw footage", "the bad takes are still in it", "here's everything I recorded".
// Supply: the cue words below, then the frames of your raw take:
//   PY fx/<id>/gen.py <project> [<id>]
// It pulls 12 frames from edit.SRC (TIMES in gen.py, or picked for you from edit.KEEP), works out which ones the
// cut removed, and writes frames.jpg and the frames block below. The library's frames are the lab's stand-in.
// Change only these constants:
var KEY = { land: 'bad' };                  // the sheet lands on this word
var MARK_ON = ['are', 'still', 'in', 'the', 'raw'];   // one mark per cut frame, on these words in order
var LABELS = ['bad take', 'cut'];           // handwritten over the first two marks in the top strip ([] = none)
var AT = { land: 0.29, mark: 0.67, gap: 0.19 };   // fallbacks (s after A): the landing, the first mark, the gap after
var FALL = 0.24;                            // the drop from above the frame (s)
var DEVELOP = { after: 0.04, step: 0.02 };  // the frames start developing this long after the landing, this far apart
var OUT = 0.21;                             // the sheet starts lifting this long before B

// ---- frames: gen.py rewrites the lines between these two markers ----
var FRAMES = [[3.069, 0], [9.206, 0], [10.05, 1], [15.444, 0], [21.581, 0], [21.95, 1], [27.819, 0], [33.95, 1], [34.056, 0], [40.194, 0], [46.331, 0], [50.7, 1]];   // [source time (s), 1 = the edit cut it] per frame, in order
var FOOT = ["STANDIN2.MP4", "RAW TAKE · 0:52 · 0.6 MB"];   // the footer: the raw file's name, length, size
// ---- end of frames ----

function $(s) { return document.querySelector(s); }
function rnd(i) { var x = Math.sin(i * 12.9898 + 1.7) * 43758.5453; return x - Math.floor(x); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
var ROW0 = 100, ROWH = 300, FW = 128, FH = 228, FGAP = 16, FX0 = 46, NF = Math.min(12, FRAMES.length);
function fpos(i) { return [FX0 + (i % 6) * (FW + FGAP), ROW0 + Math.floor(i / 6) * ROWH + 16]; }
function tc(s) { var f = Math.round(s * 30), p = function (n) { return (n < 10 ? '0' : '') + n; };
  return p(Math.floor(f / 1800)) + ':' + p(Math.floor(f / 30) % 60) + ':' + p(f % 30); }
function el(tag, cls, parent, html) { var e = document.createElement(tag); e.className = cls; if (html) e.innerHTML = html; parent.appendChild(e); return e; }

// ---- the sheet: strips with sprocket holes, frames, timecodes, footer
var sheet = $('#{{ID}}-sheet');
for (var r = 0; r < Math.ceil(NF / 6); r++) {
  var st = el('div', '{{ID}}-strip', sheet), holes = '';
  st.style.top = (ROW0 + r * ROWH) + 'px';
  for (var x = 14; x < 900; x += 22) holes += '<i style="left:' + x + 'px"></i>';
  el('div', '{{ID}}-holes {{ID}}-ht', st, holes);
  el('div', '{{ID}}-holes {{ID}}-hb', st, holes);
}
for (var i = 0; i < NF; i++) {
  var p = fpos(i), f = el('div', '{{ID}}-fr', sheet), t = el('div', '{{ID}}-tc', sheet);
  f.id = '{{ID}}-f' + i;
  f.style.left = p[0] + 'px'; f.style.top = p[1] + 'px';
  f.style.backgroundSize = (FRAMES.length * FW) + 'px ' + FH + 'px';
  f.style.backgroundPosition = (-i * FW) + 'px 0px';
  t.id = '{{ID}}-tc' + i;
  t.style.left = (p[0] - 8) + 'px'; t.style.top = (p[1] + FH + 30) + 'px';
  t.textContent = tc(FRAMES[i][0]);
}
var foot = el('div', '', sheet);
foot.id = '{{ID}}-foot';
FOOT.forEach(function (s) { var sp = document.createElement('span'); sp.textContent = s; foot.appendChild(sp); });

// ---- the grease pencil: a loose loop (about 1.12 turns, wobbling, ending past its start) or two quick strokes
function loopPath(cx, cy, rx, ry, seed) {
  var d = '', a0 = -1.2 + rnd(seed) * 0.4;
  for (var k = 0; k <= 60; k++) {
    var u = k / 60, a = a0 + u * 2 * Math.PI * 1.12, w = 1 + 0.06 * Math.sin(u * 7 + seed) + 0.05 * u;
    d += (k ? ' L' : 'M') + (cx + Math.cos(a) * rx * w).toFixed(1) + ' ' + (cy + Math.sin(a) * ry * w).toFixed(1);
  }
  return d;
}
function xPaths(x, y, seed) {
  var j = function (i) { return ((rnd(seed * 7 + i) - 0.5) * 16).toFixed(0) * 1; };
  return ['M' + (x + 6 + j(1)) + ' ' + (y + 22 + j(2)) + ' Q' + (x + 70 + j(3)) + ' ' + (y + 104 + j(4)) + ' ' + (x + FW - 2 + j(5)) + ' ' + (y + FH - 18),
          'M' + (x + FW - 8 + j(6)) + ' ' + (y + 18 + j(7)) + ' Q' + (x + 58 + j(8)) + ' ' + (y + 120 + j(9)) + ' ' + (x + 4 + j(10)) + ' ' + (y + FH - 12)];
}
var ink = $('#{{ID}}-ink'), NS = 'http://www.w3.org/2000/svg';
function stroke(d, id) { var e = document.createElementNS(NS, 'path'); e.setAttribute('class', '{{ID}}-mk'); e.setAttribute('pathLength', '1');
  e.setAttribute('d', d); e.id = id; ink.appendChild(e); return '#' + id; }
var cut = [];
for (i = 0; i < NF; i++) if (FRAMES[i][1]) cut.push(i);
var marks = cut.map(function (fi, m) {
  var p = fpos(fi), circle = m === 0 || m === cut.length - 1;
  if (circle) return { fi: fi, circle: true, a: stroke(loopPath(p[0] + FW / 2, p[1] + FH / 2, FW * 0.66, FH * 0.6, m + 2), '{{ID}}-m' + m + 'a') };
  var xs = xPaths(p[0], p[1], m + 1);
  return { fi: fi, circle: false, a: stroke(xs[0], '{{ID}}-m' + m + 'a'), b: stroke(xs[1], '{{ID}}-m' + m + 'b') };
});

// ---- labels over the first marks in the top strip, never wider than the room between them
var top = marks.filter(function (mk) { return mk.fi < 6; }).slice(0, LABELS.length);
var labels = top.map(function (mk, n) {
  var lb = el('div', '{{ID}}-lb', sheet), sp = document.createElement('span');
  sp.textContent = LABELS[n];
  lb.appendChild(sp);
  lb.id = '{{ID}}-l' + n;
  lb.setAttribute('data-layout-allow-overlap', '');
  var cx = fpos(mk.fi)[0] + FW / 2, room = 300;
  top.forEach(function (o, k) { if (k !== n) room = Math.min(room, Math.abs(fpos(o.fi)[0] + FW / 2 - cx) - 24); });
  room = Math.min(room, 2 * Math.min(cx, 940 - cx) - 24);
  lb.style.width = room + 'px'; lb.style.left = (cx - room / 2) + 'px'; lb.style.top = '4px';
  return { el: lb, span: sp, room: room, mk: mk };
});
function fit() {
  labels.forEach(function (l) {
    if (!l.span.dataset.max) l.span.dataset.max = parseFloat(getComputedStyle(l.span).fontSize);
    var max = +l.span.dataset.max;
    l.span.style.fontSize = max + 'px';
    if (l.span.offsetWidth > l.room) l.span.style.fontSize = (max * l.room / l.span.offsetWidth).toFixed(2) + 'px';
  });
}
fit();
if (document.fonts && document.fonts.load) {
  document.fonts.load(tok('--display-style') + ' ' + tok('--display-weight') + ' 64px ' + tok('--font-display'), LABELS.join(' '))
    .catch(function () {}).then(fit, fit);
  document.fonts.ready.then(fit);
}

// ---- beat times, each on its word (searched in order from A; a word missing from words.json falls back to AT)
function find(word, after, fallback) {
  var w = word ? wordAt(word, after) : null;
  return (w === null || w >= B) ? A + fallback : w;
}
var tLand = Math.max(A + FALL, find(KEY.land, A, AT.land));
var prev = tLand, tMark = [];
marks.forEach(function (mk, m) {
  var w = MARK_ON[m] ? wordAt(MARK_ON[m], prev + 0.01) : null;
  prev = (w === null || w >= B - OUT - 0.1) ? (m ? prev + AT.gap : Math.max(A + AT.mark, tLand + 0.3)) : w;
  tMark.push(prev);
});

// ---- build: up above the frame, frames undeveloped, ink and labels hidden
gsap.set('#{{ID}}-sheet', { y: -1150 });
gsap.set('#{{ID}} .{{ID}}-fr', { opacity: 0 });
gsap.set('#{{ID}} .{{ID}}-mk', { opacity: 0, attr: { 'stroke-dasharray': '1 1', 'stroke-dashoffset': 1 } });
gsap.set('#{{ID}} .{{ID}}-lb span', { clipPath: 'inset(0% 100% 0% 0%)' });

// drop: falls from rest, lands on its word, one small bounce
tl.fromTo('#{{ID}}-sheet', { y: -1150 }, { y: 0, duration: FALL, ease: 'power2.in', immediateRender: false }, q(tLand - FALL));
tl.fromTo('#{{ID}}-sheet', { y: 0 }, { y: -16, duration: 0.07, ease: 'power2.out', immediateRender: false }, q(tLand));
tl.fromTo('#{{ID}}-sheet', { y: -16 }, { y: 0, duration: 0.1, ease: 'power2.in', immediateRender: false }, q(tLand + 0.07));
// develop in reading order
for (i = 0; i < NF; i++) {
  tl.fromTo('#{{ID}}-f' + i, { opacity: 0, filter: 'brightness(2.4) contrast(0.6)' }, { opacity: 1, filter: 'brightness(1) contrast(1)',
    duration: 0.24, ease: 'power2.out', immediateRender: false }, q(tLand + DEVELOP.after + i * DEVELOP.step));
}
// the pencil, one mark per word
marks.forEach(function (mk, m) {
  var t = tMark[m];
  if (mk.circle) {
    tl.set(mk.a, { opacity: 1 }, q(t));
    tl.fromTo(mk.a, { attr: { 'stroke-dashoffset': 1 } }, { attr: { 'stroke-dashoffset': 0 }, duration: 0.2, ease: 'power1.inOut', immediateRender: false }, q(t));
  } else {
    tl.set([mk.a, mk.b], { opacity: 1 }, q(t));
    tl.fromTo(mk.a, { attr: { 'stroke-dashoffset': 1 } }, { attr: { 'stroke-dashoffset': 0 }, duration: 0.07, ease: 'power2.in', immediateRender: false }, q(t));
    tl.fromTo(mk.b, { attr: { 'stroke-dashoffset': 1 } }, { attr: { 'stroke-dashoffset': 0 }, duration: 0.07, ease: 'power2.in', immediateRender: false }, q(t + 0.08));
  }
  tl.fromTo('#{{ID}}-tc' + mk.fi, { color: tok('--c-muted-light') }, { color: tok('--c-neg'), duration: 0.06, ease: 'none', immediateRender: false }, q(t));
  tl.fromTo('#{{ID}}-f' + mk.fi, { filter: 'brightness(1) saturate(1)' }, { filter: 'brightness(0.78) saturate(0.4)', duration: 0.12, ease: 'none', immediateRender: false }, q(t + 0.06));
});
labels.forEach(function (l) {
  var t = tMark[marks.indexOf(l.mk)] + 0.12;
  tl.fromTo(l.span, { clipPath: 'inset(0% 100% 0% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: 0.06 * Math.sqrt(l.span.textContent.length) + 0.04,
    ease: 'none', immediateRender: false }, q(t));
});
// out: lifted off the top, flat
tl.fromTo('#{{ID}}-sheet', { y: 0 }, { y: -1250, duration: 0.16, ease: 'power3.in', immediateRender: false }, q(B - OUT));
