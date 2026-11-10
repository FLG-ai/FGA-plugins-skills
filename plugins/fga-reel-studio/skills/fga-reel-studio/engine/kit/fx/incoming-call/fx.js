// LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run
// gen.py on the project: it rewrites this file.
// incoming-call: written by gen.py for this window (rerun it when the window or the cut changes). The banner drops
// in and lands on the word, buzzes in two-burst pairs while the speaker keeps talking, a soft tap declines it on the
// word, it squashes and flies off, the "Call declined" pill is gone by the last word. Times are seconds after A.
var R = '#{{ID}}-', FPS = 30, F0 = Math.round(A * FPS);
var T = { land: 0.44, tap: 2.93, pill: 2.964, gone: 3.41 }, OFF = 456;
// per frame of the buzz: [frame after A, x px, rotation deg, the answer handset's rock deg]
var BUZZ = [[13,-3.39,-0.119,-5.6],[14,4.83,0.169,8.3],[15,-5.34,-0.187,-9],[16,5.0,0.175,8.1],[17,-2.75,-0.096,-5.0],[18,0,0,0],[20,3.22,0.113,5.6],[21,-5.01,-0.175,-8.3],[22,5.97,0.209,9],[23,-5.21,-0.182,-8.1],[24,2.76,0.097,5.0],[25,0,0,0],[32,-3.72,-0.13,-5.6],[33,5.32,0.186,8.3],[34,-5.33,-0.187,-9],[35,5.32,0.186,8.1],[36,-2.93,-0.102,-5.0],[37,0,0,0],[39,3.46,0.121,5.6],[40,-4.77,-0.167,-8.3],[41,5.71,0.2,9],[42,-4.92,-0.172,-8.1],[43,3.08,0.108,5.0],[44,0,0,0],[50,-3.29,-0.115,-5.6],[51,4.57,0.16,8.3],[52,-5.2,-0.182,-9],[53,4.85,0.17,8.1],[54,-2.64,-0.092,-5.0],[55,0,0,0],[57,3.1,0.108,5.6],[58,-4.88,-0.171,-8.3],[59,5.98,0.209,9],[60,-5.1,-0.179,-8.1],[61,2.83,0.099,5.0],[62,0,0,0],[69,-3.29,-0.115,-5.6],[70,4.64,0.162,8.3],[71,-5.49,-0.192,-9],[72,5.38,0.188,8.1],[73,-3.25,-0.114,-5.0],[74,0,0,0],[76,3.33,0.116,5.6],[77,-5.26,-0.184,-8.3],[78,5.52,0.193,9],[79,-5.33,-0.187,-8.1],[80,2.94,0.103,5.0],[81,0,0,0]];
function at(f) { return q((F0 + f) / FPS); }

gsap.set(R + 'cardw', { y: -OFF, transformOrigin: '696.0px 50%' });
gsap.set(R + 'accg', { transformOrigin: '50% 50%' });
gsap.set(R + 'decw', { transformOrigin: '50% 50%' });
tl.set(R + 'cardw', { opacity: 1 }, q(A + T.land - 0.07));
tl.fromTo(R + 'cardw', { y: -OFF }, { y: 0, duration: 0.17, ease: 'back.out(1.25)', immediateRender: false }, q(A + T.land - 0.07));   // reaches its spot on the word; the overshoot settles under the first buzz

BUZZ.forEach(function (b) {
  tl.set(R + 'buzz', { x: b[1], rotation: b[2] }, at(b[0]));
  tl.set(R + 'accg', { rotation: b[3] }, at(b[0]));
});

// the tap, the same soft circle as the chat effects; decline takes it
tl.fromTo(R + 'tap', { opacity: 0, scale: 1.7 }, { opacity: 1, scale: 1, duration: 0.1, ease: 'power2.out', immediateRender: false }, q(A + T.tap - 0.1));
tl.to(R + 'tap', { scale: 0.84, duration: 0.05, ease: 'power2.out' }, q(A + T.tap));
tl.to(R + 'tap', { scale: 1.2, opacity: 0, duration: 0.1, ease: 'power2.out' }, q(A + T.tap + 0.07));
tl.to(R + 'decw', { scale: 0.86, duration: 0.05, ease: 'power2.out' }, q(A + T.tap));
tl.set(R + 'dec-dim', { opacity: 0.22 }, q(A + T.tap));
// the banner takes the press, squashes, and goes
tl.to(R + 'cardw', { scaleY: 0.84, scaleX: 1.03, y: 6, duration: 0.067, ease: 'power2.out' }, q(A + T.tap + 0.033));
tl.to(R + 'cardw', { y: -OFF, scaleY: 1.05, scaleX: 0.97, duration: 0.17, ease: 'power2.in' }, q(A + T.tap + 0.1));
// "Call declined": pops as the banner takes the press, gone by the word
tl.set(R + 'pillw', { opacity: 1 }, q(A + T.pill));
tl.fromTo(R + 'pillw', { scale: 0.7 }, { scale: 1, duration: 0.16, ease: 'back.out(1.8)', immediateRender: false }, q(A + T.pill));
tl.to(R + 'pillw', { scale: 0.86, opacity: 0, duration: 0.067, ease: 'power1.in' }, q(A + T.gone - 0.067));
