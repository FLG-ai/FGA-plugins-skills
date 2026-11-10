// comment-drop (layer: top), the CTA (the comment-cta alternative). The whole thread hovers above the head:
//   BOX_ON     a comment composer slides in (its caret blinks)
//   TYPE_ON    the keyword's letters pop in big across the top of the frame one after another, hang a beat, then
//              fall with gravity into the composer (they shrink as they drop); the field takes each hit and types it
//   POST_ON    Post presses, the comment posts (your name, a heart) and lifts to make room
//   REPLY_ON   the speaker's reply (headshot, handle) drops in under it on a thread line, each word on its word
//   LIKE_ON    the comment gets a like
//   B - out    both float up and away, gone at B
// The big letters split light/dark against the picture (light over dark areas, dark over light ones, never an
// outline): one dark copy per frame shows through that frame's tile of masks.png. Rebuild it for your footage:
//   PY fx/<id>/gen.py <project> [<id>]
// It reads this effect's window from edit.py and the picture from public/clean.mp4, and writes fx/<id>/masks.png.
// The masks.png in the library is the lab's stand-in: rerun gen.py whenever the window, the cut or the footage
// changes, or set SPLIT = false to keep the letters light everywhere.
// Supply: the keyword, the reply, your HANDLE, and your headshot (a square image dropped in this folder and named in
// HEADSHOT; until then a circle with INITIALS). Measure GROUP_Y on a still: the thread spans GROUP_Y to GROUP_Y + 292,
// so GROUP_Y + 292 sits on the top of the head (never over the face); the letters' tops land about 25px under
// GROUP_Y, so keep it at 195 or more (the top safe zone) and at 160 or more (the masks' band).
// Change only these constants. A cue word finds the first matching spoken word at or after the previous beat
// (wordAt); when it is missing, its fallback in T (s after A) is used.

var KEYWORD = 'EDIT';                     // falls in, letter by letter; 2 to 6 letters
var BOX_ON = 'Comment';                   // the composer slides in on this word
var TYPE_ON = 'EDIT';                     // the letters pop in on this spoken word
var POST_ON = 'and';                      // the comment posts on this word (or just after the last letter lands)
var REPLY_ON = "I'll";                    // the reply drops in on this word
var REPLY = [['Sending', 'send'], ['it', 'it'], ['to', 'to'], ['you.', 'you']];   // the reply, each word on its spoken word
var LIKE_ON = 'you';                      // the comment gets a like on this word; '' = none
var HANDLE = '@yourhandle';               // your handle, on the reply
var HEADSHOT = '';                        // e.g. 'headshot.jpg' in this folder; '' = a circle with INITIALS
var INITIALS = 'YN';                      // the placeholder headshot
var VIEWER = 'you', WHEN = 'now', PLACEHOLDER = 'Add a comment…', POST = 'Post';   // the composer's words
var GROUP_Y = 200;                        // frame px: the top of the big letters' row (see Supply)
var SPLIT = true;                         // false: light letters only (no masks.png needed)
var T = { box: 0.10, type: 0.40, post: 0.75, reply: 1.05, words: [1.35, 1.65, 1.95, 2.25], like: 2.30, out: 0.36 };   // fallbacks; out: s before B

var R = '#{{ID}} ', BAND_Y = 160, COLS = 8, TILE_H = 600;   // the mask band and the tile grid: keep in step with gen.py
var LIFT = -160, FONT = 160, TYPED = 38;                     // the posted comment lifts this far; big and typed letter size
function $(s) { return document.querySelector(s); }
function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function word(w, after, fallback) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? fallback : t; }
var LETTERS = Array.from(KEYWORD);

