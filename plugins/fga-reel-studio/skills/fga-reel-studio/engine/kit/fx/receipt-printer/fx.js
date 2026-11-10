// receipt-printer, the motif (layer: top). The instruction the speaker gives the AI prints on a receipt:
//   A         a slim printer bar drops into place above the head (its light comes on)
//   HEAD_ON   the header feeds up out of the slot (INSTRUCTION 01, the time stamp, who it went to)
//   LINES     each line of the instruction feeds up on its spoken word, in mono caps, in stepper-motor jumps
//             (the bar shivers, the light flickers while it prints)
//   TOTAL_ON  the TOTAL line feeds out ('' = it comes out with the last line)
//   TEAR_ON   the bar tugs, the receipt rips off the slot (the torn stub stays) and flies out top right
//   B - out   the printer lifts away with its stub, gone at B
// Reach for it every time the speaker says what they told the AI to do (the prompt-bar alternative). It is a motif:
// same size, same place (centred on x 540), same move every time, 3 or 4 times a video.
// Supply: nothing, it is all type and tokens. gen.py writes one fx/<id>/ folder per appearance from one BEATS table
// (PY fx/receipt-printer/gen.py <project>; --check prints when each beat lands); rerun it when the cut moves.
// Change only these constants: the block gen.py rewrites (per appearance), then the shared ones under it (the same
// in every appearance: change them in the library copy before running gen.py). A cue word finds the first matching
// spoken word at or after the previous beat (wordAt); when one is missing, its fallback in T (s after A) is used.

// ---- constants: gen.py rewrites the lines between these two markers ----
var NUM = 1;   // the receipt's number in the header (01, 02, ...)
var LINES = [["CUT THE PAUSES,", "typed"], ["ADD CAPTIONS.", "one"]];   // [text, the spoken word it prints on]; 1 to 3 lines
var HEAD_ON = "I";   // the header feeds out on this word
var TOTAL_ON = "sentence";   // the TOTAL line feeds out on this word; '' = with the last line
var TEAR_ON = "done";   // the receipt tears off on this word
// ---- end of constants ----

var HEADER = ['INSTRUCTION', 'TO THE AI'];  // the header: left of line one, right of line two (line two's left is the time stamp)
var TOTAL = ['TOTAL', '1 SENTENCE'];         // the last line: left, right
var SLOT = 550;                              // frame px: the slot line. Measure it on the shot: the bar (SLOT - 14 to
                                             // SLOT + 38) sits just above the top of the head, the paper rises 1.3x its
                                             // height above it, so keep SLOT - 1.3 * (160 + 48 * lines) under y 220
var SCALE = 1.3;                             // the whole component, about the slot line at x 540
var T = { head: 0.06, lines: [0.30, 0.55, 0.80], total: 1.00, tear: 0.50, out: 0.20 };   // fallbacks; tear and out: s before B

var R = '#{{ID}} ', BAR = R + '.rc-bar', FLY = R + '.rc-fly';
var LINE0 = 88, LH = 48, JAG = 10, STEP = 0.034;
function $(s) { return document.querySelector(s); }
function rnd(i) { var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }
function word(w, after, fallback) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? fallback : t; }

// ---- times, each on its word
var OUT = B - T.out;
var tHead = Math.max(A + 0.04, word(HEAD_ON, A, A + T.head));
var tLines = [], prev = tHead + 0.01;
LINES.forEach(function (l, i) {
  var t = word(l[1], prev, A + (T.lines[i] !== undefined ? T.lines[i] : T.lines[T.lines.length - 1] + 0.25 * i));
  tLines.push(t); prev = t + 0.01;
});
var tTotal = TOTAL_ON ? word(TOTAL_ON, prev, A + T.total) : null;
var tTear = Math.min(word(TEAR_ON, prev, B - T.tear), B - 0.30);   // the strip is gone (0.28 s) by B

// ---- the paper: its lines, height, torn edges (seeded per receipt, so each one tears differently)
var n = LINES.length, H = LINE0 + LH * n + 6 + 10 + 36 + 10 + JAG;
function zig(seed) {
  var pts = [];
  for (var k = 0; k <= 22; k++) {
    var x = k * 100 / 22 + (k === 0 || k === 22 ? 0 : (rnd(seed + k) - 0.5) * 2.2);
    var d = k % 2 === 0 ? 0.15 + 0.25 * rnd(seed + 40 + k) : 0.75 + 0.25 * rnd(seed + 80 + k);
    pts.push([x.toFixed(2), d]);
  }
  return pts;
}
var top = zig(NUM * 97), bot = zig(NUM * 97 + 500);
var clip = top.map(function (p) { return p[0] + '% ' + (p[1] * JAG).toFixed(2) + 'px'; })
  .concat(bot.slice().reverse().map(function (p) { return p[0] + '% ' + (H - (1 - p[1]) * JAG).toFixed(2) + 'px'; }));
