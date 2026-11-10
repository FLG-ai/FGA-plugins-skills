// live-markup (layer: cam, above the speaker's cutout, under the captions). The speaker singles themselves out:
//   punch     on the turn word the shot gets a short camera punch (a synced copy of the footage, 1.06x to 1 over
//             9 frames, centred on the head) as edit.BW takes it to black and white; the shot keeps playing
//   loop      a grease pencil in the negative colour draws a rough loop round the head (1.15 turns, a lighter second
//             loop just after), on its word
//   word      WORD writes itself beside the head ("me" is a hand-drawn stroke; any other word sets in the display
//             face and wipes on), then an arrow curves into the loop, its head landing on the last cue word
//   follow    every mark rides the head track frame by frame (HEAD and TRACK, written by track.py) and shares the
//             punch while it lasts, so the speaker stays inside the loop as they move
// Reach for it on "but my way is different", "this is me", any line where the speaker singles themselves out.
// Needs edit.BW = (the punch word, the window end) and the captions left on (layer cam keeps them on top).
// Supply: the cue words below, then the head track for your footage:
//   PY fx/<id>/track.py <project> [<id>] [--head X,Y]
// It reads this effect's window from edit.py, finds the head with public/subject.webm (or --head), template-
// matches it through public/clean.mp4 and rewrites the track block below (and writes track.json). The track in the
// library is the lab's stand-in: rerun track.py whenever the window or the cut changes.
// Change only these constants:
var WORD = 'me';                            // the word the pencil writes ('me' is drawn by hand; others are set)
var KEY = { punch: 'but', loop: 'my', word: 'little', arrow: 'different' };   // the spoken word each beat lands on
var AT = { punch: 0.10, loop: 0.39, word: 1.53, arrow: 1.81 };   // fallbacks (s after A) when a word isn't found
var LEAD = { arrow: 0.18, head: 0.04 };     // the arrow starts this far ahead of its word; its head lands this far ahead
var PUNCH = 1.06, PUNCH_FRAMES = 9;         // the camera punch on the turn: scale, and frames back to 1
var LOOP = 1.4;                             // the loop's size over the head's half size
var SIDE = 'auto';                          // where the word sits: 'left', 'right', or 'auto' (the side with more room)
var MARK = 1;                               // the word and arrow's largest scale (they shrink to fit the frame)

// ---- track: track.py rewrites the lines between these two markers ----
var HEAD = {"x": 548.0, "y": 740.0, "rx": 140.0, "ry": 159.0};   // the head on the window's first frame: centre, half size (px)
var TRACK = [[0, 0.0, 0.0], [1, 0.0, 0.0], [2, 0.0, 0.0], [3, 0.0, 0.0], [4, 0.0, 0.0], [5, 0.0, 0.0], [6, 0.0, 0.0], [7, 0.0, 0.0], [8, -0.4, 0.0], [9, -0.8, 0.4], [10, -1.2, 0.8], [11, -1.6, 1.2], [12, -2.0, 1.6], [13, -2.0, 2.0], [14, -2.4, 2.4], [15, -2.8, 2.8], [16, -3.2, 3.2], [17, -3.6, 3.6], [18, -4.0, 4.0], [19, -4.4, 4.0], [20, -4.8, 4.4], [21, -5.2, 4.4], [22, -5.6, 4.4], [23, -6.4, 4.8], [24, -6.8, 5.2], [25, -7.2, 5.2], [26, -7.6, 5.6], [27, -8.4, 6.0], [28, -8.8, 6.4], [29, -9.6, 6.8], [30, -10.4, 7.2], [31, -11.2, 7.6], [32, -11.6, 8.0], [33, -12.4, 8.0], [34, -12.8, 8.0], [35, -13.2, 8.0], [36, -13.6, 8.0], [37, -14.0, 8.0], [38, -14.4, 8.0], [39, -14.8, 8.0], [40, -15.2, 8.0], [41, -15.6, 8.0], [42, -16.0, 8.0], [43, -16.4, 8.0], [44, -16.8, 8.0], [45, -17.2, 8.0], [46, -17.6, 8.0], [47, -18.0, 8.0], [48, -18.0, 7.6], [49, -18.0, 7.2], [50, -18.0, 6.8], [51, -18.0, 6.4], [52, -18.0, 6.0], [53, -18.4, 6.0], [54, -18.8, 6.0], [55, -19.2, 6.0], [56, -19.6, 6.0], [57, -19.6, 5.6], [58, -19.2, 5.2], [59, -18.8, 4.8], [60, -18.8, 4.4], [61, -18.8, 4.0], [62, -19.2, 4.0], [63, -19.2, 3.6], [64, -19.2, 3.2], [65, -18.8, 2.8], [66, -18.4, 2.4], [67, -18.0, 2.0], [68, -18.0, 2.0]];   // per frame of the window: [frame, dx, dy] from HEAD
// ---- end of track ----

function $(s) { return document.querySelector(s); }
function rnd(i) { var x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }
function find(word, after, fallback) {
  var w = word ? wordAt(word, after) : null;
  return (w === null || w >= B) ? A + fallback : w;
}
var tPunch = find(KEY.punch, A, AT.punch);
var tLoop = find(KEY.loop, tPunch, AT.loop);
var tWord = find(KEY.word, tLoop, AT.word);
var tArrow = find(KEY.arrow, tWord, AT.arrow);
var F0 = Math.round(A * 30);                 // TRACK frame 0
function T(k) { return q((F0 + k) / 30); }

