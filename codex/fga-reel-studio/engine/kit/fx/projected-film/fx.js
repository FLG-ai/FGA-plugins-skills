/* projected-film (layer: cam). The shot becomes projected film for one line.
   Beat by beat:
     A           nothing yet: the video's own look
     IN_ON word  35mm rails slide in from the left and right edges (0.22 s, power3.out) and the picture becomes film:
                 a 15 fps step print (each frame held for 2, never more than one frame behind the voice), a print-film
                 look with an exposure flicker per film frame, a teal/warm split tone, grain, a 1-2 px gate weave,
                 a scratch wandering along one line and a few dust specks, one film frame each. The rails scroll with
                 the film at its cadence: perforations, the voice as a variable-area soundtrack, real edge codes
     ROLL_ON     the loop slips: the picture rolls down one frame, frame line and all, in 6 frames, then locks
     B           gone, straight back to the video's own look: end the window on the next line
   Reach for it on "cinematic", "like a movie", "the whole scene changes", "old film".
   Supply: nothing by hand. fx.html is written by gen.py from the window, the voice and the frame numbers:
     PY fx/<id>/gen.py <project> [<id>]     (rerun it after the mix, or whenever the window or the cut moves)
   grain.png is self-made by make_grain.py.
   Sound: a projector start under the rails (IN_ON: clicks-run), a whoosh-soft on the roll (ROLL_ON).
   Change only these constants: */
var IN_ON = 'make';                 // the rails slide in and the film starts on this spoken word
var ROLL_ON = 'cinematic';          // the loop slips on this one ('' = no slip)
var AT = { in: 0.10, roll: 1.45 };  // fallbacks (s after A) when a word isn't found
var LOOK = 'sepia(0.04) contrast(1.42) saturate(0.8)';   // the print look (CSS filter); the flicker adds brightness
var EXPOSE = 0.965;                 // the print's brightness, flickering FLICKER either side per film frame
var FLICKER = 0.035;
var TONE = {                        // the split tone after it: output level at input 0, .25, .5, .75, 1 per channel
  r: [0, 0.113, 0.317, 0.613, 1],   //   teal in the shadows, warm in the highlights
  g: [0, 0.161, 0.372, 0.633, 0.945],
  b: [0, 0.173, 0.381, 0.622, 0.897]
};
var WEAVE = [3, 5];                 // gate weave, px peak to peak: x, y
var SCRATCH_X = 868;                // the scratch's line (px on 1080)
var DUST = [[0, 1], [1, 4], [2, 9], [3, 13], [0, 17], [2, 20]];   // [speck 0-3, film frame after IN] one film frame each

var FPS = 30;
function rnd(i) { var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }
function fq(f) { return Math.max(0, f / FPS - 0.002); }
function find(word, after, fallback) {
  var w = word ? wordAt(word, after) : null;
  return (w === null || w >= B) ? A + fallback : w;
}
function look(b) { return LOOK + ' brightness(' + b.toFixed(3) + ') url(#{{ID}}-tone)'; }
['r', 'g', 'b'].forEach(function (c) {
  document.getElementById('{{ID}}-t' + c).setAttribute('tableValues', TONE[c].join(' '));
});
var strip = document.getElementById('{{ID}}-ls');
var OY0 = +strip.getAttribute('data-oy0'), STEP = +strip.getAttribute('data-step');   // written by gen.py

var fA = Math.round(A * FPS), fB = Math.round(B * FPS);
var fIn = Math.max(fA, Math.round(find(IN_ON, A, AT.in) * FPS));
var tRoll = ROLL_ON ? find(ROLL_ON, fIn / FPS + 0.05, AT.roll) : null;
var fRoll = tRoll === null ? -1 : Math.round(tRoll * FPS);
// the copies are sized in whole frames by the build: on a window that ends mid-frame they stop a frame early
var fEnd = Math.min(fB, fA + Math.floor((B - A) * FPS + 1e-6));

gsap.set('#{{ID}}-weave', { opacity: 0, scale: 1.012, transformOrigin: '540px 960px' });
gsap.set('#{{ID}}-rl', { x: -130 });
gsap.set('#{{ID}}-rr', { x: 104 });
gsap.set('#{{ID}}-v1', { opacity: 0 });
gsap.set(['#{{ID}}-ls', '#{{ID}}-rs'], { y: OY0 });
gsap.set('#{{ID}}-roll', { y: 0, filter: look(EXPOSE) });

tl.set('#{{ID}}-weave', { opacity: 1 }, fq(fIn));
tl.fromTo('#{{ID}}-rl', { x: -130 }, { x: 0, duration: 0.22, ease: 'power3.out', immediateRender: false }, fq(fIn));
tl.fromTo('#{{ID}}-rr', { x: 104 }, { x: 0, duration: 0.22, ease: 'power3.out', immediateRender: false }, fq(fIn));
tl.set('#{{ID}}-weave', { opacity: 0 }, fq(fEnd));

// every output frame: the step print (the one-frame-late copy shows on odd frames = each film frame held 2).
// every film frame (2 output frames, counted from A like the strip in gen.py): strip advance, grain, weave,
// exposure flicker, the scratch
for (var f = fIn; f < fEnd; f++) {
  var i = f - fA, k = Math.floor(i / 2), t = fq(f);
  tl.set('#{{ID}}-v1', { opacity: i % 2 ? 1 : 0 }, t);
  if (i % 2 && f !== fIn) continue;
  tl.set('#{{ID}}-roll', { filter: look(EXPOSE + (rnd(k + 211) - 0.5) * 2 * FLICKER) }, t);
  tl.set(['#{{ID}}-ls', '#{{ID}}-rs'], { y: OY0 + STEP * k }, t);
  tl.set('#{{ID}}-gt', { x: -Math.floor(rnd(k + 5) * 512), y: -Math.floor(rnd(k + 977) * 512) }, t);
  tl.set('#{{ID}}-weave', { x: Math.round((rnd(k + 31) - 0.5) * WEAVE[0]), y: Math.round((rnd(k + 57) - 0.5) * WEAVE[1]) }, t);
  var sc = rnd(k + 401) > 0.45;                                     // a scratch that wanders along one line
  tl.set('#{{ID}}-scratch', { opacity: sc ? 0.16 + rnd(k + 7) * 0.12 : 0, x: SCRATCH_X + Math.round((rnd(k + 91) - 0.5) * 10) }, t);
}
DUST.forEach(function (d, n) {                                      // one film frame each, then gone
  var f0 = fIn + d[1] * 2;
  if (f0 + 2 > fEnd) return;
  tl.set('#{{ID}}-dust' + d[0], { opacity: 0.75, x: 140 + Math.round(rnd(n + 3) * 760), y: 260 + Math.round(rnd(n + 13) * 1180),
    rotation: Math.round(rnd(n + 23) * 360), scale: 0.6 + rnd(n + 33) * 0.7 }, fq(f0));
  tl.set('#{{ID}}-dust' + d[0], { opacity: 0 }, fq(f0 + 2));
});

// the loop slips: the picture rolls down one frame, frame line and all, then locks
if (fRoll > fIn && fRoll + 6 < fEnd) {
  [0.06, 0.2, 0.44, 0.7, 0.88, 0.97].forEach(function (p, n) {
    tl.set('#{{ID}}-roll', { y: Math.round(1964 * p) }, fq(fRoll + n));
  });
  tl.set('#{{ID}}-roll', { y: 0 }, fq(fRoll + 6));
}
