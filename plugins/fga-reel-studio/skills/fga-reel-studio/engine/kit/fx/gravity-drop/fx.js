// gravity-drop (layer: behind, under the speaker's cutout). One emphatic word, a second time (word-stamp's variant):
//   drop      WORD falls in from above the frame one letter at a time, each letter falling 4 frames under gravity
//             (power2.in), one landing every 2 frames, the first landing LAG after its spoken word starts
//   land      each letter squashes on its baseline (elastic back to shape), hops once, and the whole word is nudged
//             down 7px by every impact; the speaker's head breaks the baseline
//   split     light type, ink wherever a letter crosses a light part of the picture, one mask per frame (masks.png)
// Reach for it on never, always, zero, nothing: an emphatic word that already got word-stamp once in the video.
// Needs a CUT_WINDOWS entry over its window; out hard at the window end.
// Supply: the word, the spoken word it lands on, CENTER_X / Y on the head, and the masks for your footage:
//   PY fx/<id>/gen.py <project> [<id>]
// It reads this effect's window from edit.py, the picture from public/clean.mp4 (the speaker left out with
// public/subject.webm) and writes fx/<id>/masks.png. The masks.png in the library is the lab's stand-in: rerun
// gen.py whenever the window or the cut changes, or set SPLIT = false to keep the word light everywhere.
// Change only these constants:
var WORD = 'NEVER';                         // the word that drops
var KEY = 'never';                          // the spoken word it lands on
var AT = { land: 0.55 };                    // fallback: the first letter lands this long after A (s)
var LAG = 5 / 30;                           // the first letter lands this long after its word starts
var STEP = 2 / 30;                          // one landing every two frames
var FALL = 4 / 30;                          // each letter falls for four frames
var HEIGHT = 900;                           // px a letter falls (from above the frame)
var CENTER_X = 540;                         // the speaker's head on the 1080 frame: the word centres on it
var Y = 0;                                  // px: move the word down (+) or up (-) so the head breaks only its foot
var SPLIT = true;                           // false: light type only (no masks.png needed)
var BAND = 700, COLS = 8;                   // the masks' band (y 0 to BAND) and bands a row: match gen.py

function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
var band = document.getElementById('{{ID}}-band'), dk = document.getElementById('{{ID}}-dk0');
var N = Math.max(1, Math.round(B * 30) - Math.round(A * 30));      // one mask per frame of the window
var CH = Array.from(WORD);

// ---- the word, letter by letter, into the light copy and the ink copy; then one ink copy per frame
$$('#{{ID}} .{{ID}}-t').forEach(function (host) {
  host.textContent = '';
  CH.forEach(function (c, k) {
    var s = document.createElement('span');
    s.className = '{{ID}}-ch {{ID}}-c' + k;
    s.textContent = c === ' ' ? ' ' : c;
    host.appendChild(s);
  });
});
if (!SPLIT) dk.parentNode.removeChild(dk);
for (var f = 1; SPLIT && f < N; f++) {
  var c = dk.cloneNode(true);
  c.id = '{{ID}}-dk' + f;
  band.appendChild(c);
}
$$('#{{ID}} .{{ID}}-dk').forEach(function (e, i) {
  var pos = (-(i % COLS) * 1080) + 'px ' + (-Math.floor(i / COLS) * BAND) + 'px';
  e.style.webkitMaskSize = e.style.maskSize = (COLS * 1080) + 'px auto';
  e.style.webkitMaskPosition = e.style.maskPosition = pos;
});
// the copies overlap and sit behind the head on purpose: tell the layout audit (it reads the text elements)
$$('#{{ID}} .{{ID}}-ch, #{{ID}} .{{ID}}-t').forEach(function (e) {
  e.setAttribute('data-layout-allow-overlap', '');
  e.setAttribute('data-layout-allow-occlusion', '');
});

// ---- the word keeps its fx.html size unless it is wider than 960px with the pack's display face
function fit() {
  $$('#{{ID}} .{{ID}}-w').forEach(function (box) {
    if (!box.dataset.max) box.dataset.max = parseFloat(getComputedStyle(box).fontSize);
    var max = +box.dataset.max;
    box.style.fontSize = max + 'px';
    var w = box.querySelector('.{{ID}}-t').offsetWidth;
    if (w > 960) box.style.fontSize = (max * 960 / w).toFixed(2) + 'px';
  });
}
fit();
if (document.fonts && document.fonts.load) {
  document.fonts.load(tok('--display-style') + ' ' + tok('--display-weight') + ' 100px ' + tok('--font-display'), WORD)
    .catch(function () {}).then(fit, fit);
  document.fonts.ready.then(fit);
}

// ---- beat times: the first landing on its word (a word missing from words.json falls back to AT)
var w = KEY ? wordAt(KEY, A) : null;
var tLand0 = (w === null || w >= B) ? A + AT.land : w + LAG;
tLand0 = Math.max(A + FALL, tLand0);

// ---- build: hidden until they fall; centred on the head
if (q(A) <= 0) gsap.set('#{{ID}}', { opacity: 1 });
gsap.set('#{{ID}} .{{ID}}-stack', { x: CENTER_X - 540, y: Y });
gsap.set('#{{ID}} .{{ID}}-ch', { opacity: 0 });
CH.forEach(function (c, k) {
  var tL = tLand0 + k * STEP, sel = '#{{ID}} .{{ID}}-c' + k;
  tl.set(sel, { opacity: 1 }, q(tL - FALL));
  tl.fromTo(sel, { y: -HEIGHT }, { y: 0, duration: FALL, ease: 'power2.in', immediateRender: false }, q(tL - FALL));
  tl.fromTo(sel, { scaleY: 0.84, scaleX: 1.07 }, { scaleY: 1, scaleX: 1, duration: 0.34, ease: 'elastic.out(1, 0.45)', immediateRender: false }, q(tL));
  tl.fromTo(sel, { y: 0 }, { y: -16, duration: 0.07, ease: 'power2.out', immediateRender: false }, q(tL + 1 / 30));
  tl.fromTo(sel, { y: -16 }, { y: 0, duration: 0.07, ease: 'power2.in', immediateRender: false }, q(tL + 3 / 30));
  tl.fromTo('#{{ID}} .{{ID}}-stack', { y: Y + 7 }, { y: Y, duration: 0.12, ease: 'power2.out', immediateRender: false }, q(tL));
});

// ---- the ink copies: frame f of the window shows copy f (its own band of masks.png)
if (SPLIT) {
  gsap.set('#{{ID}} .{{ID}}-dk', { opacity: 0 });
  gsap.set('#{{ID}}-dk0', { opacity: 1 });
  for (var k = 1; k < N; k++) {
    off('#{{ID}}-dk' + (k - 1), A + k / 30);
    on('#{{ID}}-dk' + k, A + k / 30);
  }
}
