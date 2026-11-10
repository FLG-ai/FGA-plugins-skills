// contact-sheet-hook (layer: cam, above the main picture and the cutout, under the captions). The hook, about time
// or the video itself:
//   frame 0   OPEN (two lines in the display face) sits over the live shot, the thumbnail, settling 1.03x to 1;
//             light type, ink where it crosses a light part of the picture (a mask per frame)
//   shrink    on its word the shot shrinks into cell 01 of a 6x5 contact sheet on the dark ground (0.3s, expo.inOut),
//             the other cells settle in from cell 01 outward, TITLE sets above it word by word up through its line
//             mask, each new line pushing the last one out
//   second    one cell exposes per frame (its still is the frame of this video playing right then), an accent
//             cursor walking the sheet: exactly one real second, the one before the drop
//   dive      on the last cell the live shot takes it over and the sheet dives into it, full frame on the drop word
//   payoff    PAYOFF[0] slams in alone over the live shot on the drop; PAYOFF[1] lands in the accent on its word
//             as the first word settles and slides over to make room (split light/ink per frame like the opener)
// Reach for it on a first line about the video itself or about time: "every single frame", "a single second".
// The caption band is under the sheet's last row: hide the captions over the window (KARAOKE["hide"]), the type
// carries the line.
// Supply: the words and the spoken words they land on, then the stills and masks for your footage:
//   PY fx/<id>/gen.py <project> [<id>]
// It reads KEY / AT / CROP below and words.json, pulls the second before the drop from public/clean.mp4 into
// cells.jpg, the masks for the opener and payoff frames into masks.png, and rewrites the GEN line. The library's
// files are the lab's stand-in: rerun gen.py whenever the window, the cut or these keys change.
// Change only these constants:
var OPEN = ['EVERY SINGLE', 'FRAME'];       // the opener: two lines, on screen from frame 0 to the shrink
var TITLE = [[['OF', 'of'], ['THIS', 'this'], ['VIDEO', 'video']],
             [['WAS', 'was'], ['EDITED', 'edited']]];   // lines over the sheet: [text, the word it rises on]
var PAYOFF = [['FOR', 'for'], ['ME.', 'me']];   // after the drop: the first on the drop, the second on its word; [] = none
var KEY = {"shrink": "frame", "drop": "for"};   // the shot shrinks into the sheet on one, lands full frame on the other
var AT = {"shrink": 0.46, "drop": 1.84};    // fallbacks (s after A) when a word isn't found (gen.py reads these too)
var CROP = {"top": 300, "bottom": 180};     // px cut off the top and bottom of the frame for a 3:4 cell (gen.py too)
var T = { shrink: 0.30, settle: 0.08, ring: 0.035, rise: 0.3, push: 0.24, slam: 0.22 };   // move lengths and staggers (s)
var GEN = {"shrink": 17, "drop": 58, "run": 26, "open": 17, "pay": 17};   // written by gen.py: the frames cells.jpg and masks.png were made for

var CW = 154, CH = 205, GX = 10, GY = 10, X0 = 53, YT = 400, BAND = 560, COLS = 8, DIVE = 3;
var S = CW / 1080;                                   // live frame -> cell (the crop is 1080 wide)
function cx(i) { return X0 + (i % 6) * (CW + GX); }
function cy(i) { return YT + Math.floor(i / 6) * (CH + GY); }
function $(s) { return document.querySelector(s); }
function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function pad(n) { return (n < 10 ? '0' : '') + n; }
var FA = Math.round(A * 30);
var tShrink = GEN.shrink / 30, tDrop = GEN.drop / 30, RUN = GEN.run;

