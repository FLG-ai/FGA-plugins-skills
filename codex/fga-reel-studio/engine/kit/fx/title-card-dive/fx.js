// title-card-dive (layer: cam). "A few minutes later, this is the video": a documentary title card, then the shot
// shrinks into a phone that is playing this very video, and the camera dives back into the screen.
//   A            hard cut to the dark ground (put A on a picture cut: the card covers it). The video's own running
//                timecode (hh:mm:ss:ff, mono, accent) ticks frame by frame over the title.
//   TITLE        the title lines rise out of their masks one by one, each on its spoken word, in display caps; the
//                accent rule draws under them on RULE_ON
//   PHONE_ON     hard cut back to the live shot, which at once shrinks (0.42 s) into a generic phone on the dark
//                ground; a minimal player fades up on the screen (the true time / the video's length, a thin
//                progress bar that moves with the video)
//   PUSH_ON      the camera pushes in on the phone (1.12x, 0.2 s)
//   DIVE_ON      the dive: the phone grows back to full frame, accelerating, the player fading; on the effect's last
//                frame the screen IS the frame, identical to the picture under it, so the out at B is invisible
// Reach for it when the line says "a few minutes later", "this is the video", "exactly what you're seeing now".
// Supply: the title lines and the spoken words they land on. Nothing else: the screen is a synced copy of clean.mp4
// in the live grade (class g). Start the FX on a picture cut. If B is also a picture cut, the dive lands on the old
// shot's last frame and the cut follows (no handle needed).
// Change only these constants:
var TITLE = [['A few', 'few'], ['minutes', 'minutes'], ['later', 'later']];   // [line, the spoken word it rises on]
var RULE_ON = 'later';                      // the accent rule draws on this word
var PHONE_ON = 'this';                      // the card cuts out and the shot starts shrinking into the phone
var PUSH_ON = 'the';                        // the camera pushes in on the phone
var DIVE_ON = 'video';                      // the dive back into the screen starts on this word
var T = { title: [0.09, 0.38, 0.66], rule: 0.66, phone: 0.95, push: 1.52, dive: 1.81 };   // fallbacks, s after A
var SCREEN = [540, 800, 500];               // the phone's screen: centre x, centre y, width (px on 1080x1920)
var PUSH = 1.12;                            // how far the camera pushes in before the dive
var SHRINK = 0.42;                          // how long the shot takes to shrink into the phone (s)

var FPS = 30;
function fq(i) { return Math.max(0, i / FPS - 0.002); }           // frame index -> its time on the timeline
function fi(t) { return Math.round(t * FPS); }                    // time -> frame index
function pad(n) { return (n < 10 ? '0' : '') + n; }
function cue(w, fb, after) { var t = w ? wordAt(w, after) : null; return (t === null || t >= B) ? A + fb : t; }
function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }

// ---- the title lines into the card (each line in its own mask)
(function () {
  var box = document.getElementById('{{ID}}-title');
  if (box.childNodes.length) return;
  TITLE.forEach(function (ln, i) {
    var row = document.createElement('div'), w = document.createElement('span');
    row.className = '{{ID}}-ln'; w.className = '{{ID}}-w'; w.id = '{{ID}}-w' + i; w.textContent = ln[0];
    w.setAttribute('data-layout-allow-overlap', '');
    row.appendChild(w); box.appendChild(row);
  });
  // the rule sits a little under the last line, whatever the pack's face
  document.getElementById('{{ID}}-rule').style.top = (720 + TITLE.length * 156 + 30) + 'px';
})();
// the lines keep their fx.html size unless one is wider than 960px in the pack's display face
function fit() {
  var box = document.getElementById('{{ID}}-title');
  box.style.fontSize = '150px';
  var w = Math.max.apply(null, $$('#{{ID}} .{{ID}}-w').map(function (e) { return e.offsetWidth; }));
  if (w > 960) box.style.fontSize = (150 * 960 / w).toFixed(2) + 'px';
}
fit();
if (document.fonts && document.fonts.load) {
  document.fonts.load(tok('--display-style') + ' ' + tok('--display-weight') + ' 150px ' + tok('--font-display'),
    TITLE.map(function (l) { return l[0].toUpperCase(); }).join(' ')).then(fit, fit);
  document.fonts.ready.then(fit);
}

