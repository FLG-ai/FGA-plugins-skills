// storyboard-deck-flip (layer: top). Part 2 of 3: the AI shows its thinking. Picks up storyboard-deck's grid on
// its first frame (same cards, same slots).
//   A          the grid gathers into a loose pile beside the head, the hero card on top, landing big (scale 1)
//   FLIP_ON    the hero flips over (a lift on the turn) to show its plan as the board wrote it, ruled like an
//              index card: the beat's line, its plan, its facts (sound, music, shot, length)
//   UNDER      accent underlines land on the plan lines and the facts, each on its word
//   B          the hero stays face down (showing the plan); the note effect turns it back over
// Reach for it when the line says "it shows me its thinking", "I can see what it's planning", "here's the plan".
// Supply: nothing by hand: fx/storyboard-deck/gen.py writes these cards with the deck's (see the deck's fx.js).
// Change only these constants:
var FLIP_ON = 'shows';                       // the hero flips to its plan on this word
var UNDER = [['plan0', 'its'], ['plan1', null], ['fact0', 'thinking'], ['fact1', null]];   // [what, its word]; null = GAP after the one before
var T = { flip: 0.63, under: 1.17, gap: 0.12 };   // fallbacks: s after A (flip, the first underline), s between underlines
var HX = 640, HY = 236;                      // the hero card's top left at full size (396 x 780): beside the head
var COLS = [35, 292, 549, 806], ROWS = [250, 743], S = 0.6035;   // the deck's grid (keep in step with its fx.js)
var TILT = [-2.2, 1.8, 0, 2.6, -1.4, -3.0, 1.2, 2.2];   // the pile's loose angles, offsets under the hero
var DX = [-8, 2, 0, 4, -12, -2, -6, 3], DY = [6, -5, 0, 9, 4, -8, 10, -3];

var W2 = 198, H2 = 390;
var st = document.getElementById('{{ID}}-stage');
var N = +st.getAttribute('data-cards') || 8, HERO = +st.getAttribute('data-hero') || 0;
function slot(k) { return { x: COLS[k % 4] + W2 * S - W2, y: ROWS[Math.floor(k / 4) % ROWS.length] + H2 * S - H2 }; }
function cue(w, fb, after) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }
for (var k = 0; k < N; k++) {
  var s0 = slot(k);
  gsap.set('#{{ID}}-c' + k, { x: s0.x, y: s0.y, scale: S, rotation: 0, rotationY: 0, zIndex: k === HERO ? 200 : 10 + k, transformOrigin: '50% 50%' });
}
gsap.set('#{{ID}} .{{ID}}-u', { scaleX: 0 });

// the plan keeps its fx.html size unless a line is wider than the card with the pack's text face
function fit() {
  Array.prototype.forEach.call(document.querySelectorAll('#{{ID}}-c' + HERO + ' .{{ID}}-plan'), function (p) {
    p.style.fontSize = '';
    var max = 0;
    Array.prototype.forEach.call(p.children, function (l) { max = Math.max(max, l.firstChild.offsetWidth); });
    if (max > 356) p.style.fontSize = (parseFloat(getComputedStyle(p).fontSize) * 356 / max).toFixed(2) + 'px';
  });
}
fit();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

// the gather: the rest pile up under the hero's spot, the hero lands big on top
var order = [], i = 0;
for (var k = 0; k < N; k++) if (k !== HERO) order.push(k);
order.forEach(function (k, j) {
  tl.to('#{{ID}}-c' + k, { x: HX + DX[k % 8], y: HY + DY[k % 8], scale: 1, rotation: TILT[k % 8], duration: 0.32, ease: 'power3.inOut' }, q(A + 0.03 + j * 0.022));
});
tl.to('#{{ID}}-c' + HERO, { x: HX, y: HY, scale: 1, duration: 0.36, ease: 'power3.inOut' }, q(A + 0.07));

// the flip, with a lift on the turn
var tFlip = Math.max(A + 0.45, cue(FLIP_ON, T.flip, A));
tl.fromTo('#{{ID}}-c' + HERO, { rotationY: 0 }, { rotationY: 180, duration: 0.42, ease: 'power3.inOut', immediateRender: false }, q(tFlip));
tl.to('#{{ID}}-c' + HERO, { y: HY - 26, scale: 1.04, duration: 0.21, ease: 'power2.out' }, q(tFlip));
tl.to('#{{ID}}-c' + HERO, { y: HY, scale: 1, duration: 0.21, ease: 'power2.in' }, q(tFlip + 0.21));

// the underlines, each on its word (the ones this card doesn't have are skipped)
var prev = tFlip + 0.42 - T.gap;
UNDER.forEach(function (u, j) {
  var el = document.getElementById('{{ID}}-' + u[0]);
  if (!el) return;
  var t = u[1] ? cue(u[1], j ? prev - A + T.gap : T.under, prev) : prev + T.gap;
  t = Math.max(t, prev + 0.06);
  if (t > B - 0.16) return;
  tl.fromTo(el, { scaleX: 0 }, { scaleX: 1, duration: 0.14, ease: 'power2.out', immediateRender: false }, q(t));
  prev = t;
});