// ---- the cells
var cells = $('#{{ID}}-cells');
for (var i = 0; i < 30; i++) {
  var c = document.createElement('div');
  c.className = '{{ID}}-cell';
  c.id = '{{ID}}-c' + i;
  c.style.left = cx(i) + 'px'; c.style.top = cy(i) + 'px';
  c.innerHTML = '<span class="{{ID}}-n">' + pad(i + 1) + '</span><div class="{{ID}}-im g" id="{{ID}}-i' + i + '" style="background-position:' +
    (-(i % 6) * CW) + 'px ' + (-Math.floor(i / 6) * CH) + 'px"></div><span class="{{ID}}-tab">' + pad(i + 1) + '</span>';
  cells.appendChild(c);
}

// ---- the words: opener, title lines, payoff; then one ink copy per masked frame (opener frames, then payoff frames)
$$('#{{ID}} .{{ID}}-o1 .{{ID}}-t').forEach(function (e) { e.textContent = OPEN[0] || ''; });
$$('#{{ID}} .{{ID}}-o2 .{{ID}}-t').forEach(function (e) { e.textContent = OPEN[1] || ''; });
$$('#{{ID}} .{{ID}}-p1').forEach(function (e) { e.textContent = PAYOFF[0] ? PAYOFF[0][0] : ''; });
$$('#{{ID}} .{{ID}}-p2').forEach(function (e) { e.textContent = PAYOFF[1] ? PAYOFF[1][0] : ''; if (!PAYOFF[1]) e.style.display = 'none'; });
['#{{ID}}-ta', '#{{ID}}-tb'].forEach(function (sel, li) {
  var host = $(sel);
  (TITLE[li] || []).forEach(function (w, j) {
    if (j) host.appendChild(document.createTextNode(' '));
    var s = document.createElement('span');
    s.className = '{{ID}}-w';
    s.id = '{{ID}}-w' + li + '-' + j;
    s.textContent = w[0];
    host.appendChild(s);
  });
});
var band = $('#{{ID}}-band'), dk = $('#{{ID}}-dk0'), NK = GEN.open + (PAYOFF.length ? GEN.pay : 0);
for (var f = 1; f < NK; f++) { var cp = dk.cloneNode(true); cp.id = '{{ID}}-dk' + f; band.appendChild(cp); }
$$('#{{ID}} .{{ID}}-dk').forEach(function (e, k) {
  e.style.webkitMaskSize = e.style.maskSize = (COLS * 1080) + 'px auto';
  e.style.webkitMaskPosition = e.style.maskPosition = (-(k % COLS) * 1080) + 'px ' + (-Math.floor(k / COLS) * BAND) + 'px';
});
$$('#{{ID}} .{{ID}}-t, #{{ID}} .{{ID}}-w, #{{ID}} .{{ID}}-p1, #{{ID}} .{{ID}}-p2, #{{ID}} .{{ID}}-n, #{{ID}} .{{ID}}-tab').forEach(function (e) {
  e.setAttribute('data-layout-allow-overlap', '');
  e.setAttribute('data-layout-allow-occlusion', '');
});

// ---- every line keeps its fx.html size as a maximum and only shrinks to fit the frame with the pack's faces
var FIT = [['.{{ID}}-o1', 920], ['.{{ID}}-o2', 920], ['.{{ID}}-py', 920], ['.{{ID}}-tl', 960]];
function fit() {
  FIT.forEach(function (fv) {
    $$('#{{ID}} ' + fv[0]).forEach(function (box) {
      if (!box.dataset.max) box.dataset.max = parseFloat(getComputedStyle(box).fontSize);
      var max = +box.dataset.max, inner = box.querySelector('.{{ID}}-t'), ws = box.querySelectorAll('.{{ID}}-w');
      box.style.fontSize = max + 'px';
      var w = inner ? inner.offsetWidth : ws.length ? ws[ws.length - 1].offsetLeft + ws[ws.length - 1].offsetWidth - ws[0].offsetLeft : 0;
      if (w > fv[1]) box.style.fontSize = (max * fv[1] / w).toFixed(2) + 'px';
    });
  });
}
fit();
if (document.fonts && document.fonts.load) {
  var all = OPEN.concat(PAYOFF.map(function (p) { return p[0]; })).concat([].concat.apply([], TITLE).map(function (w) { return w[0]; })).join(' ');
  Promise.all([tok('--display-style') + ' ' + tok('--display-weight') + ' 100px ' + tok('--font-display'),
    '500 30px ' + tok('--font-mono')].map(function (fn) { return document.fonts.load(fn, all + ' 0123456789').catch(function () {}); }))
    .then(fit, fit);
  document.fonts.ready.then(fit);
}

