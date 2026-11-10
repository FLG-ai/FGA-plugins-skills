# the rig's JavaScript, filled in by gen.py. Every value below is a function of time, so the move has real inertia.
# __ID__ is the effect's id; T, POSE, Z come from gen.py (the window and the cue words); PASS is the sub-frame offset of
# this shutter pass (prerender.py sets it).
JS = r"""// layer-explode rig. PASS is the sub-frame offset of this shutter pass (prerender.py sets it)
var T = __T__;
var POSE = __POSE__;              // the exploded pose
var Z = __Z__;                    // plane depths at full separation
var LINES = __LINES__, BARS = __BARS__, WAVE = __WAVE__;
var K = __SPEED__, KP = K * K, DS = __DS__;   // spring rates for a shorter window, tween length scale
var LIGHT = '__LIGHT__', LIT = '__LIT__', HAS_EMPTY = __HAS_EMPTY__, NW = __NW__;
var PASS = 0 /*__PASS__*/;
var FOLD = T.land - T.fold;
// back sheets peel off the back, front sheets off the front, so no sheet ever passes through another
var SLIDE = { room: T.back, type: T.back + 0.06 * DS, snd: T.front, cap: T.front + 0.06 * DS };

function step(t, t0, w, z) {        // the step response of a damped spring: starts at zero velocity, carries weight
  if (t <= t0) return 0;
  var d = t - t0, wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * d) * (Math.cos(wd * d) + (z * w / wd) * Math.sin(wd * d));
}
function land(t, t0, t1) {          // 0 -> 1 exactly at t1 with a long settle
  if (t <= t0) return 0;
  if (t >= t1) return 1;
  var u = (t - t0) / (t1 - t0);
  return 1 - Math.pow(1 - Math.pow(u, 2), 3);
}
function smooth(t, a, b) { var u = Math.max(0, Math.min(1, (t - a) / (b - a))); return u * u * (3 - 2 * u); }

function pan(t) {
  return POSE.pan * step(t, T.start, 9.5 * K, 0.74) + POSE.orbit * smooth(t, T.drift, T.fold);     // swing, then the slow orbit while it holds
}
function rig(t) {
  var home = 1 - land(t, T.fold, T.land);
  var p = pan(t);
  var tilt = POSE.tilt * step(t, T.start, 7.5 * K, 0.8);
  var dolly = POSE.dolly * step(t, T.start, 10 * K, 0.86) - 150 * smooth(t, T.drift, T.fold) - 120 * smooth(t, T.push, T.push + 0.5 * DS);
  var x = POSE.x * step(t, T.start, 8 * K, 0.85), y = POSE.y * step(t, T.start, 8 * K, 0.85);
  // the camera banks into the turn, a crane does this on its own: roll follows how fast the pan is moving
  var e = 1 / 120, v = (pan(t + e) * (1 - land(t + e, T.fold, T.land)) - pan(t - e) * (1 - land(t - e, T.fold, T.land))) / (2 * e);
  return { pan: p * home, tilt: tilt * home, dolly: -dolly * home, x: x * home, y: y * home, roll: t >= T.land - 1e-6 ? 0 : 0.012 * v };
}
function plane(t, k) {
  var fold = 1 - land(t, T.fold + FOLD * (k === 'snd' ? 0 : k === 'cap' ? 0.037 : k === 'type' ? 0.024 : 0.12), T.land);
  var out = step(t, SLIDE[k], 13 * KP, 0.62);
  return Z[k] * out * (1 + 0.05 * smooth(t, T.push - 0.1 * DS, T.fold)) * fold;
}

var PL = ['room', 'type', 'cap', 'snd'];
for (var n = Math.round(A * 30); n <= Math.round(T.land * 30); n++) {
  var first = n === Math.round(A * 30), t = first ? A : n / 30 + PASS, ts = first ? q(A) : n / 30 + PASS - 0.0004;    // the first frame stays exactly flat
  var r = rig(t);
  tl.set('#__ID__-dolly', { x: r.x, y: r.y, z: r.dolly, rotation: r.roll }, ts);
  tl.set('#__ID__-tilt', { rotationX: r.tilt }, ts);
  tl.set('#__ID__-pan', { rotationY: r.pan }, ts);
  PL.forEach(function (k) { tl.set('#__ID__-p-' + k, { z: plane(t, k) }, ts); });
  var zb = plane(t, 'room'), zf = plane(t, 'snd');
  tl.set('.__ID__-xz', { z: zb, scaleX: Math.max(0.0001, (zf - zb) / 1000) }, ts);
}

var HAIR = { room: 0.62, type: 0.7, me: 0.86, cap: 0.92, snd: 0.96 };    // the far sheets a little dimmer
// hairlines: one stroke runs round each sheet from its top-left corner as the sheet leaves; labels follow; both gone before it lands
['room', 'type', 'me', 'cap', 'snd'].forEach(function (k) {
  var at = k === 'me' ? T.back + 0.06 * DS : SLIDE[k];
  var h = '.__ID__-' + k + '-h', l = '.__ID__-' + k + '-l', d = 0.15 * DS;
  gsap.set(h + '.__ID__-xh-t,' + h + '.__ID__-xh-b', { scaleX: 0 });
  gsap.set(h + '.__ID__-xh-l,' + h + '.__ID__-xh-r', { scaleY: 0 });
  gsap.set(l, { opacity: 0 });
  gsap.set(h, { opacity: HAIR[k] });
  tl.to(h + '.__ID__-xh-t', { scaleX: 1, duration: d, ease: 'power1.in' }, q(at));
  tl.to(h + '.__ID__-xh-l', { scaleY: 1, duration: d, ease: 'power1.in' }, q(at));
  tl.to(h + '.__ID__-xh-r', { scaleY: 1, duration: d, ease: 'power2.out' }, q(at) + d);
  tl.to(h + '.__ID__-xh-b', { scaleX: 1, duration: d, ease: 'power2.out' }, q(at) + d);
  tl.fromTo(l, { opacity: 0 }, { opacity: 1, duration: 0.1 * DS, ease: 'none', immediateRender: false }, q(at + 0.16 * DS));
  tl.to(h, { opacity: 0, duration: 0.16 * DS, ease: 'none' }, q(T.land - 0.585 * FOLD));
  tl.to(l, { opacity: 0, duration: 0.1 * DS, ease: 'none' }, q(T.fold + 0.1 * FOLD));
});
gsap.set('.__ID__-xz', { opacity: 0, rotationY: -90 });
tl.to('.__ID__-xz', { opacity: 0.24, duration: 0.24 * DS, ease: 'none' }, q(T.front + 0.1 * DS));
tl.to('.__ID__-xz', { opacity: 0, duration: 0.14 * DS, ease: 'none' }, q(T.fold + 0.17 * FOLD));
gsap.set('#__ID__-dim', { opacity: 0 });
tl.to('#__ID__-dim', { opacity: 0.26, duration: 0.5 * DS, ease: 'power2.inOut' }, q(T.back));
tl.to('#__ID__-dim', { opacity: 0, duration: 0.45 * DS, ease: 'power2.inOut' }, q(T.out));

// the room: the take's room while the speaker is flat on it, the true empty room once the sheets have separated
if (HAS_EMPTY) {
  gsap.set('#__ID__-v-empty', { opacity: 0 });
  tl.to('#__ID__-v-empty', { opacity: 1, duration: 0.1, ease: 'none' }, q(T.back + 0.066));       // inside the fastest frames of the room leaving
  tl.to('#__ID__-v-empty', { opacity: 0, duration: 0.13, ease: 'none' }, q(T.fold + 0.2 * FOLD));   // inside the fastest frames of the fold
}

// TYPE: each word rises through its mask on its own word, leaves as the fold starts
for (var i = 0; i < NW; i++) {
  gsap.set('#__ID__-w' + i, { yPercent: 130 });
  tl.to('#__ID__-w' + i, { yPercent: 0, duration: 0.2 * DS, ease: 'power3.out' }, q(T['w' + i] - 0.01));
  tl.to('#__ID__-w' + i, { yPercent: -130, duration: 0.2 * DS, ease: 'power3.in' }, q(T.out - 0.05 * DS + 0.03 * DS * i));
}

// CAPTIONS: the same box, words and lighting as the real ones, on their own plane
LINES.forEach(function (L, i) {
  on('#__ID__-kc' + i, L[0]);
  if (i < LINES.length - 1) off('#__ID__-kc' + i, L[1]);
  L[2].forEach(function (w, j) { tl.set('#__ID__-k' + i + '_' + j, { color: LIT }, q(w[1])); });
});

// SOUND: bars grow out from the left as the plane leaves, played bars go light, the playhead runs, bars sink as it folds
var snd0 = SLIDE.snd - 0.02;
for (var b = 0; b < BARS; b++) {
  var id = '#__ID__-b' + b, tb = WAVE[0] + (WAVE[1] - WAVE[0]) * (b + 0.5) / BARS;
  gsap.set(id, { scaleY: 0 });
  tl.to(id, { scaleY: 1, duration: 0.22 * DS, ease: 'power3.out' }, q(snd0 + b * 0.0035 * DS));
  tl.set(id, { backgroundColor: LIGHT }, q(tb));
  tl.to(id, { scaleY: 0, duration: 0.16 * DS, ease: 'power3.in' }, q(T.out - 0.03 + b * 0.001 * DS));
}
function phx(t) { return 40 + 1000 * (t - WAVE[0]) / (WAVE[1] - WAVE[0]); }
gsap.set('#__ID__-ph', { opacity: 0, x: phx(snd0) });
tl.set('#__ID__-ph', { opacity: 1 }, q(snd0 + 0.1 * DS));
tl.fromTo('#__ID__-ph', { x: phx(snd0) }, { x: phx(T.land), duration: T.land - snd0, ease: 'none', immediateRender: false }, q(snd0));
tl.to('#__ID__-ph', { opacity: 0, duration: 0.1 * DS, ease: 'none' }, q(T.out + 0.05 * DS));
"""
