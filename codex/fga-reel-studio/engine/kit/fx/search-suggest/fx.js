// LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run
// gen.py on the project: it rewrites this file.
// search-suggest: written by gen.py for this window (rerun it when the window, the cut or the query changes). The
// pill drops in and lands on the first word, the query types a letter a frame in bursts on the speaker's words, the
// real rows swap per prefix, the top row highlights and takes a soft tap, it all lifts away. The panel sits behind
// the speaker (a CUT_WINDOWS entry over the window). Frames are counted from A's frame.
var R = '#{{ID}}-', S = '#{{ID}} .{{ID}}-', FPS = 30, F0 = Math.round(A * FPS);
var LAND = 4, PILL_OFF = 352, LIFT = 660;
var KEYS = [[5,1],[6,2],[7,3],[8,4],[14,5],[15,6],[16,7],[24,8],[25,9],[26,10],[27,11],[28,12],[37,13],[38,14],[45,15],[46,16],[47,17],[48,18],[49,19]];   // [frame, letters on screen]
var ROWS = [[16,0],[24,1],[26,2],[28,3],[37,4],[45,5],[47,6],[49,7]];   // [frame, which answer]
var HILITE = 49, TAP = 51, LIFT_F = 54;
var CUTF = [];   // picture cuts inside the window
function at(f) { return q((F0 + f) / FPS); }

// the pill drops in and lands on the first word; the panel waits for its first answer
gsap.set(R + 'pillw', { y: -PILL_OFF });
gsap.set(R + 'panelw', { opacity: 0 });
tl.fromTo(R + 'pillw', { y: -PILL_OFF }, { y: 0, duration: 4 / FPS, ease: 'back.out(1.2)', immediateRender: false }, at(LAND - 4));

// the keys: each letter on its frame, the caret follows (it sits after the letters), the clear glyph with the first one
var letters = document.querySelectorAll(S + 'c');
KEYS.forEach(function (k) { tl.set(letters[k[1] - 1], { display: 'inline' }, at(k[0])); });
tl.set(R + 'x', { opacity: 1 }, at(KEYS[0][0]));

// the dropdown opens on the first answer, then swaps per prefix with no transition, as real search does
tl.set(R + 'panelw', { opacity: 1 }, at(ROWS[0][0]));
tl.fromTo(R + 'panel', { clipPath: 'inset(0px 0px 280.0px 0px round 28.0px)' }, { clipPath: 'inset(-60px -60px -60px -60px round 28.0px)', duration: 0.13, ease: 'power3.out', immediateRender: false }, at(ROWS[0][0]));
ROWS.forEach(function (r, k) {
  tl.set(R + 'st' + r[1], { opacity: 1 }, at(r[0]));
  if (k) tl.set(R + 'st' + ROWS[k - 1][1], { opacity: 0 }, at(r[0]));
});

// the top row highlights on the last letter, the soft tap lands and presses it
tl.set(R + 'hl', { opacity: 1 }, at(HILITE));
tl.fromTo(R + 'tap', { opacity: 0, scale: 1.6 }, { opacity: 1, scale: 1, duration: 2 / FPS, ease: 'power2.out', immediateRender: false }, at(TAP - 2));
tl.to(R + 'tap', { scale: 0.84, duration: 0.05, ease: 'power2.out' }, at(TAP));
tl.to(R + 'tap', { scale: 1.2, opacity: 0, duration: 0.1, ease: 'power2.out' }, at(TAP + 2));
tl.set(R + 'hl2', { opacity: 1 }, at(TAP));
tl.set(S + 'caret', { opacity: 0 }, at(TAP));

// a picture cut inside the window: on its frame the footage can still show the shot before and no cutout plays, so
// the rows (which pass behind the head) sit that one frame out
CUTF.forEach(function (f) { tl.set(R + 'cutw', { opacity: 0 }, at(f)); tl.set(R + 'cutw', { opacity: 1 }, at(f + 1)); });

// it all lifts away: the pill leads, the panel a frame behind; the shadow counter-moves so it stays on the head
tl.to(R + 'pillw', { y: -LIFT, duration: 5 / FPS, ease: 'power2.in' }, at(LIFT_F));
tl.to(R + 'panelw', { y: -LIFT, duration: 5 / FPS, ease: 'power2.in' }, at(LIFT_F + 1));
if (document.querySelector(R + 'shw')) tl.to(R + 'shw', { y: LIFT, duration: 5 / FPS, ease: 'power2.in' }, at(LIFT_F + 1));
