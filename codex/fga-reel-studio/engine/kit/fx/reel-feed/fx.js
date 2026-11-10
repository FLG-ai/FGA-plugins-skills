// reel-feed (layer: cam, above the cutout: it covers the speaker). "Lots of people are doing this":
//   A         a hard cut into a feed: the first screenshot fills the frame with a small scale settle (1.07, 1.02, 1)
//   flicks    the feed snaps through eight screenshots of other people doing it, like a fast flick-scroll: every
//             move is one frame of vertical motion blur, every card holds a few frames, the holds shortening as it
//             speeds up (ACCEL); a thin scroll thumb on the right tracks it
//   LAND_ON   the last move brakes over three frames onto the speaker (a synced copy of the live shot, the ninth
//             card), landing on the word; the thumb fades and the effect hands back at B with no visible change
// Reach for it on "lots of people do this", "everyone's posting these": the fast alternative to grid-collapse.
// Supply: eight real screenshots of other creators doing what you describe (9:16, full frame, headline readable),
// files in this folder, listed in SHOTS. Until then the cards are token-built PLACEHOLDERS labelled LABEL 1..8.
// Change only these constants:
var SHOTS = [];                     // e.g. ['shot1.jpg', 'shot2.jpg', ...]: up to 8, in feed order; [] = placeholders
var LABEL = 'Screenshot';           // the placeholder cards' label (numbered)
var LAND_ON = 'this';               // the feed lands on the speaker on this word (fallback: A + T.land)
var ACCEL = 1.25;                   // 1 = even holds; higher = long holds first, short last (it speeds up)
var T = {
  land: 1.27,                       // fallback for LAND_ON (s after A)
  minGap: 2,                        // frames between landings at the fastest (one blur frame + one held)
  thumbOut: 0.15                    // the scroll thumb fades over this, two frames after the landing
};
var THUMB = { top: 230, bottom: 1290, h: 150 };   // the thumb travels inside the safe zone

var ID = '{{ID}}', FPS = 30, N = 8;
function el(s) { return document.getElementById(ID + '-' + s); }

// ---- the cards: real screenshots replace the placeholders, the placeholders get their numbered label
for (var c = 1; c <= N; c++) {
  var card = el('c' + c), shot = SHOTS[c - 1];
  if (shot) {
    card.innerHTML = '';
    var img = document.createElement('img');
    img.className = ID + '-i';
    img.src = 'fx/' + ID + '/' + shot;
    img.alt = '';
    card.appendChild(img);
  } else {
    var n = card.querySelector('.' + ID + '-n');
    n.textContent = LABEL + ' ' + c;
    n.setAttribute('data-layout-allow-overlap', '');
    n.setAttribute('data-layout-allow-overflow', '');
  }
}

// ---- landing frames: card 1 at A, the speaker on LAND_ON, the seven between on an accelerating curve
var f0 = Math.round(A * FPS);
var tLand = wordAt(LAND_ON, A);
if (tLand === null || tLand >= B - 0.1) tLand = A + T.land;
var fLand = Math.round(tLand * FPS), L = [];
for (var i = 0; i <= N; i++) L.push(Math.round(f0 + (fLand - f0) * (1 - Math.pow(1 - i / N, ACCEL))));
for (var k = 1; k <= N; k++) L[k] = Math.max(L[k], L[k - 1] + (k === N ? 3 : T.minGap));   // the brake needs three

// ---- keys, one per frame: pos = which card is on screen (0 = the first ... N = the speaker), blur = vertical
// motion blur for that frame (it grows as the feed speeds up)
function F(f) { return q(f / FPS); }
function key(f, pos, b) {
  tl.set('#' + ID + '-strip', { y: -pos * 1920 }, F(f));
  tl.set('#' + ID + '-view', { filter: b > 0.5 ? 'url(#' + ID + '-mb)' : 'none' }, F(f));
  if (b > 0.5) tl.set('#' + ID + '-mb-g', { attr: { stdDeviation: '0 ' + b.toFixed(1) } }, F(f));
  tl.set('#' + ID + '-thumb', { y: THUMB.top + (THUMB.bottom - THUMB.top - THUMB.h) * Math.max(0, pos) / N }, F(f));
}
gsap.set('#' + ID + '-strip', { y: 0 });
gsap.set('#' + ID + '-thumb', { y: THUMB.top, opacity: 0 });
gsap.set('#' + ID + '-view', { transformOrigin: '540px 960px', filter: 'none' });
key(L[0], 0, 22);
key(L[0] + 1, 0, 0);
for (var j = 1; j < N; j++) {                                   // a blurred frame half way, then the card
  var b = 70 + 10 * (j / N);
  key(L[j] - 1, j - 0.52, b);
  key(L[j], j, 0);
}
key(L[N] - 2, N - 0.38, 80);                                    // onto the speaker: brakes over three frames
key(L[N] - 1, N - 0.05, 18);
key(L[N], N, 0);
tl.set('#' + ID + '-thumb', { opacity: 0.85 }, F(L[0]));
tl.set('#' + ID + '-view', { scale: 1.07 }, F(L[0]));
tl.set('#' + ID + '-view', { scale: 1.02 }, F(L[0] + 1));
tl.set('#' + ID + '-view', { scale: 1 }, F(L[0] + 2));
tl.fromTo('#' + ID + '-thumb', { opacity: 0.85 }, { opacity: 0, duration: T.thumbOut, ease: 'none', immediateRender: false }, F(L[N] + 2));
