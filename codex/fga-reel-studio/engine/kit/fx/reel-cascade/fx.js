// reel-cascade (layer: behind, under the speaker's cutout). "My best videos drop in behind me":
//   A         the room dims (a veil in the dark ground, half strength, 0.3 s)
//   LAND      eight of your own videos fly in out of depth, one after another: each starts far back behind the head
//             (small, tumbling, fogged dark, out of focus) and comes forward into one wall plane behind you, braking
//             into it; a hair past the plane on its word, then back onto it with a contact shadow. The landings on
//             spoken words also jolt the whole wall. All eight keep playing.
//   OUT_ON    on the line's last word they recede back into depth, last in first out, and the room comes back up,
//             all gone by B
// Reach for it on "my best videos", "everything I've posted", a body of work showing up behind you. playing-grid is
// the calmer version of the same line. Needs a CUT_WINDOWS entry over its window (the head breaks the wall).
// Supply: your videos as t1.mp4 .. t8.mp4 in this folder, cut by mkclips.py (small all-intra proxies, so every frame
// seeks exactly):
//   PY fx/<id>/mkclips.py <project> [<id>] --from best1.mp4 best2.mp4@3.5 ...
// Without --from it cuts PLACEHOLDERS from the project's own clean.mp4 (the library's are the lab's stand-in);
// PLACEHOLDER labels them on the tiles. Set it to '' once the clips are yours.
// Change only these constants:
var LAND = [                        // [tile, cue] in landing order: tiles 1-4 the top row, 5-8 the bottom row, left to
  [2, 'videos'], [3, null], [5, 'drop'], [8, null],   // right; cue = the spoken word it lands on, null = evenly
  [1, 'in'], [4, null], [6, 'behind'], [7, null]      // between its neighbours (or T.fill after the last word)
];
var AT = [0.29, 0.41, 0.53, 0.65, 0.77, 0.89, 1.01, 1.12];   // fallbacks (s after A) for cue words not found
var OUT_ON = 'me';                  // they recede on this word (fallback, and at the latest: T.out before B)
var GRID = { cols: 4, w: 216, h: 384, gap: 18, top: 222, x: 540 };   // the wall: 9:16 tiles centred on x
var VANISH = { x: 540, y: 700 };    // where they fly out of: behind the speaker's head
var PLACEHOLDER = 'Your video';     // the label on each tile (numbered); '' once the clips are yours
var T = {
  dim: 0.5,                         // how far the room dims (veil opacity)
  flight: 0.42,                     // the longest flight; a tile that lands sooner after A flies for less
  minFlight: 0.18,                  // no landing earlier than this after A
  fill: 0.11,                       // a null cue after the last word lands this long after the one before
  out: 0.34,                        // the recede starts this long before B at the latest
  stagger: 0.016                    // between the tiles on the way out
};

function rnd(i) { var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }
function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
var ID = '{{ID}}', FAR = -2600;

// ---- the wall: tiles placed from GRID, the vanishing point on the head, the placeholder labels
document.getElementById(ID + '-stage').style.perspectiveOrigin = VANISH.x + 'px ' + VANISH.y + 'px';
var left0 = GRID.x - (GRID.cols * GRID.w + (GRID.cols - 1) * GRID.gap) / 2;
$$('#' + ID + ' .' + ID + '-t').forEach(function (t, i) {
  t.style.left = (left0 + (i % GRID.cols) * (GRID.w + GRID.gap)) + 'px';
  t.style.top = (GRID.top + Math.floor(i / GRID.cols) * (GRID.h + GRID.gap)) + 'px';
  t.style.width = GRID.w + 'px';
  t.style.height = GRID.h + 'px';
});
$$('#' + ID + ' .' + ID + '-tag').forEach(function (e, i) {
  e.textContent = PLACEHOLDER ? PLACEHOLDER + ' ' + (i + 1) : '';
  if (!PLACEHOLDER) e.style.display = 'none';
  e.setAttribute('data-layout-allow-overlap', '');
  e.setAttribute('data-layout-allow-occlusion', '');
  e.setAttribute('data-layout-allow-overflow', '');
});

// ---- landing times: on their words (searched in order from A), nulls spread between their neighbours
var hit = [], prev = A;
LAND.forEach(function (p, i) {
  hit.push(null);
  if (!p[1]) return;
  var w = wordAt(p[1], prev);
  hit[i] = (w === null || w >= B - T.out) ? A + AT[i] : w;
  prev = hit[i];
});
for (var i = 0; i < hit.length; i++) {
  if (hit[i] !== null) continue;
  var a = i - 1, b = i + 1;
  while (b < hit.length && hit[b] === null) b++;
  var ta = a >= 0 ? hit[a] : A + T.minFlight;
  for (var m = i; m < b; m++) hit[m] = b < hit.length ? ta + (hit[b] - ta) * (m - a) / (b - a) : ta + T.fill * (m - a);
  i = b - 1;
}
for (var k = 0; k < hit.length; k++) hit[k] = Math.max(hit[k], A + T.minFlight, k ? hit[k - 1] + 1 / 30 : 0);
var last = Math.max.apply(null, hit);
var tOut = wordAt(OUT_ON, last);
tOut = Math.min(tOut === null ? B : tOut, B - T.out);
tOut = Math.max(tOut, last + 0.1);