var stub = bot.map(function (p) { return p[0] + '% ' + (p[1] * JAG).toFixed(2) + 'px'; }).concat(['100% 30px', '0% 30px']);
function pad(v) { return (v < 10 ? '0' : '') + v; }
var ts = tLines[0], stamp = pad(Math.floor(ts / 60)) + ':' + pad(Math.floor(ts % 60)) + '.' + pad(Math.floor((ts % 1) * 100));
(function () {
  var box = $(R + '.rc-lines');
  if (box.childNodes.length) return;
  LINES.forEach(function (l, i) {
    var d = document.createElement('div');
    d.className = 'rc-line';
    d.style.top = (LINE0 + LH * i) + 'px';
    d.textContent = l[0];
    box.appendChild(d);
  });
  $(R + '.rc-k1').textContent = HEADER[0];
  $(R + '.rc-k2').textContent = HEADER[1];
  $(R + '.rc-num').textContent = pad(NUM);
  $(R + '.rc-stamp').textContent = stamp;
  $(R + '.rc-k3').textContent = TOTAL[0];
  $(R + '.rc-k4').textContent = TOTAL[1];
  $(R + '.rc-dots').style.top = (LINE0 + LH * n + 6) + 'px';
  $(R + '.rc-total').style.top = (LINE0 + LH * n + 16) + 'px';
  [$(FLY), $(R + '.rc-paper')].forEach(function (e) { e.style.height = H + 'px'; });
  var teeth = 'M0 5';
  for (var x = 0; x < 432; x += 8) teeth += ' L' + (x + 4) + ' 1 L' + (x + 8) + ' 5';
  $(R + '.rc-tp').setAttribute('d', teeth + ' Z');
})();

// ---- the feeds: how far the paper has come out of the slot at each beat
var stops = [[tHead, 84]];
LINES.forEach(function (l, i) { stops.push([tLines[i], LINE0 + LH * (i + 1) + 2]); });
if (tTotal === null) stops[stops.length - 1][1] = H - JAG - 2;     // the last line and the TOTAL in one feed
else stops.push([tTotal, H - JAG - 2]);
var FEEDS = [], cur = 0, tcur = 0;
stops.forEach(function (s) {
  var dist = s[1] - cur, k = Math.max(2, Math.min(4, Math.round(dist / 24))), t = Math.max(s[0], tcur + 0.02), ys = [];
  for (var j = 0; j < k; j++) ys.push(-(cur + dist * (j + 1) / k));
  FEEDS.push([t, ys]);
  tcur = t + k * STEP; cur = s[1];
});
tTear = Math.max(tTear, tcur);

// ---- build
gsap.set(R + '.rc-root', { y: SLOT, scale: SCALE, transformOrigin: '540px 0px' });   // centred on x 540
gsap.set(R + '.rc-paper', { clipPath: 'polygon(' + clip.join(', ') + ')' });
gsap.set(R + '.rc-stub', { clipPath: 'polygon(' + stub.join(', ') + ')', opacity: 0 });
gsap.set(BAR, { opacity: 0, y: -22 });
gsap.set(FLY, { y: 0, x: 0, rotation: 0, rotationX: 0, transformPerspective: 900, transformOrigin: '50% 100%' });
gsap.set(R + '.rc-led', { opacity: 0.35 });
// in: the printer drops into place
tl.fromTo(BAR, { y: -22 }, { y: 0, duration: 0.24, ease: 'power3.out', immediateRender: false }, q(A));
tl.fromTo(BAR, { opacity: 0 }, { opacity: 1, duration: 0.08, ease: 'none', immediateRender: false }, q(A));
tl.set(R + '.rc-led', { opacity: 1 }, q(A + 0.20));
// feeds: the paper steps up out of the slot in stepper-motor jumps (each step a quick ease, a small settle at the end);
// the bar shivers 1px while it prints, the light flickers
FEEDS.forEach(function (f) {
  var t = f[0], ys = f[1], te = t + ys.length * STEP, last = ys[ys.length - 1];
  ys.forEach(function (y, i) { tl.to(FLY, { y: y, duration: 0.026, ease: 'power2.out' }, q(t + i * STEP) + 0.001); });
  tl.to(FLY, { y: last + 1.5, duration: 0.03, ease: 'power1.out' }, q(te) + 0.001);
  tl.to(FLY, { y: last, duration: 0.05, ease: 'power1.inOut' }, q(te + STEP) + 0.001);
  tl.to(BAR, { y: 1, duration: 0.03, ease: 'none' }, q(t) + 0.001);
  tl.to(BAR, { y: 0, duration: 0.05, ease: 'power1.out' }, q(te));
  tl.set(R + '.rc-led', { opacity: 0.35 }, q(t));
  tl.set(R + '.rc-led', { opacity: 1 }, q(te));
});
// tear: the bar tugs down, the strip rips up off the slot (the torn stub stays), tips back and flies out top right
var Y = -cur;
tl.to(BAR, { y: 4, duration: 0.05, ease: 'power2.out' }, q(tTear));
tl.to(BAR, { y: 0, duration: 0.22, ease: 'back.out(2)' }, q(tTear + 0.05));
tl.set(R + '.rc-stub', { opacity: 1 }, q(tTear));
tl.to(FLY, { y: Y - 20, rotation: -2.5, duration: 0.06, ease: 'power3.out' }, q(tTear));
tl.to(FLY, { x: 300, y: Y - 820, rotation: 16, rotationX: 48, duration: 0.22, ease: 'power2.in' }, q(tTear + 0.06));
// out: the printer lifts away with the stub in its slot, gone at B
tl.to(BAR, { opacity: 0, y: -18, duration: 0.18, ease: 'power2.in' }, q(OUT));
tl.to(R + '.rc-stub', { opacity: 0, y: -18, duration: 0.18, ease: 'power2.in' }, q(OUT));
