// jiggle-delete (layer: top), for "no X, no Y, nothing" (the icon-strike alternative).
//   A          a light panel lands above the head with a home-screen row of app tiles, settling left to right
//   EDIT_ON    edit mode: EDIT MODE and the app count come in, delete badges pop, every tile wiggles on its own phase
//   each del   on the app's name its badge is tapped (it flashes the negative colour), the tile collapses into it,
//              the count ticks down and the row slides left to close the gap
//   FALL_ON    the tiles left hop and drop out of frame with gravity, the count reads 0, WORD rises in the empty row
//   B - 0.16   the panel lifts away, gone at B
// Supply: nothing for the placeholders: generic tiles drawn from tokens (glyph 'notes', 'files', 'timeline',
// 'presets' or 'grid'). When the speaker names real apps, fetch their icons into your project's copy of this effect
// with the kit's icon fetcher (PY fx/icon-strike/icons.py <project>/fx/<id> "App One" "App Two") and set img on
// each app. Fetched icons belong to their owners: they live in your project's copy, never in the library.
// Change only these constants. A cue word finds the first matching spoken word at or after the previous beat
// (wordAt); when it is missing, its fallback in T (s after A) is used.

var APPS = [                                    // 2 to 4 tiles, left to right
  { label: 'Notes', glyph: 'notes', img: '', del: '' },               // del '' = it stays until FALL_ON
  { label: 'Timeline', glyph: 'timeline', img: '', del: 'timeline' }, // del = the spoken word it is deleted on
  { label: 'Presets', glyph: 'presets', img: '', del: 'presets' },
  { label: 'Files', glyph: 'files', img: '', del: '' }
];
var EDIT_ON = 'No';                             // edit mode starts on this word
var FALL_ON = 'nothing';                        // the tiles left drop on this word
var WORD = 'nothing.';                          // the word that rises in the empty row; '' = none
var MODE = 'Edit mode';                         // the label top left
var UNIT = 'apps';                              // the count top right reads "4 apps"
var T = { edit: 0.12, dels: [0.45, 1.10, 1.30], fall: 1.46, out: 0.16 };   // fallbacks; out: s before B

var R = '#{{ID}} ', SLOTW = 200;
function $(s) { return document.querySelector(s); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function word(w, after, fallback) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? fallback : t; }
var GLYPHS = {
  notes: '<svg viewBox="0 0 168 168"><rect class="s" x="50" y="38" width="68" height="92" rx="9"/><path class="s" d="M64 64h40M64 82h40M64 100h24"/></svg>',
  files: '<svg viewBox="0 0 168 168"><path class="s" d="M40 60v58a8 8 0 0 0 8 8h72a8 8 0 0 0 8-8V72a8 8 0 0 0-8-8H86l-10-12H48a8 8 0 0 0-8 8z"/></svg>',
  timeline: '<svg viewBox="0 0 220 220"><rect class="k1" x="40" y="64" width="72" height="24" rx="6"/><rect class="k2" x="120" y="64" width="60" height="24" rx="6"/>' +
            '<rect class="k2" x="40" y="98" width="38" height="24" rx="6"/><rect class="k1" x="86" y="98" width="94" height="24" rx="6"/>' +
            '<rect class="k1" x="40" y="132" width="108" height="24" rx="6"/><rect class="k2" x="156" y="132" width="24" height="24" rx="6"/>' +
            '<path class="ph" d="M132 54 V172"/><path class="phh" d="M121 44 H143 L132 58 Z"/></svg>',
  presets: '<svg viewBox="0 0 220 220"><path class="tr" d="M68 56 V164 M110 56 V164 M152 56 V164"/>' +
           '<path class="fl" d="M68 126 V164 M110 84 V164 M152 112 V164"/>' +
           '<circle class="kn" cx="68" cy="126" r="16"/><circle class="kn ka" cx="110" cy="84" r="16"/><circle class="kn" cx="152" cy="112" r="16"/></svg>',
  grid: '<svg viewBox="0 0 220 220"><rect class="k1" x="50" y="50" width="54" height="54" rx="12"/><rect class="k2" x="116" y="50" width="54" height="54" rx="12"/>' +
        '<rect class="k2" x="50" y="116" width="54" height="54" rx="12"/><rect class="k1" x="116" y="116" width="54" height="54" rx="12"/></svg>'
};

// build the row once, centred in the panel
(function () {
  var row = $(R + '.jd-row');
  if (row.childNodes.length) return;
  var x0 = (880 - APPS.length * SLOTW) / 2;
  APPS.forEach(function (ap, i) {
    var g = GLYPHS[ap.glyph] ? ap.glyph : 'grid';
    var a = document.createElement('div');
    a.className = 'jd-app jd-a' + i;
    a.setAttribute('data-layout-allow-overlap', '');          // they fall through the frame on purpose
    a.style.left = (x0 + i * SLOTW) + 'px';
    a.innerHTML = '<div class="jd-wig"><div class="jd-tile ' + (ap.img ? '' : 'jd-g-' + g) + '">' +
      (ap.img ? '<img src="fx/{{ID}}/' + ap.img + '" alt="">' : GLYPHS[g]) + '</div><div class="jd-badge"><i></i></div></div>' +
      '<div class="jd-name" data-layout-allow-overlap></div>';
    a.querySelector('.jd-name').textContent = ap.label;
    row.appendChild(a);
  });
  $(R + '.jd-mode').textContent = MODE;
  $(R + '.jd-unit').textContent = UNIT;
  $(R + '.jd-n').textContent = String(APPS.length);
  $(R + '.jd-left span').textContent = WORD;
})();

