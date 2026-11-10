// double-exposure (layer: cam). The picture is exposure.mp4, pre-rendered by gen.py for this window: a flat field, the
// speaker's live mono silhouette, real footage screened into their chest (gen.py INNER). This file only sets the line
// over it as title credits, the way a film's opening names its crew: a small role line over a spaced-caps name in the
// display face, each landing on its spoken word, each row cutting to the next. Give the window a KARAOKE hide
// (edit.py: KARAOKE = dict(hide=[(start, end)])) so the captions step aside.
// Change only these constants:
var CREDITS = [                    // [role, the word it lands on, NAME, the word it lands on]; NAME '' = the role alone
  ["it could be", "could", "THE IDEA", "idea"],
  ["or", "or", "THE EDIT", "edit"],
  ["or just", "just", "SHOWING UP", "showing"],
];
var AT = 0.10;                     // fallback (s after A) for a first cue word that isn't spoken; later rows +0.45 each
var OFF_ON = '';                   // the credits clear on this word ('' = they hold to the window's end)
var MAX_W = 980;                   // a name wider than this (px, in the pack's face) shrinks to fit

// ---- the rows, built once: a role line over a name line
var host = document.getElementById('{{ID}}-credits');
var rows = CREDITS.map(function (c, k) {
  var d = document.createElement('div');
  d.className = '{{ID}}-credit';
  d.id = '{{ID}}-c' + k;
  var lines = [['{{ID}}-role', c[0]], ['{{ID}}-name', c[2]]].map(function (x) {
    var line = document.createElement('div');
    line.className = '{{ID}}-line';
    var s = document.createElement('span');
    s.className = x[0];
    s.textContent = x[1];
    s.setAttribute('data-layout-allow-overlap', '');
    line.appendChild(s);
    d.appendChild(line);
    return s;
  });
  host.appendChild(d);
  return { row: d, role: lines[0], name: lines[1] };
});

// a long name in a wide face shrinks to fit the frame, never wraps
function fit() {
  rows.forEach(function (r) {
    var n = r.name;
    if (!n.dataset.max) n.dataset.max = parseFloat(getComputedStyle(n).fontSize);
    var max = +n.dataset.max;
    n.style.fontSize = max + 'px';
    var w = n.getBoundingClientRect().width;
    if (w > MAX_W) n.style.fontSize = (max * MAX_W / w).toFixed(2) + 'px';
  });
}
fit();
if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit);

// ---- times: every cue searched in order from A, so a word repeated later in the line lands on its own turn
function cue(w, after, fallback) {
  var t = w ? wordAt(w, after) : null;
  return (t === null || t >= B) ? fallback : t;
}
var prev = A, beats = [];
CREDITS.forEach(function (c, k) {
  var tRole = Math.max(prev, cue(c[1], prev, k ? prev + 0.45 : A + AT));
  var tName = c[2] ? Math.max(tRole, cue(c[3], tRole, tRole + 0.30)) : tRole;
  beats.push([tRole, tName]);
  prev = tName + 0.001;
});
var tOff = OFF_ON ? cue(OFF_ON, prev, B) : B;

// ---- hard cuts, like the inner footage: the role on its word, the name on its word, the next row replaces it
gsap.set('#{{ID}} .{{ID}}-credit', { opacity: 0 });
rows.forEach(function (r, k) {
  var t0 = beats[k][0], t1 = beats[k][1];
  var end = k + 1 < rows.length ? beats[k + 1][0] : tOff;
  if (end <= t0) return;
  gsap.set(r.name, { opacity: 0 });
  tl.set(r.row, { opacity: 1 }, q(t0));
  tl.set(r.name, { opacity: 1 }, q(t1));
  tl.set(r.row, { opacity: 0 }, q(end));
});