// ---- the loop round the head: 1.15 turns, starting top right, wobbling, slightly open
var LX = HEAD.rx * LOOP, LY = HEAD.ry * LOOP;
function loop(cx, cy, rx, ry, seed) {
  var d = '', n = 46;
  for (var i = 0; i <= n; i++) {
    var a = -0.9 - (i / n) * Math.PI * 2 * 1.15, w = 1 + (rnd(seed + i) - 0.5) * 0.05 + 0.06 * i / n;
    d += (i ? ' L ' : 'M ') + (cx + rx * w * Math.cos(a)).toFixed(1) + ' ' + (cy + ry * w * Math.sin(a)).toFixed(1);
  }
  return d;
}
$('#{{ID}}-loop').setAttribute('d', loop(HEAD.x, HEAD.y, LX, LY, 3));
$('#{{ID}}-loop2').setAttribute('d', loop(HEAD.x + 4, HEAD.y + 6, LX * 0.95, LY * 0.97, 41));

// ---- the word and the arrow: the arrow's tip on the loop's upper corner, the word beyond it, shrunk to fit
// (in the mark's own units the word spans x -458..-210 and y -175..-98 from the tip, the arrow head reaches x 28)
var side = SIDE === 'auto' ? (HEAD.x <= 540 ? 'right' : 'left') : SIDE;
var dir = side === 'left' ? -1 : 1;
var tipX = HEAD.x + dir * LX * 0.74, tipY = HEAD.y - LY * 0.74;
var room = side === 'left' ? tipX - 50 : 1030 - tipX;
var s = Math.min(MARK, room / 470, (tipY - 240) / 180);
$('#{{ID}}-mark').setAttribute('transform', 'translate(' + tipX.toFixed(1) + ' ' + tipY.toFixed(1) + ') scale(' + s.toFixed(3) + ')');
$('#{{ID}}-arw').setAttribute('transform', side === 'left' ? '' : 'scale(-1 1)');
var me = $('#{{ID}}-me'), word = $('#{{ID}}-word');
if (WORD.toLowerCase() === 'me') {
  me.setAttribute('transform', 'translate(' + (side === 'left' ? -458 : 210) + ' -220) scale(1.25)');
  word.parentNode.removeChild(word);
  word = null;
} else {
  me.parentNode.removeChild(me);
  me = null;
  word.textContent = WORD;
  word.setAttribute('x', side === 'left' ? -210 : 210);
  word.setAttribute('y', -100);
  word.setAttribute('text-anchor', side === 'left' ? 'end' : 'start');
}

// ---- the camera punch on the turn word: the synced copy, PUNCH -> 1 over PUNCH_FRAMES, then the main picture
var P0 = Math.round(tPunch * 30) - F0;       // the punch's TRACK frame
function ps(k) { var p = Math.min(1, Math.max(0, (k - P0) / PUNCH_FRAMES)); return 1 + (PUNCH - 1) * Math.pow(1 - p, 3); }
gsap.set('#{{ID}}-punch', { opacity: 0, transformOrigin: HEAD.x + 'px ' + HEAD.y + 'px' });
gsap.set('#{{ID}}-trk', { transformOrigin: HEAD.x + 'px ' + HEAD.y + 'px' });
tl.set('#{{ID}}-punch', { opacity: 1 }, T(P0));
tl.set('#{{ID}}-punch', { opacity: 0 }, T(P0 + PUNCH_FRAMES));

// every frame: the marks follow the head and share the punch while it lasts
for (var i = 0; i < TRACK.length; i++) {
  var k = TRACK[i][0], sc = k >= P0 ? ps(k) : 1;
  if (k >= P0 && k < P0 + PUNCH_FRAMES) tl.set('#{{ID}}-punch', { scale: sc }, T(k));
  tl.set('#{{ID}}-trk', { x: sc * TRACK[i][1], y: sc * TRACK[i][2], scale: sc }, T(k));
}

// ---- grease pencil, drawn on its words (hidden until it draws: no round-cap dot before)
var DRAW = [['#{{ID}}-loop', tLoop, 0.40, 'power2.inOut', 1], ['#{{ID}}-loop2', tLoop + 0.08, 0.36, 'power2.inOut', 0.55],
            ['#{{ID}}-me', tWord, 0.22, 'none', 1], ['#{{ID}}-arrow', tArrow - LEAD.arrow, 0.14, 'power2.out', 1],
            ['#{{ID}}-head', tArrow - LEAD.head, 0.07, 'power1.out', 1]];
DRAW.forEach(function (d) {
  if (!$(d[0])) return;
  gsap.set(d[0], { opacity: 0, attr: { 'stroke-dasharray': '1 1', 'stroke-dashoffset': 1 } });
  tl.set(d[0], { opacity: d[4] }, q(d[1]));
  tl.fromTo(d[0], { attr: { 'stroke-dashoffset': 1 } }, { attr: { 'stroke-dashoffset': 0 }, duration: d[2], ease: d[3], immediateRender: false }, q(d[1]));
});
if (word) {                                   // a set word wipes on left to right, the way it is written
  gsap.set(word, { opacity: 0 });
  tl.set(word, { opacity: 1 }, q(tWord));
  tl.fromTo(word, { clipPath: 'inset(0% 100% 0% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: 0.24, ease: 'none', immediateRender: false }, q(tWord));
}