// ---- beat times, each on its word (searched in order from A)
var tTitle = [], prev = A;
TITLE.forEach(function (ln, i) { prev = cue(ln[1], T.title[i] !== undefined ? T.title[i] : 0.1 + 0.28 * i, prev); tTitle.push(prev); });
var tRule = cue(RULE_ON, T.rule, tTitle[0]);
var tPhone = cue(PHONE_ON, T.phone, tTitle[tTitle.length - 1] + 0.01);
var tPush = cue(PUSH_ON, T.push, tPhone + SHRINK);
var tDive = cue(DIVE_ON, T.dive, tPush + 0.01);
var LEN = (typeof TOTAL === 'number') ? TOTAL : B;                  // the video's length, for the player
function mss(s) { s = Math.floor(s); return Math.floor(s / 60) + ':' + pad(s % 60); }
document.getElementById('{{ID}}-tot').textContent = ' / ' + mss(LEN);

// ---------------------------------------------------------------- part 1: the title card, hard in, hard out
var C0 = fi(A), C1 = fi(tPhone);
gsap.set('#{{ID}}-card', { opacity: 1 });
tl.set('#{{ID}}-card', { opacity: 0 }, fq(C1));
for (var f = C0; f < C1; f++) {                                    // the video's own running timecode
  tl.set('#{{ID}}-tc', { textContent: '00:' + pad(Math.floor(f / FPS / 60)) + ':' + pad(Math.floor(f / FPS) % 60) + ':' + pad(f % FPS) }, fq(f));
}
gsap.set('#{{ID}} .{{ID}}-w', { yPercent: 105 });
tTitle.forEach(function (t, i) {
  tl.fromTo('#{{ID}}-w' + i, { yPercent: 105 }, { yPercent: 0, duration: 0.22, ease: 'power3.out', immediateRender: false }, q(t));
});
gsap.set('#{{ID}}-rule', { scaleX: 0 });
tl.fromTo('#{{ID}}-rule', { scaleX: 0 }, { scaleX: 1, duration: 0.26, ease: 'expo.out', immediateRender: false }, q(tRule));

// ---------------------------------------------------------------- part 2: the phone
var K = SCREEN[2] / 1080, DX = SCREEN[0] - SCREEN[2] / 2, DY = SCREEN[1] - 1920 * K / 2, R = 99;
var P0 = fi(tPhone), PU = fi(tPush), DV = fi(tDive), END = fi(B) - 1;
gsap.set('#{{ID}}-stage', { opacity: 0, scale: 1, transformOrigin: SCREEN[0] + 'px ' + SCREEN[1] + 'px' });
gsap.set('#{{ID}}-dev', { transformOrigin: '0px 0px', x: 0, y: 0, scale: 1 });
gsap.set('#{{ID}}-scr', { borderRadius: 0 });
gsap.set('#{{ID}}-chrome', { opacity: 0 });
tl.set('#{{ID}}-stage', { opacity: 1 }, fq(P0));
// the live frame (identical to the picture under it) shrinks into the phone
tl.fromTo('#{{ID}}-dev', { x: 0, y: 0, scale: 1 }, { x: DX, y: DY, scale: K, duration: SHRINK, ease: 'power3.inOut', immediateRender: false }, fq(P0));
tl.fromTo('#{{ID}}-scr', { borderRadius: 0 }, { borderRadius: R, duration: SHRINK, ease: 'power3.inOut', immediateRender: false }, fq(P0));
tl.fromTo('#{{ID}}-chrome', { opacity: 0 }, { opacity: 1, duration: 0.12, ease: 'none', immediateRender: false }, fq(P0) + SHRINK * 0.85);
// the player: the true time / the length, the progress of this video
for (var g = P0; g <= END; g++) {
  var p = Math.min(1, (g / FPS) / LEN);
  tl.set('#{{ID}}-fill', { scaleX: p }, fq(g));
  tl.set('#{{ID}}-head', { x: 940 * p }, fq(g));
  if (g === P0 || g % FPS === 0) tl.set('#{{ID}}-now', { textContent: mss(g / FPS) }, fq(g));
}
// the camera pushes in on the phone
tl.fromTo('#{{ID}}-stage', { scale: 1 }, { scale: PUSH, duration: 0.2, ease: 'power3.out', immediateRender: false }, fq(PU));
// the dive into the screen, accelerating, full frame on the last frame
var DD = Math.max(1, END - DV) / FPS;
tl.fromTo('#{{ID}}-stage', { scale: PUSH }, { scale: 1, duration: DD, ease: 'power3.in', immediateRender: false }, fq(DV));
tl.fromTo('#{{ID}}-dev', { x: DX, y: DY, scale: K }, { x: 0, y: 0, scale: 1, duration: DD, ease: 'power3.in', immediateRender: false }, fq(DV));
tl.fromTo('#{{ID}}-scr', { borderRadius: R }, { borderRadius: 0, duration: DD, ease: 'power3.in', immediateRender: false }, fq(DV));
tl.fromTo('#{{ID}}-chrome', { opacity: 1 }, { opacity: 0, duration: Math.min(0.12, DD / 2), ease: 'none', immediateRender: false }, fq(DV) + DD / 2);
