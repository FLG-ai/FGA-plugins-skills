// LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run
// gen.py on the project: it rewrites this file.
// voice-note (dark): written by gen.py for this window and this line (rerun it when the window, the cut or the mix
// changes). The bubble pops, the line's own waveform plays through in real time behind the playhead, each bar plucks
// as the playhead reaches it, the transcript pill grows word by word, a tap sends it, it flies off, Delivered.
// Times are seconds after A, read off words.json when gen.py ran.
var R = '#{{ID}}-', N = 40, WAVE = 475, TRR = 26.0;
var T = { pop: 0.0, t0: 0.1, d: 2.3850, tr: 0.1, send: 2.21, lift: 0.05, fly: 0.11, flyDur: 0.160, del: 2.33, gone: 2.47 };
var ON = [0.1, 0.385, 0.76, 1.09, 1.51, 1.84, 2.17];   // each transcript word, on its spoken word
var INS = [358, 343.3, 275.7, 235.7, 148.4, 119.4, 79.5, 0.2];   // the pill's right inset before the first word, then once each word is in
// scale 1: the bubble and the transcript clear the head at full size

// the bubble pops from its bottom-right corner (the headshot's corner)
gsap.set(R + 'pop', { transformOrigin: '100% 100%' });
gsap.set(R + 'row', { transformOrigin: '100% 50%' });
tl.set(R + 'row', { opacity: 1 }, q(A + T.pop));
tl.fromTo(R + 'pop', { scale: 0.6 }, { scale: 1, duration: 0.2, ease: 'back.out(1.6)', immediateRender: false }, q(A + T.pop));

// the waveform plays through in real time behind the playhead
gsap.set(R + 'played', { clipPath: 'inset(0px 100% 0px 0px)' });
tl.fromTo(R + 'played', { clipPath: 'inset(0px 100% 0px 0px)' }, { clipPath: 'inset(0px 0% 0px 0px)', duration: T.d, ease: 'none', immediateRender: false }, q(A + T.t0));
tl.fromTo(R + 'head', { x: 0 }, { x: WAVE, duration: T.d, ease: 'none', immediateRender: false }, q(A + T.t0));
for (var s = 1; s < T.d; s++) tl.set(R + 'time', { textContent: '0:' + (s < 10 ? '0' : '') + s }, q(A + T.t0 + s));
for (var i = 0; i < N; i++) {                 // each bar plucks as the playhead reaches it
  var ti = A + T.t0 + i / N * T.d, bar = R + 'p' + i;
  gsap.set(bar, { transformOrigin: '50% 50%' });
  tl.fromTo(bar, { scaleY: 1 }, { scaleY: 1.2, duration: 0.05, ease: 'power2.out', immediateRender: false }, q(ti));
  tl.to(bar, { scaleY: 1, duration: 0.13, ease: 'power2.inOut' }, q(ti + 0.05));
}

// the transcript pill grows with the words
gsap.set(R + 'tr', { clipPath: 'inset(0px ' + INS[0] + 'px 0px 0px round ' + TRR + 'px)' });
tl.set(R + 'trw', { opacity: 1 }, q(A + T.tr));
ON.forEach(function (t, k) {
  tl.set(R + 'w' + k, { opacity: 1 }, q(A + t));
  tl.fromTo(R + 'tr', { clipPath: 'inset(0px ' + INS[k] + 'px 0px 0px round ' + TRR + 'px)' },
    { clipPath: 'inset(0px ' + INS[k + 1] + 'px 0px 0px round ' + TRR + 'px)', duration: 0.08, ease: 'power3.out', immediateRender: false }, q(A + Math.max(t, T.tr)));
});

// the send: a soft tap, the button takes it, the bubble lifts and flies off up-right
tl.fromTo(R + 'tap', { opacity: 0, scale: 1.7 }, { opacity: 1, scale: 1, duration: 0.1, ease: 'power2.out', immediateRender: false }, q(A + T.send - 0.1));
tl.to(R + 'tap', { scale: 0.84, duration: 0.05, ease: 'power2.out' }, q(A + T.send));
tl.to(R + 'tap', { scale: 1.2, opacity: 0, duration: 0.1, ease: 'power2.out' }, q(A + T.send + 0.07));
tl.fromTo(R + 'send', { scale: 0.8 }, { scale: 1, duration: 0.16, ease: 'back.out(2)', immediateRender: false }, q(A + T.send));
tl.to(R + 'row', { y: -16, scale: 1.02, duration: T.fly - T.lift, ease: 'power2.out' }, q(A + T.send + T.lift));
tl.to(R + 'row', { x: 980, y: -420, scale: 0.52, duration: T.flyDur, ease: 'power2.in' }, q(A + T.send + T.fly));

// Delivered, then the label and the transcript leave just before B
tl.set(R + 'del', { opacity: 1 }, q(A + T.del));
tl.fromTo(R + 'del', { scale: 0.7 }, { scale: 1, duration: 0.16, ease: 'back.out(1.8)', immediateRender: false }, q(A + T.del));
tl.to([R + 'del', R + 'trw'], { opacity: 0, duration: 0.08, ease: 'power1.out' }, q(A + T.gone - 0.08));