// ---- times: edit mode, each delete on its name (in order), the drop
var EDIT = Math.max(A + 0.12, word(EDIT_ON, A, A + T.edit)), prev = EDIT, DEL = [];
APPS.forEach(function (ap, i) {
  if (!ap.del) { DEL.push(null); return; }
  var k = DEL.filter(function (d) { return d !== null; }).length;
  var t = word(ap.del, prev, A + (T.dels[k] !== undefined ? T.dels[k] : T.dels[T.dels.length - 1] + 0.3 * k));
  t = Math.max(t, prev + 0.05);
  DEL.push(t); prev = t + 0.01;
});
var FALL = Math.max(prev + 0.2, word(FALL_ON, prev, A + T.fall));

// ---- build
var apps = APPS.map(function (_, i) { return R + '.jd-a' + i; });
gsap.set(R + '.jd-panel', { opacity: 0, y: -36, scale: 0.94, transformOrigin: '440px 165px' });
gsap.set(apps, { opacity: 0, scale: 0.7, y: 18 });
gsap.set(R + '.jd-badge', { scale: 0 });
gsap.set([R + '.jd-mode', R + '.jd-count'], { opacity: 0, y: -8 });
gsap.set(R + '.jd-left span', { yPercent: 108 });

// in: the panel lands, tiles settle in left to right
tl.fromTo(R + '.jd-panel', { opacity: 0, y: -36, scale: 0.94 }, { opacity: 1, y: 0, scale: 1, duration: 0.24, ease: 'power3.out', immediateRender: false }, q(A));
apps.forEach(function (a, i) {
  tl.fromTo(a, { opacity: 0, scale: 0.7, y: 18 }, { opacity: 1, scale: 1, y: 0, duration: 0.22, ease: 'back.out(1.6)', immediateRender: false }, q(A + 0.03 + i * 0.025));
});

// edit mode: the corner labels come in, badges pop, every tile wiggles on its own phase until it goes
tl.to([R + '.jd-mode', R + '.jd-count'], { opacity: 1, y: 0, duration: 0.16, ease: 'power3.out' }, q(EDIT));
apps.forEach(function (a, i) { tl.to(a + ' .jd-badge', { scale: 1, duration: 0.2, ease: 'back.out(2.2)' }, q(EDIT + i * 0.03)); });
function jig(a, t0, t1, ph) {
  for (var k = 0, t = t0; t < t1; k++, t += 0.1) {
    tl.to(a + ' .jd-wig', { rotation: ((k + ph) % 2 ? 1 : -1) * 2.6, duration: 0.1, ease: 'sine.inOut' }, q(t));
  }
}
var PH = [0, 0.033, 0.017, 0.05];
apps.forEach(function (a, i) { jig(a, EDIT + PH[i % 4], DEL[i] !== null ? DEL[i] + 0.3 : FALL + 0.1, i % 2); });

// delete on the name: the badge is pressed (negative colour), the tile collapses into it, the row closes the gap
var NEG = tok('--c-neg'), count = APPS.length, off = APPS.map(function () { return 0; }), gone = APPS.map(function () { return false; });
APPS.forEach(function (_, i) {
  var t = DEL[i];
  if (t === null) return;
  var a = apps[i];
  tl.to(a + ' .jd-badge', { keyframes: [{ scale: 1.32, backgroundColor: NEG, duration: 0.07, ease: 'power2.out' },
    { scale: 1, duration: 0.08, ease: 'power2.in' }] }, q(t + 0.01));
  tl.to(a + ' .jd-wig', { scale: 0, duration: 0.2, ease: 'back.in(1.7)' }, q(t + 0.09));
  tl.to(a + ' .jd-name', { opacity: 0, y: -6, duration: 0.12, ease: 'power2.in' }, q(t + 0.11));
  tl.set(R + '.jd-n', { textContent: String(--count) }, q(t + 0.25));
  gone[i] = true;
  for (var j = i + 1, k = 0; j < APPS.length; j++) {
    if (gone[j]) continue;
    off[j] -= SLOTW;
    tl.to(apps[j], { x: off[j], duration: 0.2, ease: 'power3.inOut' }, q(t + 0.14 + 0.02 * k++));
  }
});

// the drop: what is left hops and falls out with gravity, the empty row gets its word
var left = APPS.map(function (_, i) { return i; }).filter(function (i) { return DEL[i] === null; });
left.forEach(function (i, k) {
  var a = apps[i], t = FALL + (k - (left.length - 1) / 2) * 0.04;
  tl.to(a, { y: -24, duration: 0.08, ease: 'power2.out' }, q(t));
  tl.to(a, { y: 1760, x: off[i] + [-30, 40, -20, 30][k % 4], rotation: [-22, 18, -14, 20][k % 4], duration: 0.36, ease: 'power2.in' }, q(t + 0.08));
  tl.set(a, { opacity: 0 }, q(t + 0.45));
});
tl.set(R + '.jd-n', { textContent: '0' }, q(FALL + 0.14));
if (WORD) tl.to(R + '.jd-left span', { yPercent: 0, duration: 0.26, ease: 'power3.out' }, q(FALL + 0.16));

// out: the panel lifts away, gone at B
tl.to(R + '.jd-panel', { opacity: 0, y: -24, scale: 0.96, duration: 0.14, ease: 'power2.in' }, q(B - T.out));
