// follow-chip (layer: top), the sign-off, from A to the last frame. A profile chip rises just before the speaker's
// "make sure to follow", the Follow button presses to Following on "follow" (the label slides out, a check draws),
// and a short line slides in under the handle on its word. Captions stay on: the chip sits over the band's top edge.
// Supply: run gen.py (PY fx/<id>/gen.py <project>): it fills in HANDLE from the creator's style pack and copies their
// headshot in (until then a neutral person glyph stands in: a placeholder). Then set SUB and the cue words below.
// A cue finds the first matching spoken word at or after the previous beat (wordAt); a missing one uses its fallback
// in T (seconds after A, or after the previous beat). SUB comes in only when SUB_ON is spoken ('' = T.fsub after the
// press), so the chip never claims a line the speaker didn't say.

// ---- gen.py rewrites the lines between these two markers ----
var HANDLE = '@yourhandle';               // the creator's handle (gen.py: the pack's handle, else its site, else its name)
var HEADSHOT = '';                        // a square photo in this folder (gen.py copies it in); '' = the placeholder glyph
// ---- end of gen.py's block ----
var SUB = 'Daily tips';                   // the line under the handle; '' = none
var LABELS = ['Follow', 'Following'];     // the button, before and after the press
var CHIP_ON = 'make';                     // the chip rises just before this word ("make sure to follow")
var PRESS_ON = 'follow';                  // the button presses on this word
var SUB_ON = 'daily';                     // the line under the handle comes in on this word
var T = { lead: 0.03, fchip: 0.03, fpress: 0.33, fsub: 0.54 };   // the chip leads its word; fallbacks
var HANDLE_W = 300;                       // px the handle may run before the button: a longer one shrinks to fit

var R = '#{{ID}} ';
function $(s) { return document.querySelector(s); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function word(w, after, fallback) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? fallback : t; }
var GLYPH = '<svg viewBox="0 0 48 48" data-placeholder="headshot"><circle class="fc-ph0" cx="24" cy="24" r="24"/>' +
            '<circle class="fc-gl" cx="24" cy="19" r="8"/><path class="fc-gl" d="M8 46 C9.5 34 16 29.5 24 29.5 C32 29.5 38.5 34 40 46 Z"/></svg>';

// build the chip once, from the constants
(function () {
  var av = $(R + '.fc-av');
  if (!av || av.childNodes.length) return;
  av.innerHTML = HEADSHOT ? '<img src="fx/{{ID}}/' + HEADSHOT + '" alt="">' : GLYPH;
  $(R + '.fc-handle').textContent = HANDLE;
  $(R + '.fc-sub').textContent = SUB;
  $(R + '.fc-b0 span').textContent = LABELS[0];
  $(R + '.fc-b1 span').textContent = LABELS[1];
})();

// a long handle keeps its fx.html size as a maximum and only shrinks, once the pack's fonts are in
function fit() {
  var h = $(R + '.fc-handle');
  if (!h.dataset.max) h.dataset.max = parseFloat(getComputedStyle(h).fontSize);
  var max = +h.dataset.max;
  h.style.fontSize = max + 'px';
  if (h.scrollWidth > HANDLE_W) h.style.fontSize = (max * HANDLE_W / h.scrollWidth).toFixed(2) + 'px';
}
fit();
if (document.fonts && document.fonts.load) {
  document.fonts.load('800 36px ' + tok('--font-text'), HANDLE).catch(function () {}).then(fit, fit);
  document.fonts.ready.then(fit);
}

// times, each on its word
var CHIP = Math.max(A, word(CHIP_ON, A, A + T.fchip + T.lead) - T.lead);
var PRESS = word(PRESS_ON, CHIP, CHIP + T.fpress);
var SUBT = SUB ? (SUB_ON ? word(SUB_ON, PRESS, null) : PRESS + T.fsub) : null;

gsap.set([R + '.fc-chip', R + '.fc-b1', R + '.fc-sub'], { opacity: 0 });
gsap.set(R + '.fc-chk', { strokeDasharray: 30, strokeDashoffset: 30 });

// the chip rises over the captions band
tl.fromTo(R + '.fc-chip', { opacity: 0, y: 46, scale: 0.96 }, { opacity: 1, y: 0, scale: 1, duration: 0.32, ease: 'power3.out', immediateRender: false }, q(CHIP));

// the press: the button dips, the Follow label slides out, Following slides in and its check draws
tl.to(R + '.fc-btn', { scale: 0.88, duration: 0.067, ease: 'power2.in' }, q(PRESS));
tl.to(R + '.fc-btn', { scale: 1, duration: 0.26, ease: 'back.out(1.8)' }, q(PRESS + 0.067));
tl.to(R + '.fc-b0', { yPercent: -100, opacity: 0, duration: 0.18, ease: 'power3.in' }, q(PRESS + 0.067));
tl.fromTo(R + '.fc-b1', { yPercent: 100, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.22, ease: 'power3.out', immediateRender: false }, q(PRESS + 0.1));
tl.to(R + '.fc-chk', { strokeDashoffset: 0, duration: 0.22, ease: 'power2.out' }, q(PRESS + 0.2));

// the line under the handle, on its word
if (SUBT !== null) {
  tl.to(R + '.fc-handle', { y: -18, duration: 0.24, ease: 'power3.out' }, q(SUBT - 0.02));
  tl.fromTo(R + '.fc-sub', { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.24, ease: 'power3.out', immediateRender: false }, q(SUBT - 0.02));
}