// ---- in: the room dims, each tile flies in on its landing
gsap.set('#' + ID + '-veil', { opacity: 0 });
gsap.set('#' + ID + ' .' + ID + '-t', { opacity: 0 });
tl.fromTo('#' + ID + '-veil', { opacity: 0 }, { opacity: T.dim, duration: 0.3, ease: 'power2.out', immediateRender: false }, q(A));
LAND.forEach(function (p, i) {
  var s = '#' + ID + '-t' + p[0], h = hit[i], col = (p[0] - 1) % GRID.cols, side = col < GRID.cols / 2 ? -1 : 1;
  var top = p[0] <= GRID.cols, D = Math.min(T.flight, h - A), t0 = h - D;
  var rx = (top ? 1 : -1) * (18 + 14 * rnd(i + 1)), ry = side * (30 + 20 * rnd(i + 7)), rz = side * (6 + 6 * rnd(i + 3));
  gsap.set(s, { z: FAR, rotationX: rx, rotationY: ry, rotation: rz, transformOrigin: '50% 50%' });
  gsap.set(s + ' .' + ID + '-fog', { opacity: 0.82 });
  gsap.set(s + ' .' + ID + '-sh', { opacity: 0 });
  gsap.set(s + ' .' + ID + '-v', { filter: 'blur(6px)' });
  tl.set(s, { opacity: 1 }, q(t0));
  // the flight: fast out of the dark, braking into the wall; a hair past the plane on the word, then back onto it
  tl.fromTo(s, { z: FAR }, { z: 40, duration: D, ease: 'power3.out', immediateRender: false }, q(t0));
  tl.fromTo(s, { rotationX: rx, rotationY: ry, rotation: rz }, { rotationX: 0, rotationY: 0, rotation: 0, duration: D, ease: 'power2.out', immediateRender: false }, q(t0));
  tl.fromTo(s + ' .' + ID + '-fog', { opacity: 0.82 }, { opacity: 0, duration: D, ease: 'power2.in', immediateRender: false }, q(t0));
  tl.fromTo(s + ' .' + ID + '-v', { filter: 'blur(6px)' }, { filter: 'blur(0px)', duration: D, ease: 'power2.in', immediateRender: false }, q(t0));
  tl.set(s + ' .' + ID + '-v', { filter: 'none' }, q(h + 0.01));
  tl.fromTo(s, { z: 40 }, { z: 0, duration: 0.2, ease: 'back.out(2.2)', immediateRender: false }, q(h));
  tl.fromTo(s + ' .' + ID + '-sh', { opacity: 0 }, { opacity: 1, duration: 0.12, ease: 'power2.out', immediateRender: false }, q(h));
});
// the wall takes each landing on a spoken word: a small push back and a spring
LAND.forEach(function (p, i) {
  if (!p[1]) return;
  tl.fromTo('#' + ID + '-wall', { z: 0 }, { z: -16, duration: 0.05, ease: 'power2.out', immediateRender: false }, q(hit[i]));
  tl.fromTo('#' + ID + '-wall', { z: -16 }, { z: 0, duration: 0.13, ease: 'back.out(2)', immediateRender: false }, q(hit[i] + 0.05));
});

// ---- out: everything recedes back into depth, last in first out, the room back up by B
LAND.slice().reverse().forEach(function (p, i) {
  var s = '#' + ID + '-t' + p[0], col = (p[0] - 1) % GRID.cols, side = col < GRID.cols / 2 ? -1 : 1, t = tOut + T.stagger * i;
  tl.fromTo(s, { z: 0, rotationY: 0, rotationX: 0 },
    { z: FAR, rotationY: -side * 26, rotationX: (p[0] <= GRID.cols ? -1 : 1) * 14, duration: 0.2, ease: 'power3.in', immediateRender: false }, q(t));
  tl.fromTo(s + ' .' + ID + '-fog', { opacity: 0 }, { opacity: 0.85, duration: 0.2, ease: 'power2.in', immediateRender: false }, q(t));
  tl.fromTo(s + ' .' + ID + '-sh', { opacity: 1 }, { opacity: 0, duration: 0.1, ease: 'none', immediateRender: false }, q(t));
  tl.fromTo(s, { opacity: 1 }, { opacity: 0, duration: 0.06, ease: 'none', immediateRender: false }, q(t + 0.14));
});
tl.fromTo('#' + ID + '-veil', { opacity: T.dim }, { opacity: 0, duration: 0.22, ease: 'power2.inOut', immediateRender: false }, q(tOut + 0.09));
