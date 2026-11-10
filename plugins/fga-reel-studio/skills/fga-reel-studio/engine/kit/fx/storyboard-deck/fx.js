// storyboard-deck (layer: top). Part 1 of 3 (then storyboard-deck-flip, storyboard-deck-note): the video's own
// storyboard as a deck of cards.
//   A          the deck (face down, squared, a hair rotated) slides in from the right into the last grid slot
//   DEAL_ON    the cards deal out one by one, each flipping face up with a little spin and a bounce as it lands in
//              its slot of a 4 x 2 grid (front: the beat's frame, its number and time, its line)
//   SLAM_ON    the last card turns over where it lies and slams down; the table takes the hit
//   B          the grid holds; the flip effect picks it up on the next frame
// Reach for it when the line says "it plans every beat", "it gives me a full storyboard", any "here is the plan".
// Supply: nothing by hand. The cards are the beats of the storyboard the kit made for this video:
//   PY fx/storyboard-deck/gen.py <project>      (after pipeline/storyboard.py; rerun when the board changes)
// writes the cards of all three effects (fx.html) and their frames from <project>/storyboard/ (without a board,
// from the video's own lines and frames cut from clean.mp4). Which beats, the hero and the note's before/after
// frames are constants in gen.py. The library's cards are the effects lab's stand-in board.
// Keep the three ids as <id>, <id>-flip, <id>-note, back to back on the timeline, all on layer top.
// Change only these constants:
var DEAL_ON = 'plans';                       // the first card leaves the deck on this word
var SLAM_ON = 'beat';                        // the last card slams down on this word
var T = { deal: 0.30, slam: 1.50 };          // fallbacks (s after A) when a word isn't found
var COLS = [35, 292, 549, 806], ROWS = [250, 743];   // the grid: each column's left, each row's top (px)
var S = 0.6035;                              // a dealt card's scale (the card is 396 x 780 at 1)
var FLY = 0.28;                              // one card's flight from the deck to its slot (s)

var W2 = 198, H2 = 390;                      // half a card at scale 1 (fx.html)
var N = +document.getElementById('{{ID}}-stage').getAttribute('data-cards') || 8;
function slot(k) { return { x: COLS[k % 4] + W2 * S - W2, y: ROWS[Math.floor(k / 4) % ROWS.length] + H2 * S - H2 }; }
function cue(w, fb, after) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }
var DECK = slot(N - 1);
var cards = [];
for (var k = 0; k < N; k++) cards.push('#{{ID}}-c' + k);

var tDeal = cue(DEAL_ON, T.deal, A), tSlam = cue(SLAM_ON, T.slam, tDeal + 0.01);
// every card but the last lands between the deal and just before the slam, evenly
var first = tDeal + FLY, last = Math.max(first, tSlam - 0.12), LAND = [];
for (var k = 0; k < N - 1; k++) LAND.push(N > 2 ? first + (last - first) * k / (N - 2) : first);

// the deck: face down, squared up, a hair rotated; card 0 on top
for (var k = 0; k < N; k++) {
  var d = N - 1 - k;
  gsap.set(cards[k], { x: DECK.x - d * 2.4, y: DECK.y - d * 4.4, scale: S, rotation: -4, rotationY: 180,
    zIndex: 20 - k, transformOrigin: '50% 50%' });
}
gsap.set('#{{ID}}-stage', { x: 620 });
// the deck slides in from the right into its slot (clear of the caption band)
tl.fromTo('#{{ID}}-stage', { x: 620 }, { x: 0, duration: 0.32, ease: 'power3.out', immediateRender: false }, q(A));

// the deal: each card flips face up with a little spin and lands with a bounce
for (var k = 0; k < N - 1; k++) {
  var c = cards[k], to = slot(k), t0 = LAND[k] - FLY, dir = (k % 2 ? 1 : -1), dd = N - 1 - k;
  tl.set(c, { zIndex: 100 + k }, q(t0));
  tl.fromTo(c, { x: DECK.x - dd * 2.4, y: DECK.y - dd * 4.4, rotationY: 180 },
    { x: to.x, y: to.y, rotationY: 0, duration: FLY, ease: 'power3.out', immediateRender: false }, q(t0));
  tl.fromTo(c, { rotation: -4 }, { rotation: dir * 16, duration: 0.12, ease: 'power2.out', immediateRender: false }, q(t0));
  tl.to(c, { rotation: 0, duration: 0.2, ease: 'back.out(1.8)' }, q(t0 + 0.12));
  tl.fromTo(c, { scale: S }, { scale: S * 1.1, duration: 0.11, ease: 'power2.out', immediateRender: false }, q(t0));
  tl.to(c, { scale: S, duration: 0.17, ease: 'power2.in' }, q(t0 + 0.11));
}

// the last card turns over where it lies and slams down on its word
var lc = cards[N - 1], ls = slot(N - 1), tTurn = Math.max(LAND[N - 2] !== undefined ? LAND[N - 2] - 0.1 : tDeal, tSlam - 0.30);
tl.set(lc, { zIndex: 120 }, q(tTurn));
tl.fromTo(lc, { rotationY: 180, rotation: -4, x: DECK.x, y: DECK.y },
  { rotationY: 0, rotation: 0, x: ls.x, y: ls.y - 24, duration: tSlam - 0.1 - tTurn, ease: 'power3.out', immediateRender: false }, q(tTurn));
tl.fromTo(lc, { scale: S }, { scale: S * 1.14, duration: tSlam - 0.1 - tTurn, ease: 'power3.out', immediateRender: false }, q(tTurn));
tl.to(lc, { scale: S, y: ls.y, duration: 0.1, ease: 'power3.in' }, q(tSlam - 0.1));
// the table takes the hit
tl.fromTo('#{{ID}}-stage', { scale: 1 }, { scale: 1.014, duration: 0.05, ease: 'power2.out', immediateRender: false, transformOrigin: '540px 732px' }, q(tSlam));
tl.to('#{{ID}}-stage', { scale: 1, duration: 0.22, ease: 'power2.out' }, q(tSlam + 0.05));
