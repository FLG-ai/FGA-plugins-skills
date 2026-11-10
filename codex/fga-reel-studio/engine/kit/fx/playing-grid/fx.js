// playing-grid (layer: behind, under the speaker's cutout). "Here are my last six videos":
//   LAND      six of your own videos, all playing, fall one by one from above the frame with gravity (a touch of
//             stretch), each landing on its word: squash, one bounce, a swing to rest, flat. Every landing knocks the tiles
//             already up (a small drop and tilt that springs back).
//   B - T.out they are yanked back up out of frame, one after another, all gone just before B
// Reach for it on "my last videos", "here's what I've been posting", a profile grid of your work behind you. The
// calmer sibling of reel-cascade (same line, less spectacle). Needs a CUT_WINDOWS entry over its window.
// Supply: your videos as t1.mp4 .. t6.mp4 in this folder, cut by reel-cascade's mkclips.py:
//   PY fx/reel-cascade/mkclips.py <project> <id> --from v1.mp4 v2.mp4@2.0 ...
// Without --from it cuts PLACEHOLDERS from the project's own clean.mp4 (the library's are the lab's stand-in);
// PLACEHOLDER labels them on the tiles. Set it to '' once the clips are yours.
// Change only these constants:
var LAND = [                        // [tile, cue, swing] in landing order: tiles 1-3 the top row, 4-6 the bottom;
  [1, 'are', -1], [6, 'my', 1], [3, null, 1],        // cue = the spoken word it lands on, null = evenly between its
  [4, 'last', -1], [5, null, 1], [2, 'six', -1]      // neighbours (or T.fill after the last word); swing = which way
];                                  // it tilts on the way down (-1 / 1): every tile comes to rest flat, at 0 degrees
var AT = [0.37, 0.63, 0.77, 0.90, 1.03, 1.17];   // fallbacks (s after A) for cue words not found
var GRID = { cols: 3, w: 296, h: 395, gap: 14, top: 236, x: 540 };   // the grid: 3:4 tiles centred on x
var PLACEHOLDER = 'Your video';     // the label on each tile (numbered); '' once the clips are yours
var T = {
  fall: 0.30,                       // the drop from above the frame onto the landing
  fill: 0.12,                       // a null cue after the last word lands this long after the one before
  out: 0.26,                        // the yank starts this long before B
  stagger: 0.018                    // between the tiles on the way out
};

function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
var ID = '{{ID}}';

// ---- the grid: slots placed from GRID, the placeholder labels
var left0 = GRID.x - (GRID.cols * GRID.w + (GRID.cols - 1) * GRID.gap) / 2;
$$('#' + ID + ' .' + ID + '-slot').forEach(function (s, i) {
  s.style.left = (left0 + (i % GRID.cols) * (GRID.w + GRID.gap)) + 'px';
  s.style.top = (GRID.top + Math.floor(i / GRID.cols) * (GRID.h + GRID.gap)) + 'px';
  s.style.width = GRID.w + 'px';
  s.style.height = GRID.h + 'px';
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
  var ta = a >= 0 ? hit[a] : A + T.fall;
  for (var m = i; m < b; m++) hit[m] = b < hit.length ? ta + (hit[b] - ta) * (m - a) / (b - a) : ta + T.fill * (m - a);
  i = b - 1;
}
for (var k = 0; k < hit.length; k++) hit[k] = Math.max(hit[k], A + T.fall, k ? hit[k - 1] + 1 / 30 : 0);
var tOut = B - T.out;

// ---- the fall: gravity in, squash, one bounce, swing to rest; each landing knocks the ones already up
LAND.forEach(function (p, i) {
  var f = '#' + ID + '-s' + p[0] + ' .' + ID + '-fall', h = hit[i], rot = 0, sw = p[2] < 0 ? -1 : 1;   // rests flat
  var row = Math.floor((p[0] - 1) / GRID.cols), top = GRID.top + row * (GRID.h + GRID.gap), above = -(top + GRID.h + 80);
  gsap.set(f, { y: above, rotation: rot + 9 * sw, scaleY: 1, transformOrigin: '50% 100%' });
  tl.fromTo(f, { y: above, rotation: rot + 9 * sw, scaleY: 1.06 },
    { y: 0, rotation: rot + 2.5 * sw, scaleY: 1.06, duration: T.fall, ease: 'power2.in', immediateRender: false }, q(h - T.fall));
  tl.fromTo(f, { scaleY: 1.06 }, { scaleY: 0.965, duration: 0.05, ease: 'power2.out', immediateRender: false }, q(h));
  tl.fromTo(f, { scaleY: 0.965 }, { scaleY: 1, duration: 0.14, ease: 'back.out(2)', immediateRender: false }, q(h + 0.05));
  tl.fromTo(f, { y: 0 }, { y: -20, duration: 0.11, ease: 'power2.out', immediateRender: false }, q(h));
  tl.fromTo(f, { y: -20 }, { y: 0, duration: 0.12, ease: 'power2.in', immediateRender: false }, q(h + 0.11));
  tl.fromTo(f, { y: 0 }, { y: -5, duration: 0.06, ease: 'power2.out', immediateRender: false }, q(h + 0.23));
  tl.fromTo(f, { y: -5 }, { y: 0, duration: 0.07, ease: 'power2.in', immediateRender: false }, q(h + 0.29));
  tl.fromTo(f, { rotation: rot + 2.5 * sw }, { rotation: rot - 1.6 * sw, duration: 0.13, ease: 'power2.out', immediateRender: false }, q(h));
  tl.fromTo(f, { rotation: rot - 1.6 * sw }, { rotation: rot, duration: 0.2, ease: 'power2.inOut', immediateRender: false }, q(h + 0.13));
  for (var k = 0; k < i; k++) {                 // the knock, on every tile already up
    if (hit[k] > h - 0.12) continue;            // still bouncing from its own landing
    var j = '#' + ID + '-s' + LAND[k][0] + ' .' + ID + '-jolt';
    tl.to(j, { y: 6, rotation: (k % 2 ? -0.7 : 0.7), duration: 0.05, ease: 'power2.out' }, q(h));   // .to: knocks chain
    tl.to(j, { y: 0, rotation: 0, duration: 0.18, ease: 'back.out(2.2)' }, q(h + 0.05));
  }
});

// ---- out: yanked back up out of frame, one after another
LAND.forEach(function (p, i) {
  var f = '#' + ID + '-s' + p[0] + ' .' + ID + '-fall', sw = p[2] < 0 ? -1 : 1;
  var row = Math.floor((p[0] - 1) / GRID.cols), top = GRID.top + row * (GRID.h + GRID.gap);
  tl.fromTo(f, { y: 0, rotation: 0 }, { y: -(top + GRID.h + 120), rotation: -6 * sw, duration: 0.16,
    ease: 'power3.in', immediateRender: false }, q(tOut + T.stagger * i));
});
