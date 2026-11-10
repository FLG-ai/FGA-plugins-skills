// video-backdrop (layer: behind, under the speaker's cutout) + video-backdrop-label (layer: top). "I recorded a
// walkthrough":
//   CUES      the walkthrough replaces the room behind the speaker, full bleed, darkened a touch: each chapter
//             PUSHES in from the right in 0.24 s centred on its word, the old one sliding a third of the way left and
//             darkening as it goes (parallax), each new clip settling from a slight zoom
//   OUT_ON    at the end of the line the last chapter pushes out left and the real room comes back, gone by B
// The label (video-backdrop-label) names each chapter on the same words, one label at a time.
// Reach for it on "I recorded a video walking you through it", a course, a demo: the full-bleed alternative to
// video-card. Needs a CUT_WINDOWS entry over its window (the backdrop sits behind the speaker).
// Supply: your screen recording. mkclips.py picks the moments that move (the frame-difference energy pass of
// video-card/energy.py), cuts a 9:16 column of the screen for each chapter (leave the webcam box out: you are in
// front), sped up so the movement reads, and prints the <video> tags to paste over the placeholder blocks in fx.html:
//   PY fx/<id>/mkclips.py <project> [<id>] <recording.mov> [--col 0.35] [--rate 1.5]
// Then set PLACEHOLDER = ''. Until then the chapters are token-built PLACEHOLDER screens that scroll.
// Keep CUES, AT and OUT_ON the same in video-backdrop-label (its CHAPTERS carry the same words).
// Change only these constants:
var CUES = ['I', 'recorded', 'a'];  // the word each chapter pushes in on, in order (up to the 4 chapters in fx.html)
var AT = [0.10, 0.53, 0.95, 1.30];  // fallbacks (s after A) for cue words not found
var OUT_ON = '';                    // the room comes back on this word; '' or not found: T.out before B
var PLACEHOLDER = 'Your screen recording';   // the placeholder screens' label (numbered); '' once the clips are yours
var T = {
  push: 0.24,                       // each push, centred on its word
  park: -360,                       // where the old chapter slides to (px), a third of the way
  dark: 0.75,                       // how dark the old chapter gets on its way out (the dim layer)
  zoom: 1.08,                       // each new clip settles from this scale over 0.7 s
  scroll: 520,                      // px a placeholder pane scrolls across its chapter (its movement)
  out: 0.24                         // the last chapter pushes out this long before B
};

function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
var ID = '{{ID}}', N = Math.min(CUES.length, 4);

// ---- chapter times: on their words, searched in order from A; the push never starts before A
var at = [], prev = A;
for (var i = 0; i < N; i++) {
  var w = wordAt(CUES[i], prev);
  at.push((w === null || w >= B - T.out) ? A + AT[i] : w);
  prev = at[i];
}
var tOut = OUT_ON ? wordAt(OUT_ON, at[N - 1]) : null;
tOut = Math.min(tOut === null ? B : tOut, B - T.out);
function pushAt(k) { return Math.max(A, at[k] - T.push / 2); }

// ---- build: the chapters past N stay hidden, the placeholders get their numbered labels
for (var h = N + 1; h <= 4; h++) { var e = document.getElementById(ID + '-c' + h); if (e) e.style.display = 'none'; }
$$('#' + ID + ' .' + ID + '-n').forEach(function (e, k) {
  e.textContent = PLACEHOLDER ? PLACEHOLDER + ' ' + (k + 1) : '';
  e.setAttribute('data-layout-allow-overlap', '');
  e.setAttribute('data-layout-allow-occlusion', '');
  e.setAttribute('data-layout-allow-overflow', '');
});
gsap.set('#' + ID + ' .' + ID + '-ch', { x: 1080 });

// ---- each chapter pushes in on its word; the one before slides left in parallax, darkens, then goes
for (var k = 0; k < N; k++) {
  var c = '#' + ID + '-c' + (k + 1), s = q(pushAt(k)), end = k + 1 < N ? pushAt(k + 1) + T.push : tOut + 0.22;
  tl.fromTo(c, { x: 1080 }, { x: 0, duration: T.push, ease: 'power3.inOut', immediateRender: false }, s);
  tl.fromTo(c + ' .' + ID + '-m', { scale: T.zoom }, { scale: 1, duration: 0.7, ease: 'power2.out', immediateRender: false }, s);
  // a placeholder moves like a recording: its pane scrolls and the cursor drifts across the chapter
  if (document.querySelector(c + ' .' + ID + '-scroll')) tl.fromTo(c + ' .' + ID + '-scroll', { y: 0 }, { y: -T.scroll, duration: end - pushAt(k), ease: 'none', immediateRender: false }, s);
  if (document.querySelector(c + ' .' + ID + '-cur')) tl.fromTo(c + ' .' + ID + '-cur', { x: 520 - 60 * k, y: 700 + 90 * k }, { x: 380 + 70 * k, y: 980 - 60 * k, duration: end - pushAt(k),
    ease: 'power1.inOut', immediateRender: false }, s);
  if (k > 0) {
    var o = '#' + ID + '-c' + k;
    tl.fromTo(o, { x: 0 }, { x: T.park, duration: T.push, ease: 'power3.inOut', immediateRender: false }, s);
    tl.fromTo(o + ' .' + ID + '-dim', { opacity: 0.34 }, { opacity: T.dark, duration: T.push, ease: 'power2.in', immediateRender: false }, s);
    tl.set(o, { opacity: 0 }, q(at[k] + T.push / 2 + 0.01));
  }
}
// ---- out: the last chapter pushes out left and the room is back (its edge shadow off the frame too)
var lastC = '#' + ID + '-c' + N;
tl.fromTo(lastC, { x: 0 }, { x: -1080, duration: 0.22, ease: 'power3.in', immediateRender: false }, q(tOut));
tl.set(lastC, { opacity: 0 }, q(tOut + 0.22));
