// picture-dive (layer: cam). "The one you're watching right now": the video becomes a framed picture on the wall
// behind the speaker, a picture of itself, four levels deep, and then the camera dives past the speaker into it.
//   LEVELS     one level per word: the live frame (a synced copy, so it starts invisible on top of its parent)
//              shrinks into the picture on the wall behind the speaker, with a light frame line; each inner level
//              is the same again inside the one before, so every inner speaker stands in front of their own picture
//   DIVE_ON    the dive: the picture grows to fill the frame, accelerating, while the speaker in front sweeps past
//              the camera faster (parallax, never a double exposure: the plate behind is only uncovered where the
//              picture already covers it); it fills the frame on the last frame. If B is a picture cut, it fills
//              the frame 6 frames early and keeps pushing gently (PUSH) into the cut.
// Reach for it when the line says "the one you're watching right now", "exactly what you're seeing", recursion.
// Supply: nothing but the picture's place, measured on a still of the shot (PIC): a spot on the wall beside the
// head that the head overlaps a little. Every level is a synced copy of clean.mp4 and subject.webm in the live
// grade. It carries its own cutout, so it needs no CUT_WINDOWS entry (it works with one too).
// Change only these constants:
var LEVELS = ['the', 'one', "you're", 'watching'];   // the word each level shrinks in on (null = GAP after the one before)
var DIVE_ON = 'right';                       // the dive into the picture starts on this word
var T = { levels: [0.10, 0.37, 0.63, 0.90], dive: 1.17, gap: 0.27 };   // fallbacks, s after A
var PIC = [560, 240, 480];                   // the picture on the wall: left, top, width (px on 1080x1920; 9:16)
var LINE = [6.0, 4.2, 3.0, 2.2];             // each level's frame line on screen (px)
var PUSH = 1.12;                             // how far it keeps pushing after it fills the frame, when B is a cut

var FPS = 30;
function fq(i) { return Math.max(0, i / FPS - 0.002); }
function fi(t) { return Math.round(t * FPS); }
function cue(w, fb, after) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }
var S = PIC[2] / 1080, PX = PIC[0] / (1 - S), PY = PIC[1] / (1 - S);   // each level S of its parent, about (PX, PY)
var ORIGIN = PX + 'px ' + PY + 'px';
var LV = [null, { d: 0.46, ease: 'expo.out' }, { d: 0.26, ease: 'power4.out' }, { d: 0.24, ease: 'power4.out' }, { d: 0.18, ease: 'power4.out' }];

// ---- the levels, one per word
var lv = [], prev = A;
for (var k = 1; k <= 4; k++) {
  var w = LEVELS[k - 1];
  lv[k] = w ? cue(w, T.levels[k - 1], prev + (k > 1 ? 0.01 : 0)) : prev + T.gap;
  prev = lv[k];
}
for (var k = 1; k <= 4; k++) {
  var L = LV[k], par = Math.pow(S, k - 1), own = Math.pow(S, k);
  gsap.set('#{{ID}}-n' + k, { opacity: 0, scale: 1, transformOrigin: ORIGIN });
  gsap.set('#{{ID}}-f' + k, { borderWidth: LINE[k - 1] / par });
  tl.set('#{{ID}}-n' + k, { opacity: 1 }, q(lv[k]));
  // it starts exactly on its parent (same footage, same frame, under the same cutout: invisible) and shrinks into place
  tl.fromTo('#{{ID}}-n' + k, { scale: 1 }, { scale: S, duration: L.d, ease: L.ease, immediateRender: false }, q(lv[k]));
  tl.fromTo('#{{ID}}-f' + k, { borderWidth: LINE[k - 1] / par }, { borderWidth: LINE[k - 1] / own, duration: L.d, ease: L.ease, immediateRender: false }, q(lv[k]));
}

// ---- the dive. The picture (level 1) grows about its point from S to the full frame at F1, its right edge easing
// onto the frame's edge; the speaker (c0) holds until W, then scales about the same point faster than the picture
// (foreground parallax) and sweeps out of frame, gone by F1.
var cutAtB = CUTS.some(function (c) { return Math.abs(c - B) < 0.02; });
var Z0 = fi(Math.max(cue(DIVE_ON, T.dive, prev + 0.01), lv[4] + 0.15)), ZE = fi(B) - 1;
var F1 = cutAtB ? Math.max(Z0 + 4, ZE - 6) : ZE, W = Math.max(Z0, F1 - 8);
var K = [1.0, 1.22, 1.5, 1.85, 2.2, 2.8, 3.6, 4.6, 5.8];             // the speaker's scale, frame by frame from W
gsap.set('#{{ID}}-c0', { transformOrigin: ORIGIN });
for (var f = W; f <= Math.min(F1, W + K.length - 1); f++) tl.set('#{{ID}}-c0', { scale: K[f - W] }, fq(f));
tl.set('#{{ID}}-c0', { opacity: 0 }, fq(Math.min(F1, W + K.length)));

for (var j = Z0; j <= ZE; j++) {
  var s1, ez;
  if (j <= F1) { var pz = (j - Z0) / Math.max(1, F1 - Z0); ez = pz * pz; s1 = S * Math.pow(1 / S, ez); }
  else { ez = 1; s1 = 1 + (PUSH - 1) * (j - F1) / Math.max(1, ZE - F1); }
  var r = Math.min(1, (j - Z0) / Math.max(1, W - Z0)), rr = r * r * (3 - 2 * r);
  tl.set('#{{ID}}-n1', { scale: s1, x: rr * (1080 - PX) * Math.max(0, 1 - s1) }, fq(j));
  // each level's frame line slides to the next level's weight as the picture comes up to full frame
  for (var m = 1; m <= 4; m++) {
    var target = m === 1 ? LINE[0] * (1 - ez) : LINE[m - 1] + (LINE[m - 2] - LINE[m - 1]) * ez;
    tl.set('#{{ID}}-f' + m, { borderWidth: target / (s1 * Math.pow(S, m - 1)) }, fq(j));
  }
}