// ---- build-time state (a set at time 0 does not render on a seek to 0)
if (q(A) <= 0) gsap.set('#{{ID}}', { opacity: 1 });
gsap.set(['#{{ID}}-field', '#{{ID}}-sheet', '#{{ID}}-cur'], { opacity: 0 });
gsap.set('#{{ID}} .{{ID}}-im, #{{ID}} .{{ID}}-tab', { opacity: 0 });
gsap.set('#{{ID}} .{{ID}}-cell', { opacity: 0 });
gsap.set('#{{ID}} .{{ID}}-w', { yPercent: 105 });
gsap.set('#{{ID}}-live', { transformOrigin: '0px 0px', x: 0, y: 0, scale: 1, clipPath: 'inset(0px 0px 0px 0px)' });
gsap.set('#{{ID}}-sheet', { transformOrigin: '0px 0px', x: 0, y: 0, scale: 1 });
gsap.set('#{{ID}} .{{ID}}-py', { opacity: 0 });

// ---- the ink copies: copy k shows on its masked frame (opener frames from A, payoff frames from the drop)
gsap.set('#{{ID}} .{{ID}}-dk', { opacity: 0 });
for (var k = 0; k < NK; k++) {
  var fk = k < GEN.open ? FA + k : GEN.drop + (k - GEN.open);
  if (fk === FA) gsap.set('#{{ID}}-dk' + k, { opacity: 1 });
  else on('#{{ID}}-dk' + k, fk / 30);
  off('#{{ID}}-dk' + k, (fk + 1) / 30);
}

// ---- frame 0 to the shrink: the opener over the live shot (the thumbnail)
tl.fromTo('#{{ID}} .{{ID}}-op', { scale: 1.03 }, { scale: 1, duration: 0.5, ease: 'power2.out', immediateRender: q(A) <= 0 }, q(A));
off('#{{ID}} .{{ID}}-op', tShrink);

// ---- the shrink: the shot into cell 01, the sheet around it, cells settling in from cell 01 outward
on('#{{ID}}-field', tShrink); on('#{{ID}}-sheet', tShrink);
tl.fromTo('#{{ID}}-live', { x: 0, y: 0, scale: 1, clipPath: 'inset(0px 0px 0px 0px)' },
  { x: cx(0), y: cy(0) - CROP.top * S, scale: S, clipPath: 'inset(' + CROP.top + 'px 0px ' + CROP.bottom + 'px 0px)',
    duration: T.shrink, ease: 'expo.inOut', immediateRender: false }, q(tShrink));
tl.set('#{{ID}}-c0', { opacity: 1 }, q(tShrink));
for (i = 1; i < 30; i++) {
  var d = Math.sqrt(Math.pow(i % 6, 2) + Math.pow(Math.floor(i / 6), 2));
  tl.fromTo('#{{ID}}-c' + i, { opacity: 0, scale: 0.86 }, { opacity: 1, scale: 1, duration: 0.22, ease: 'power3.out', immediateRender: false },
    q(tShrink + T.settle + d * T.ring));
}

// ---- the title: word by word up through the line mask; a new line pushes the last one out on its first word
var prev = tShrink;
TITLE.slice(0, 2).forEach(function (line, li) {
  line.forEach(function (w, j) {
    var t = w[1] ? wordAt(w[1], prev) : null;
    t = (t === null || t >= tDrop) ? prev + (li || j ? 0.25 : 0.06) : t;
    if (li && !j) {
      tl.fromTo('#{{ID}}-ta .{{ID}}-w', { yPercent: 0 }, { yPercent: -105, duration: T.push, ease: 'expo.out', immediateRender: false }, q(t));
    }
    tl.fromTo('#{{ID}}-w' + li + '-' + j, { yPercent: 105 }, { yPercent: 0, duration: T.rise, ease: 'expo.out', immediateRender: false }, q(t));
    prev = t;
  });
});