// ---- times, each on its word; the letters must land before the post, the post before the reply
var tBox = word(BOX_ON, A, A + T.box);
var tType = Math.max(tBox + 0.2, word(TYPE_ON, tBox, A + T.type));
var POP = 0.05, HANG = 0.11, DROP = 0.26;
var tLast = tType + (LETTERS.length - 1) * POP + HANG + DROP;           // the last letter lands
var tPost = Math.max(tLast + 0.06, word(POST_ON, tType, A + T.post));
var tLift = tPost + 0.08;
var tReply = Math.max(tLift + 0.09, word(REPLY_ON, tPost, A + T.reply));
var tWords = [], prev = tReply;
REPLY.forEach(function (r, i) {
  var t = Math.max(prev, word(r[1], prev, A + (T.words[i] !== undefined ? T.words[i] : T.words[T.words.length - 1] + 0.3 * i)));
  tWords.push(t); prev = t + 0.01;
});
var tLike = LIKE_ON ? Math.max(tReply + 0.1, word(LIKE_ON, tReply, A + T.like)) : 0;
var tOut = B - T.out;

// ---- fixed layout (no measuring, so every render worker gets the same numbers): each letter sits centred in a cell
// as wide as its usual advance in a sans face; the big row and the typed word use the same cells at their own sizes
function adv(c) {
  if ('IJ1'.indexOf(c) >= 0) return c === 'I' ? 0.32 : 0.54;
  if ('MW'.indexOf(c) >= 0) return 0.9;
  if ('iljfrt'.indexOf(c) >= 0) return 0.36;
  if ('mw'.indexOf(c) >= 0) return 0.84;
  if (c === ' ') return 0.3;
  return c === c.toUpperCase() ? 0.7 : 0.58;
}
var CELLS = LETTERS.map(adv), SUM = CELLS.reduce(function (a, b) { return a + b; }, 0);
function cellX(i, size, left) { var x = left; for (var j = 0; j < i; j++) x += CELLS[j] * size; return x; }
var BIG_LEFT = 540 - SUM * FONT / 2, FIELD_LEFT = 90 + 108;          // the big row is centred on x 540; the field's text starts here
var BIG_CY = GROUP_Y + 85, TYPED_CY = GROUP_Y + 180 + 32 + 24;      // centre lines: the big row, the typed word

// ---- build the words once
(function () {
  var host = $(R + '.cd-word');
  if (host.childNodes.length) return;
  LETTERS.forEach(function (c, i) {
    var f = document.createElement('span');
    f.className = 'cd-f cd-f' + i;
    f.style.left = cellX(i, FONT, BIG_LEFT).toFixed(1) + 'px';
    f.style.width = (CELLS[i] * FONT).toFixed(1) + 'px';
    f.setAttribute('data-layout-allow-overlap', '');
    f.innerHTML = '<span class="cd-fi" data-layout-allow-overlap data-layout-allow-occlusion></span>';   // they drop behind the card on purpose
    f.firstChild.textContent = c;
    host.appendChild(f);
    var t = document.createElement('span');
    t.className = 'cd-t cd-t' + i;
    t.style.left = (cellX(i, TYPED, 0)).toFixed(1) + 'px';
    t.style.width = (CELLS[i] * TYPED).toFixed(1) + 'px';
    t.setAttribute('data-layout-allow-occlusion', '');           // the caret sits on each letter as it lands
    t.textContent = c;
    $(R + '.cd-typed').appendChild(t);
  });
  REPLY.forEach(function (r, i) {
    if (i) $(R + '.cd-rtxt').appendChild(document.createTextNode(' '));
    var s = document.createElement('span');
    s.className = 'cd-r cd-r' + i;
    s.textContent = r[0];
    $(R + '.cd-rtxt').appendChild(s);
  });
  $(R + '.cd-me').innerHTML = HEADSHOT ? '<img src="fx/{{ID}}/' + HEADSHOT + '" alt="">' : '';
  if (!HEADSHOT) $(R + '.cd-me').textContent = INITIALS;
  $(R + '.cd-handle').textContent = HANDLE;
  $(R + '.cd-viewer').textContent = VIEWER;
  $$(R + '.cd-when').forEach(function (e) { e.textContent = WHEN; });
  $(R + '.cd-ph').textContent = PLACEHOLDER;
  $(R + '.cd-pl').textContent = POST;
  $(R + '.cd-word').style.top = (GROUP_Y - BAND_Y) + 'px';
})();

