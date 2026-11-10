// storyboard-deck-note (layer: top). Part 3 of 3: "I just leave it a note". Picks up the flip's pile on its first
// frame (the hero face down, showing its plan).
//   TURN_ON    the hero turns back over to its frame (a full turn, a lift): the BEFORE frame
//   NOTE_ON    a comment slides in beside it (headshot, name, "on p08") and the note types in, a caret leading,
//              finishing by the end of TYPE_TO; as MARK_WORD types, the problem on the frame gets marked (with the
//              default BEFORE: the two black bars, in the negative colour)
//   FIX_ON     the frame wipes to AFTER behind an accent edge, the marks go, a check lands on the card's corner
//   B - OUT    the pile flicks off to the right, the note off to the left (a move, never a fade: opacity on 3D
//              cards ghosts the pile)
// Reach for it when the line says "I just leave it a note", "I explain what I want", any feedback loop.
// Supply: the note and who leaves it (below). The before/after frames are written by fx/storyboard-deck/gen.py
// (BEFORE / AFTER there: by default the hero's board frame letterboxed, then full height). Your headshot: a square
// image in this folder named in HEADSHOT (until then a token circle with the name's initials).
// Change only these constants:
var NOTE = 'Fill the screen, no black bars.';   // the note that types in (keep it short: it types in about a second)
var MARK_WORD = 'bars';                      // the marks land as this word types ('' = when the typing ends)
var NAME = 'Your Name';                      // who leaves the note
var HEADSHOT = '';                           // e.g. 'headshot.jpg' in this folder; '' = initials in a token circle
var TURN_ON = 'I', NOTE_ON = 'leave', TYPE_TO = 'it', FIX_ON = 'note';   // the spoken words each beat lands on
var T = { turn: 0.10, note: 0.67, typed: 1.19, fix: 1.52, out: 0.12 };   // fallbacks (s after A); out = s before B
var HX = 640, HY = 236;                      // the hero card's top left (keep in step with the flip)
var TILT = [-2.2, 1.8, 0, 2.6, -1.4, -3.0, 1.2, 2.2];
var DX = [-8, 2, 0, 4, -12, -2, -6, 3], DY = [6, -5, 0, 9, 4, -8, 10, -3];

var st = document.getElementById('{{ID}}-stage');
var N = +st.getAttribute('data-cards') || 8, HERO = +st.getAttribute('data-hero') || 0;
function cue(w, fb, after) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }
function span(w, fb, after) { var s = w ? wordSpan(w, after) : null; return (s === null || s[0] >= B) ? A + fb : s[1]; }
for (var k = 0; k < N; k++) {
  gsap.set('#{{ID}}-c' + k, { x: HX + DX[k % 8], y: HY + DY[k % 8], scale: 1, rotation: TILT[k % 8], rotationY: k === HERO ? 180 : 0,
    zIndex: k === HERO ? 200 : 10 + k, transformOrigin: '50% 50%' });
}

// the comment: headshot (or initials), name, the beat it is on, the note one character at a time
(function () {
  var p = document.getElementById('{{ID}}-typed');
  if (!p || p.childNodes.length) return;
  var av = document.querySelector('#{{ID}} .{{ID}}-av');
  if (HEADSHOT) av.innerHTML = '<img src="fx/{{ID}}/' + HEADSHOT + '" alt="">';
  else av.textContent = NAME.split(/\s+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0].toUpperCase(); }).join('');
  document.querySelector('#{{ID}} .{{ID}}-name').textContent = NAME;
  var strip = document.querySelector('#{{ID}}-c' + HERO + ' .{{ID}}-strip b');
  document.querySelector('#{{ID}} .{{ID}}-on').textContent = 'on ' + (strip ? strip.textContent : 'this beat');
  for (var i = 0; i < NOTE.length; i++) { var s = document.createElement('i'); s.textContent = NOTE[i]; p.appendChild(s); }
  var c = document.createElement('span'); c.className = '{{ID}}-caret'; p.appendChild(c);
  // the comment is as tall as the whole note once typed (measured with every character showing)
  function size() {
    var m = document.createElement('p');
    m.className = '{{ID}}-text'; m.style.height = 'auto'; m.style.visibility = 'hidden'; m.style.position = 'absolute';
    m.style.width = p.offsetWidth + 'px'; m.textContent = NOTE + '\u00a0\u00a0';
    p.parentNode.appendChild(m);
    p.style.height = m.offsetHeight + 'px';
    p.parentNode.removeChild(m);
  }
  size();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(size);
})();
gsap.set('#{{ID}}-chip', { opacity: 0, x: -40, scale: 0.96, transformOrigin: '560px 40px' });
gsap.set('#{{ID}}-typed i', { display: 'none' });
gsap.set('#{{ID}} .{{ID}}-bar', { opacity: 0 });
gsap.set('#{{ID}}-edge', { opacity: 0, x: 0 });
gsap.set('#{{ID}}-check', { x: HX + 352, y: HY - 22, scale: 0, transformOrigin: '50% 50%', zIndex: 300 });

