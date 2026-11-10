// video-backdrop-label (layer: top, the same window as video-backdrop). The chapter label for the walkthrough:
//   first cue  the box wipes open from the left just before the first chapter's word, its label pushes in
//   each cue   the old label pushes out left (gone 0.02 s before the word), the new one pushes in from the right on
//              the word, so two labels are never in view; the rail segment of the chapter just left fills, the
//              current one runs across its chapter
//   out        the box wipes shut to the right as the last chapter pushes out behind (T.out before B, or OUT_ON)
// Use it with video-backdrop (same at / end). Keep CHAPTERS' words, AT and OUT_ON the same as its CUES, AT and
// OUT_ON. Without the backdrop it still works as a chapter lower third over any walkthrough.
// Supply: the chapter names (plain, true labels of what each chapter shows).
// Change only these constants:
var CHAPTERS = [                    // label, and the spoken word its chapter pushes in on
  { label: 'The raw take', word: 'I' },
  { label: 'The plan', word: 'recorded' },
  { label: 'One note', word: 'a' }
];
var AT = [0.10, 0.53, 0.95, 1.30];  // fallbacks (s after A) for words not found
var OUT_ON = '';                    // the box wipes shut on this word; '' or not found: T.out before B
var POS = { x: 64, y: 1150 };       // the box's top-left: above the caption band, clear of the right-side UI
var T = {
  push: 0.24,                       // video-backdrop's push (the label moves with it)
  out: 0.24,                        // video-backdrop's out (s before B)
  wipe: 0.26                        // the box opening
};

function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
var ID = '{{ID}}', N = CHAPTERS.length;
function el(s) { return document.getElementById(ID + '-' + s); }
var box = el('box'), row = el('row'), rail = el('rail');

// ---- build the labels and the rail from CHAPTERS
CHAPTERS.forEach(function (c, i) {
  var d = document.createElement('div'), b = document.createElement('b'), s = document.createElement('span');
  d.id = ID + '-l' + i;
  d.className = ID + '-l';
  b.textContent = (i < 9 ? '0' : '') + (i + 1);
  s.textContent = c.label;
  [b, s].forEach(function (e) { e.setAttribute('data-layout-allow-overlap', ''); e.setAttribute('data-layout-allow-occlusion', ''); });
  d.appendChild(b);
  d.appendChild(s);
  row.appendChild(d);
  var seg = document.createElement('div'), f = document.createElement('i');
  seg.className = ID + '-seg';
  f.id = ID + '-f' + i;
  seg.appendChild(f);
  rail.appendChild(seg);
});
// the box is as wide as its longest label (420-900 px); the rail splits its width between the chapters
function fit() {
  var wmax = 0;
  for (var i = 0; i < N; i++) {
    var d = el('l' + i), w = 56 + 18;
    Array.prototype.forEach.call(d.children, function (e) { w += e.offsetWidth; });
    wmax = Math.max(wmax, w);
  }
  var W = Math.round(Math.min(900, Math.max(420, wmax)));
  box.style.width = W + 'px';
  var rw = W - 56, g = 8, sw = (rw - g * (N - 1)) / N;
  rail.style.width = rw + 'px';
  Array.prototype.forEach.call(rail.children, function (s, i) { s.style.left = (i * (sw + g)) + 'px'; s.style.width = sw + 'px'; });
}
fit();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

// ---- chapter times: on their words, searched in order from A (as video-backdrop)
var at = [], prev = A;
CHAPTERS.forEach(function (c, i) {
  var w = wordAt(c.word, prev);
  at.push((w === null || w >= B - T.out) ? A + AT[i] : w);
  prev = at[i];
});
var tOut = OUT_ON ? wordAt(OUT_ON, at[N - 1]) : null;
tOut = Math.min(tOut === null ? B : tOut, B - T.out);

// ---- start states
var R = tok('--radius') || '0px';
var SHUT = 'inset(0% 100% 0% 0% round ' + R + ')', OPEN = 'inset(0% 0% 0% 0% round ' + R + ')', GONE = 'inset(0% 0% 0% 100% round ' + R + ')';
gsap.set(box, { x: POS.x, y: POS.y, clipPath: SHUT });
for (var i = 0; i < N; i++) { gsap.set(el('l' + i), { xPercent: 105 }); gsap.set(el('f' + i), { scaleX: 0 }); }

// ---- in, chapters, out
tl.fromTo(box, { clipPath: SHUT }, { clipPath: OPEN, duration: T.wipe, ease: 'power3.out', immediateRender: false }, q(Math.max(A, at[0] - 0.09)));
for (var k = 0; k < N; k++) {
  var t = at[k], next = k + 1 < N ? at[k + 1] : tOut;
  if (k > 0) {
    tl.fromTo(el('l' + (k - 1)), { xPercent: 0 }, { xPercent: -105, duration: 0.12, ease: 'power3.in', immediateRender: false }, q(t - 0.14));
    tl.set(el('f' + (k - 1)), { scaleX: 1 }, q(t));
  }
  tl.fromTo(el('l' + k), { xPercent: 105 }, { xPercent: 0, duration: 0.22, ease: 'power3.out', immediateRender: false }, q(Math.max(A, t - 0.02)));
  tl.fromTo(el('f' + k), { scaleX: 0 }, { scaleX: 1, duration: Math.max(0.05, next - t), ease: 'none', immediateRender: false }, q(t));
}
tl.fromTo(box, { clipPath: OPEN }, { clipPath: GONE, duration: 0.2, ease: 'power3.in', immediateRender: false }, q(tOut));