// ---- the dark copies: one per frame the letters are on screen, each showing its own tile of masks.png
var F0 = Math.round(A * 30), FA = Math.max(0, Math.floor(tType * 30) - F0 - 1), FB = Math.ceil((tLast + 0.05) * 30) - F0;
var lt = document.getElementById('{{ID}}-lt');
if (SPLIT && !$(R + '.cd-dk')) {
  for (var k = FA; k <= FB; k++) {
    var c = lt.cloneNode(true);
    c.id = '{{ID}}-dk' + k;
    c.className = 'cd-band cd-dk';
    var pos = (-(k % COLS) * 1080) + 'px ' + (-Math.floor(k / COLS) * TILE_H) + 'px';
    c.style.webkitMaskPosition = pos; c.style.maskPosition = pos;
    c.style.webkitMaskSize = (COLS * 1080) + 'px auto'; c.style.maskSize = (COLS * 1080) + 'px auto';
    $(R + '.cd-dks').appendChild(c);
  }
}

// ---- build: the group sits at GROUP_Y; hidden until their beats
gsap.set(R + '.cd-group', { y: GROUP_Y });
gsap.set([R + '.cd-box', R + '.cd-reply', R + '.cd-bmeta', R + '.cd-heart', R + '.cd-f', R + '.cd-t', R + '.cd-r'], { opacity: 0 });
gsap.set(R + '.cd-caret', { opacity: 0 });
gsap.set(R + '.cd-dk', { opacity: 0 });

// the composer slides in, its caret blinks while it waits
tl.fromTo(R + '.cd-box', { opacity: 0, y: -40, scale: 0.96 }, { opacity: 1, y: 0, scale: 1, duration: 0.32, ease: 'power3.out', immediateRender: false }, q(tBox));
for (var bt = tBox, bv = 1; bt < tType + 0.3; bt += 0.2, bv = 1 - bv) tl.set(R + '.cd-caret', { opacity: bv }, q(bt));

// the letters: each pops in big, hangs a beat, then falls with gravity into the field (shrinking to the typed size)
var DARK = tok('--c-dark'), LIGHT = tok('--c-light'), NEG = tok('--c-neg'), SC = TYPED / FONT;
LETTERS.forEach(function (_, i) {
  var a = tType + i * POP, f = a + HANG, land = f + DROP, w = R + '.cd-f' + i, inner = w + ' .cd-fi';
  var dx = cellX(i, TYPED, FIELD_LEFT) + CELLS[i] * TYPED / 2 - (cellX(i, FONT, BIG_LEFT) + CELLS[i] * FONT / 2), dy = TYPED_CY - BIG_CY;
  tl.set(w, { opacity: 1 }, q(a));
  tl.fromTo(inner, { scale: 0.55 }, { scale: 1, duration: 0.1, ease: 'back.out(2.4)', immediateRender: false }, q(a));
  tl.fromTo(w, { y: 0 }, { y: dy, duration: DROP, ease: 'power2.in', immediateRender: false }, q(f));
  tl.fromTo(w, { x: 0 }, { x: dx, duration: DROP, ease: 'power3.in', immediateRender: false }, q(f));
  tl.fromTo(inner, { scale: 1 }, { scale: SC, duration: DROP, ease: 'power3.in', immediateRender: false }, q(f + 0.001));
  // the catch: the big letter becomes the typed one, the field takes the hit
  tl.set(w, { opacity: 0 }, q(land));
  tl.set(R + '.cd-t' + i, { opacity: 1 }, q(land));
  tl.fromTo(R + '.cd-t' + i, { scaleY: 0.55, scaleX: 1.3, y: 6 }, { scaleY: 1, scaleX: 1, y: 0, duration: 0.2, ease: 'back.out(3)', immediateRender: false }, q(land));
  tl.fromTo(R + '.cd-box', { y: 0 }, { y: Math.max(3, 9 - i), duration: 0.04, ease: 'power2.out', immediateRender: false }, q(land));
  tl.to(R + '.cd-box', { y: 0, duration: 0.18, ease: 'back.out(3)' }, q(land + 0.04));
  tl.set(R + '.cd-caret', { opacity: 1, x: cellX(i + 1, TYPED, 0) + 2 }, q(land));
  if (i === 0) {
    tl.set(R + '.cd-ph', { opacity: 0 }, q(land));
    tl.to(R + '.cd-post', { backgroundColor: DARK, color: LIGHT, duration: 0.12, ease: 'power2.out' }, q(land));
  }
});
// the light/dark split: frame k of the window shows dark copy k
if (SPLIT) {
  for (var m = FA; m <= FB; m++) {
    on('#{{ID}}-dk' + m, (F0 + m) / 30);
    off('#{{ID}}-dk' + m, (F0 + m + 1) / 30);
  }
}