var tTurn = cue(TURN_ON, T.turn, A), tNote = cue(NOTE_ON, T.note, tTurn + 0.3);
var tTyped = Math.max(tNote + 0.4, span(TYPE_TO, T.typed, tNote + 0.01));
var tFix = Math.max(tTyped + 0.06, cue(FIX_ON, T.fix, tNote + 0.01));
var tOut = B - T.out;

// back to the front: a full turn, a lift
tl.fromTo('#{{ID}}-c' + HERO, { rotationY: 180 }, { rotationY: 360, duration: 0.42, ease: 'power3.inOut', immediateRender: false }, q(tTurn));
tl.to('#{{ID}}-c' + HERO, { y: HY - 22, scale: 1.035, duration: 0.21, ease: 'power2.out' }, q(tTurn));
tl.to('#{{ID}}-c' + HERO, { y: HY, scale: 1, duration: 0.21, ease: 'power2.in' }, q(tTurn + 0.21));

// the note slides in and types
tl.fromTo('#{{ID}}-chip', { opacity: 0, x: -40, scale: 0.96 }, { opacity: 1, x: 0, scale: 1, duration: 0.22, ease: 'power3.out', immediateRender: false }, q(tNote));
var chars = document.querySelectorAll('#{{ID}}-typed i'), t0 = tNote + 0.1, dt = Math.max(0.005, (tTyped - t0) / chars.length);
for (var i = 0; i < chars.length; i++) tl.set(chars[i], { display: 'inline' }, q(t0 + i * dt));
tl.set('#{{ID}}-typed .{{ID}}-caret', { display: 'none' }, q(tTyped + 0.1));

// the problem gets marked as its word types
var mk = MARK_WORD ? NOTE.toLowerCase().indexOf(MARK_WORD.toLowerCase()) : -1;
var tMark = Math.min(tFix - 0.25, mk < 0 ? tTyped : t0 + (mk + MARK_WORD.length) * dt);
tl.fromTo('#{{ID}} .{{ID}}-bar', { opacity: 0, scale: 1.05 }, { opacity: 1, scale: 1, duration: 0.14, ease: 'power3.out', stagger: 0.05, immediateRender: false }, q(tMark));

// the fix: the frame wipes to AFTER behind an accent edge, a check lands
tl.to('#{{ID}} .{{ID}}-bar', { opacity: 0, duration: 0.06 }, q(tFix));
tl.set('#{{ID}}-edge', { opacity: 1 }, q(tFix));
tl.fromTo('#{{ID}}-after', { clipPath: 'inset(0% 100% 0% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', duration: 0.12, ease: 'power2.inOut', immediateRender: false }, q(tFix));
tl.fromTo('#{{ID}}-edge', { x: 0 }, { x: 368, duration: 0.12, ease: 'power2.inOut', immediateRender: false }, q(tFix));
tl.set('#{{ID}}-edge', { opacity: 0 }, q(tFix + 0.13));
tl.fromTo('#{{ID}}-check', { scale: 0 }, { scale: 1, duration: 0.14, ease: 'back.out(1.8)', immediateRender: false }, q(tFix + 0.08));
tl.fromTo('#{{ID}}-tick', { attr: { 'stroke-dashoffset': 40 } }, { attr: { 'stroke-dashoffset': 0 }, duration: 0.1, ease: 'power2.out', immediateRender: false }, q(tFix + 0.12));

// out before B: the pile flicks off right, the note off left
tl.to('#{{ID}}-stage', { x: 660, duration: 0.1, ease: 'power3.in' }, q(tOut));
tl.to('#{{ID}}-chip', { x: -1340, duration: 0.1, ease: 'power3.in' }, q(tOut));