// ---- the second: one cell exposes per frame (its still is the frame playing), the cursor walks the sheet
off('#{{ID}}-live', RUN / 30);
on('#{{ID}}-cur', RUN / 30);
for (k = 0; k < 30; k++) {
  var tk = (RUN + k) / 30;
  tl.set(['#{{ID}}-i' + k, '#{{ID}}-c' + k + ' .{{ID}}-tab'], { opacity: 1 }, q(tk));
  tl.set('#{{ID}}-c' + k + ' .{{ID}}-n', { opacity: 0 }, q(tk));
  tl.set('#{{ID}}-cur', { x: (k % 6) * (CW + GX), y: Math.floor(k / 6) * (CH + GY) }, q(tk));
}

// ---- the last cell: the live copy takes it over and the sheet dives into it, full frame on the drop
var L = 29, TL0 = (RUN + 29) / 30, Z = 1 / S;
tl.set('#{{ID}}-live', { opacity: 1, x: cx(L), y: cy(L) - CROP.top * S }, q(TL0));
off('#{{ID}}-cur', TL0 + 1 / 30);
tl.fromTo('#{{ID}}-sheet', { x: 0, y: 0, scale: 1 }, { x: -cx(L) * Z, y: CROP.top - cy(L) * Z, scale: Z, duration: tDrop - TL0,
  ease: 'power2.in', immediateRender: false }, q(TL0));
tl.fromTo('#{{ID}}-live', { clipPath: 'inset(' + CROP.top + 'px 0px ' + CROP.bottom + 'px 0px)' }, { clipPath: 'inset(0px 0px 0px 0px)',
  duration: tDrop - TL0, ease: 'power2.in', immediateRender: false }, q(TL0));
off('#{{ID}}-field', tDrop); off('#{{ID}}-sheet', tDrop);

// ---- the payoff over the live shot: the first word slams in alone, centred and larger; the second lands in the
// accent on its word as the first settles and slides over (offsets measured when the tween first renders, after
// the pack's faces have loaded)
if (PAYOFF.length) {
  on('#{{ID}} .{{ID}}-py', tDrop);
  var two = PAYOFF.length > 1;
  var alone = function (i, e) {                     // the first word centred alone: half the room the second takes
    if (!two) return 0;
    var p2 = e.parentNode.querySelector('.{{ID}}-p2');
    return (p2.offsetLeft + p2.offsetWidth - e.offsetLeft - e.offsetWidth) / 2;
  };
  var big = function (i, e) { return Math.min(1.33, 920 / Math.max(1, e.offsetWidth)); };
  var big13 = function (i, e) { return big(i, e) * 1.3; };
  gsap.set('#{{ID}} .{{ID}}-p2', { opacity: 0 });
  tl.fromTo('#{{ID}} .{{ID}}-p1', { x: alone, scale: big13 }, { x: alone, scale: big, duration: T.slam, ease: 'power4.out', immediateRender: false }, q(tDrop));
  if (two) {
    var t2 = PAYOFF[1][1] ? wordAt(PAYOFF[1][1], tDrop) : null;
    t2 = (t2 === null || t2 >= B) ? tDrop + 0.3 : t2;
    tl.fromTo('#{{ID}} .{{ID}}-p1', { x: alone, scale: big }, { x: 0, scale: 1, duration: 0.2, ease: 'expo.out', immediateRender: false }, q(t2));
    tl.set('#{{ID}} .{{ID}}-p2', { opacity: 1 }, q(t2));
    tl.fromTo('#{{ID}} .{{ID}}-p2', { scale: 1.36 }, { scale: 1, duration: 0.2, ease: 'power4.out', immediateRender: false }, q(t2));
  }
}
