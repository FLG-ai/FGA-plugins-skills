// screenplay-page (layer: top, above the speaker; the page carries the words, so the captions step aside). The
// speaker's own lines, typeset as a screenplay:
//   in        the page slides straight up over the speaker on the first beat (expo.out) and squares the frame
//   page      the end of the previous scene (dim), CUT TO:, the scene heading, the character cue and parenthetical,
//             the dialogue: what was already said dim, the line being spoken full ink; then CUT TO:, the next scene
//             heading and its first line, dim. All in the pack's mono face, true screenplay columns
//   read      an accent highlighter sweeps under each word on the moment it is spoken; never under a heading, a cue
//             or CUT TO:
//   drift     the page creeps up a little for the rest of the beat, like a read-along; out hard on B
// Reach for it on "movie script", "like a script", "my lines", any line about writing or the script itself. Give the
// window a KARAOKE hide (edit.py: KARAOKE = dict(hide=[(start, end)])) so the captions don't print over the page.
// Supply: nothing but labels. The lines come from words.json: the sentences spoken inside the window are the live
// line, the ones before and after fill the page (BEFORE / TAIL / AFTER say how many). Set NAME to the creator's name.
// Change only these constants:
var NAME = 'SPEAKER';                       // the character cue (the creator's name, in caps)
var PAREN = '(to camera)';                  // the parenthetical under the cue; '' = none
var SCENE = 'INT. HOME OFFICE - DAY';       // the scene heading over the live line
var NEXT_SCENE = 'INT. HOME OFFICE - CONTINUOUS';   // the heading of the next scene, dim; '' = no next scene
var CUT = 'CUT TO:';                        // the transition printed between scenes
var TAIL = 1;                               // sentences printed above as the end of the previous scene (dim)
var BEFORE = 2;                             // sentences already said in this scene, above the live line (dim)
var AFTER = 1;                              // sentences of the next scene (dim)
var COLS = 24;                              // the dialogue column, in characters (cue, CUT TO: and headings hang off it)
var CENTER_Y = 845;                         // the page block centres on this y (captions are hidden over the beat)
var DRIFT = 36;                             // px the page creeps up over the beat

var LH = 42;                                // one row (the sheet's line-height); one column = 1ch of the mono face
var DCOL = 4;                               // the dialogue column starts 4 columns in from the scene headings

