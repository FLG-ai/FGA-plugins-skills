/* film-look (layer: cam). The line asks for film and the whole frame becomes film, only on that line.
   Beat by beat:
     A           nothing yet: the gate is closed, the picture is the video's own look
     WIPE_ON     a hard wipe, left to right, a light edge riding it, carries a film-graded copy of the footage across
                 the full frame (no bars), eased in and out, done on LAND_ON
     LAND_ON     the wipe lands, the edge goes, the copy punches 1.04 to 1 and settles (0.3 s)
     hold        film grain moved every frame and a 1-2 px gate weave, under the film look (deep blacks, more
                 contrast, less saturation, teal shadows, warm highlights) and a soft vignette
     B           a hard return to the video's own look: end the window on the end of the line (never let it bleed)
   Reach for it on "cinematic", "make it look like film", "the whole scene changes", only on that line.
   Supply: nothing. grain.png is self-made by make_grain.py (rerun it to rebuild the file). The copy of the footage
   in fx.html is timed by the build from the FX entry, so the effect works wherever it sits.
   Sound: a whoosh on the wipe (WIPE_ON), a low hit on the land (LAND_ON).
   Change only these constants: */
var WIPE_ON = 'scene';              // the wipe starts on this spoken word
var LAND_ON = 'changes';            // and lands on this one (the punch-in)
var AT = { wipe: 0.75, land: 1.07 };   // fallbacks (s after A) when a word isn't found
var WIPE = [4, 14];                 // the wipe takes the frames between the two words, at least / at most this many
var LOOK = 'sepia(0.04) contrast(1.36) saturate(0.74) brightness(0.98)';   // the film look on the copy (CSS filter)
var TONE = {                        // the split tone after it: output level at input 0, .25, .5, .75, 1 per channel
  r: [0, 0.155, 0.374, 0.655, 1],   //   red lifted in the highlights
  g: [0, 0.187, 0.402, 0.647, 0.92],
  b: [0, 0.179, 0.376, 0.589, 0.82] //   blue kept in the shadows, pulled in the highlights: teal low, warm high
};
var PUNCH = 1.04;                   // the copy's scale on the land, settling to 1
var GRAIN = 0.26;                   // grain strength (opacity of the overlay)
var WEAVE = [2, 4];                 // gate weave, px peak to peak: x, y

var FPS = 30;
function fq(f) { return Math.max(0, f / FPS - 0.002); }
function e2io(p) { return p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2; }
function rnd(i) { var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }
function find(word, after, fallback) {
  var w = word ? wordAt(word, after) : null;
  return (w === null || w >= B) ? A + fallback : w;
}
['r', 'g', 'b'].forEach(function (c) {
  document.getElementById('{{ID}}-t' + c).setAttribute('tableValues', TONE[c].join(' '));
});

var tWipe = find(WIPE_ON, A, AT.wipe), tLand = find(LAND_ON, tWipe + 0.01, AT.land);
var fW = Math.round(tWipe * FPS), fB = Math.round(B * FPS);
var N = Math.max(WIPE[0], Math.min(WIPE[1], Math.round(tLand * FPS) - fW));
var fL = fW + N;                                                  // the frame the wipe has covered everything
// the copy's last frame: the build sizes it in whole frames, so on a window that ends mid-frame it can stop a frame
// before the wrapper does; the hard return happens there instead of showing a frame of nothing
var fEnd = Math.min(fB, Math.round(A * FPS) + Math.floor((B - A) * FPS + 1e-6));

gsap.set('#{{ID}}-v', { filter: LOOK + ' url(#{{ID}}-tone)', transformOrigin: '540px 900px' });
gsap.set('#{{ID}}-gate', { scale: 1.008, transformOrigin: '540px 960px' });   // covers the weave's edge
gsap.set('#{{ID}}-grain', { opacity: GRAIN });
gsap.set('#{{ID}}-edge', { opacity: 0 });
gsap.set('#{{ID}}-gate', { clipPath: 'inset(0px 1080px 0px 0px)' });

// the wipe: per frame, so the clip edge and the light edge are always the same pixel column
tl.set('#{{ID}}-edge', { opacity: 1 }, fq(fW));
for (var i = 0; i < N; i++) {
  var x = 1080 * e2io((i + 1) / (N + 1));
  tl.set('#{{ID}}-gate', { clipPath: 'inset(0px ' + (1080 - x).toFixed(1) + 'px 0px 0px)' }, fq(fW + i));
  tl.set('#{{ID}}-edge', { x: x }, fq(fW + i));
}
tl.set('#{{ID}}-gate', { clipPath: 'inset(0px 0px 0px 0px)' }, fq(fL));
tl.set('#{{ID}}-edge', { opacity: 0 }, fq(fL));
tl.fromTo('#{{ID}}-v', { scale: PUNCH }, { scale: 1, duration: 0.3, ease: 'power3.out', immediateRender: false }, fq(fL));

// grain and the gate weave, a new seeded offset every frame until B
tl.set('#{{ID}}-gate', { opacity: 0 }, fq(fEnd));
for (var f = fW; f < fEnd; f++) {
  tl.set('#{{ID}}-gt', { x: -Math.floor(rnd(f) * 512), y: -Math.floor(rnd(f + 977) * 512) }, fq(f));
  tl.set('#{{ID}}-gate', { x: Math.round((rnd(f + 31) - 0.5) * WEAVE[0]), y: Math.round((rnd(f + 57) - 0.5) * WEAVE[1]) }, fq(f));
}