// Post presses: the comment posts and lifts to make room
tl.to(R + '.cd-post', { scale: 0.84, duration: 0.06, ease: 'power2.in' }, q(tPost));
tl.to(R + '.cd-post', { scale: 1, duration: 0.18, ease: 'back.out(2)' }, q(tPost + 0.06));
tl.set(R + '.cd-caret', { opacity: 0 }, q(tPost + 0.06));
tl.to(R + '.cd-post', { opacity: 0, scale: 0.6, duration: 0.12, ease: 'power2.in' }, q(tLift - 0.02));
tl.fromTo(R + '.cd-heart', { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.22, ease: 'back.out(2)', immediateRender: false }, q(tLift + 0.08));
tl.to(R + '.cd-txt', { y: 18, duration: 0.24, ease: 'power3.out' }, q(tLift));
tl.fromTo(R + '.cd-bmeta', { opacity: 0, y: -8 }, { opacity: 1, y: 0, duration: 0.22, ease: 'power3.out', immediateRender: false }, q(tLift));
tl.to(R + '.cd-box', { y: LIFT, duration: 0.3, ease: 'power3.out' }, q(tLift));

// the reply drops in under it, the thread draws, its words land on theirs
tl.fromTo(R + '.cd-reply', { opacity: 0, y: -36, scaleY: 0.7 }, { opacity: 1, y: 0, scaleY: 1, duration: 0.26, ease: 'back.out(1.6)', immediateRender: false }, q(tReply));
tl.to(R + '.cd-tp', { strokeDashoffset: 0, duration: 0.24, ease: 'power2.out' }, q(tReply + 0.08));
tWords.forEach(function (t, i) {
  tl.fromTo(R + '.cd-r' + i, { opacity: 0, y: 10 }, { opacity: 1, y: 0, duration: 0.14, ease: 'power3.out', immediateRender: false }, q(t));
});
// the like
if (tLike) {
  tl.set(R + '.cd-hp', { fill: NEG, stroke: NEG }, q(tLike));
  tl.fromTo(R + '.cd-heart', { scale: 1.45 }, { scale: 1, duration: 0.3, ease: 'back.out(2.2)', immediateRender: false }, q(tLike));
}

// out: the thread floats up and away, gone at B
tl.to(R + '.cd-thread', { opacity: 0, duration: 0.08, ease: 'power2.in' }, q(tOut));
tl.to(R + '.cd-box', { y: LIFT - 120, opacity: 0, duration: 0.2, ease: 'power3.in' }, q(tOut));
tl.to(R + '.cd-reply', { y: -120, opacity: 0, duration: 0.2, ease: 'power3.in' }, q(tOut + 0.05));