// ---- the sentences around the window, from words.json
var sents = [], cur = [];
WORDS.forEach(function (w, i) {
  cur.push({ s: w[0], e: w[1], t: w[2] });
  if (/[.?!]["”']?$/.test(w[2]) || i === WORDS.length - 1) { sents.push(cur); cur = []; }
});
var live = [];
sents.forEach(function (s, i) { if (s.some(function (w) { return w.s >= A - 0.001 && w.s < B; })) live.push(i); });
if (!live.length) { var best = 0; sents.forEach(function (s, i) { if (s[0].s < B) best = i; }); live = [best]; }
var i0 = live[0], i1 = live[live.length - 1];
var before = sents.slice(Math.max(0, i0 - BEFORE), i0);
var tail = sents.slice(Math.max(0, i0 - BEFORE - TAIL), Math.max(0, i0 - BEFORE));
var after = sents.slice(i1 + 1, i1 + 1 + AFTER);
var liveWords = [];
live.forEach(function (i) { liveWords = liveWords.concat(sents[i]); });

// wrap words into rows of at most COLS characters
function wrap(words) {
  var rows = [], row = [], n = 0;
  words.forEach(function (w) {
    var len = w.t.length;
    if (row.length && n + 1 + len > COLS) { rows.push(row); row = []; n = 0; }
    n += (row.length ? 1 : 0) + len;
    row.push(w);
  });
  if (row.length) rows.push(row);
  return rows;
}
function flat(list) { var o = []; list.forEach(function (s) { o = o.concat(s); }); return o; }

// ---- the page, row by row: [col, text or words, class]; col 'cue' centres over the dialogue, 'cut' hangs right
var R = [];
function blank() { R.push(null); }
function text(col, t, cls) { R.push([col, t, cls || '']); }
wrap(flat(tail)).forEach(function (r) { R.push([DCOL, r, 'dim']); });
if (tail.length) { blank(); text('cut', CUT, 'dim'); blank(); }
text(0, SCENE, 'hd'); blank();
text('cue', NAME); if (PAREN) text('cue', PAREN);
// the dialogue: what was said before the window dim, the live words full ink
var dl = flat(before).map(function (w) { return { s: w.s, e: w.e, t: w.t, dim: true }; })
  .concat(liveWords.map(function (w) { return { s: w.s, e: w.e, t: w.t, dim: w.s < A - 0.001 }; }));
wrap(dl).forEach(function (r) { R.push([DCOL, r, '']); });
if (NEXT_SCENE || after.length) { blank(); text('cut', CUT); blank(); }
if (NEXT_SCENE) { text(0, NEXT_SCENE, 'hd'); blank(); }
if (after.length) { text('cue', NAME, 'dim'); wrap(flat(after)).forEach(function (r) { R.push([DCOL, r, 'dim']); }); }

// ---- build: the dialogue column is centred on x 540 (1ch = one column of the pack's mono face)
var sheet = document.getElementById('{{ID}}-sheet');
var tx = document.getElementById('{{ID}}-tx'), mk = document.getElementById('{{ID}}-mk');
var Y0 = Math.round(CENTER_Y - R.length * LH / 2);
var X0 = 'calc(540px - ' + (DCOL + COLS / 2) + 'ch)';
var marks = [];
function colOf(c, t) {
  if (c === 'cue') return DCOL + (COLS - t.length) / 2;
  if (c === 'cut') return DCOL + COLS - t.length;
  return c;
}
R.forEach(function (r, ri) {
  if (!r) return;
  var y = Y0 + ri * LH, el = document.createElement('div');
  el.className = '{{ID}}-l';
  el.style.top = y + 'px';
  if (typeof r[1] === 'string') {
    el.style.left = 'calc(' + X0 + ' + ' + colOf(r[0], r[1]) + 'ch)';
    el.textContent = r[1];
    if (r[2]) el.className += ' {{ID}}-' + r[2];
  } else {
    el.style.left = 'calc(' + X0 + ' + ' + r[0] + 'ch)';
    if (r[2]) el.className += ' {{ID}}-' + r[2];
    var c = r[0];
    r[1].forEach(function (w, i) {
      var s = document.createElement('span');
      s.textContent = w.t + (i < r[1].length - 1 ? ' ' : '');
      if (w.dim && r[2] !== 'dim') s.className = '{{ID}}-dim';
      el.appendChild(s);
      var spoken = !w.dim && r[2] !== 'dim' && w.s >= A - 0.001 && w.s < B;
      if (spoken) {                          // one stroke per spoken word, a hair wider than the word at a row's ends
        var m = document.createElement('i'), first = i === 0, last = i === r[1].length - 1;
        m.className = '{{ID}}-m';
        m.style.left = 'calc(' + X0 + ' + ' + c + 'ch - ' + (first ? 6 : 0) + 'px)';
        m.style.width = 'calc(' + (w.t.length + (last ? 0 : 1)) + 'ch + ' + ((first ? 6 : 0) + (last ? 6 : 0)) + 'px)';
        m.style.top = (y + 3) + 'px';
        mk.appendChild(m);
        marks.push([m, w.s, w.e]);
      }
      c += w.t.length + 1;
    });
  }
  tx.appendChild(el);
});
// rows sit one line apart on purpose (line-height = font size): tell the layout audit on every text element
Array.prototype.slice.call(document.querySelectorAll('#{{ID}} .{{ID}}-l, #{{ID}} .{{ID}}-l span')).forEach(function (e) {
  e.setAttribute('data-layout-allow-overlap', '');
});

// ---- motion
gsap.set('#{{ID}} .{{ID}}-m', { scaleX: 0 });
gsap.set('#{{ID}}-page', { y: 2100 });
var IN = 0.34;
tl.fromTo('#{{ID}}-page', { y: 2100 }, { y: 0, duration: IN, ease: 'expo.out', immediateRender: false }, q(A));
if (B - A - IN > 0.1) tl.fromTo('#{{ID}}-page', { y: 0 }, { y: -DRIFT, duration: B - A - IN, ease: 'none', immediateRender: false }, q(A + IN));
// the highlighter: one stroke per word, left to right, on its onset, sized to the gap to the next word
marks.forEach(function (m, i) {
  var next = i + 1 < marks.length ? marks[i + 1][1] : m[2];
  var d = Math.min(0.24, Math.max(0.1, (next - m[1]) * 0.8));
  tl.fromTo(m[0], { scaleX: 0 }, { scaleX: 1, duration: d, ease: 'power2.out', immediateRender: false }, q(Math.max(A + 0.12, m[1])));
});
