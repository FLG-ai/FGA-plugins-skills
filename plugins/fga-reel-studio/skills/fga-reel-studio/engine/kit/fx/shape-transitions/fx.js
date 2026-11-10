/* shape-transitions (layer: cam). A different shape-mask transition on each picture cut: the camera-transitions
   alternative when the edit wants graphic cuts instead of camera moves.
   Each one runs in the frames BEFORE its cut (FRAMES_PER, at most the join's J-cut lead) and reveals the incoming
   shot from its pre-roll handle, in sync with the incoming line's audio that is already playing:
     iris     a circle opens from the incoming face, a light ring on its edge, the new shot settling from 1.14
     blinds   vertical slats open left to right, the new shot sliding in behind them
     doors    the frame splits down the middle and swings open like two doors onto the new shot
     push     a push into the face on the way out (motion blur), the next shot lands face on face and pulls back
     clock    a clock-hand sweep around the incoming face, a light hand on its edge
   The mask covers the whole frame on the last frame before the cut; on the cut the main picture carries on from the
   next frame, so nothing freezes and nothing jumps. Nothing touches #foot or #cam (CAMERA zooms carry it).
   Use: one entry for the whole video, dict(id="shape-transitions", layer="cam", at=0.0, end="end").
   Supply: nothing by hand. handles.py cuts each transition's pre-roll handle from edit.SRC exactly like the pipeline
   cuts the pieces and writes fx.html (one group per cut, its shape from SHAPES):
     PY fx/<id>/handles.py <project> [<id>]     (rerun it whenever KEEP, SHOTS or the FX list change)
   Sound, one per transition on its cut: whoosh-soft (iris, blinds, clock), whoosh (doors), whoosh-deep (push),
   14 to 18 dB under the voice.
   Change only these constants (handles.py reads SHAPES, ONLY, SKIP and FRAMES_PER from here: rerun it after): */
var SHAPES = ["iris", "blinds", "doors", "push", "clock"];   // in order, cycling over the cuts that get one
var ONLY = [];                      // seconds: only these cuts; [] = every cut no full-frame effect covers
var SKIP = [];                      // seconds: cuts to leave alone (matched within 0.1 s)
var FRAMES_PER = 9;                 // frames before the cut (never more than the join's J-cut lead)
var FACE = [540, 760];              // the face on the 1080x1920 frame: the iris and the clock centre, the push's aim
var FACES = {};                     // per cut, when the face moves: { "34.0": [[outX, outY], [inX, inY]] }

var FPS = 30;
function T(f) { return Math.max(0, f / FPS - 0.002); }
function cl(x) { return Math.max(0, Math.min(1, x)); }
function n1(v) { return v.toFixed(1); }
function poly(pts) { return 'polygon(' + pts.map(function (p) { return n1(p[0]) + 'px ' + n1(p[1]) + 'px'; }).join(', ') + ')'; }
var NONE = 'polygon(0px 0px, 0px 0px, 0px 0px)';
var W = 1080, H = 1920;
function faces(cut) {
  for (var k in FACES) { if (Math.abs(+k - cut) < 0.05) return FACES[k]; }
  return [FACE, FACE];
}

gsap.set('#{{ID}} .{{ID}}-g', { opacity: 0 });
gsap.set('#{{ID}} .{{ID}}-line', { opacity: 0 });
function show(sel, f0, f1) { tl.set(sel, { opacity: 1 }, T(f0)); tl.set(sel, { opacity: 0 }, T(f1 + 1)); }
function blur(sel, f, sd) {
  tl.set(sel, { filter: sd > 0.3 ? 'url(#{{ID}}-mb)' : 'none' }, T(f));
  if (sd > 0.3) tl.set('#{{ID}}-mb-g', { attr: { stdDeviation: sd.toFixed(1) } }, T(f));
}

var SHAPE = {
  // a circle opens from the incoming face; its handle settles from 1.14 as it opens
  iris: function (k, C, n, fc) {
    var EX = fc[1][0], EY = fc[1][1], S = C - n;
    var R = Math.max(Math.hypot(EX, EY), Math.hypot(W - EX, EY), Math.hypot(EX, H - EY), Math.hypot(W - EX, H - EY)) + 4;
    show('#{{ID}}-g' + k, S + 2, C - 1); show('#{{ID}}-ring' + k, S + 2, C - 2);
    gsap.set('#{{ID}}-h' + k, { transformOrigin: EX + 'px ' + EY + 'px' });
    gsap.set('#{{ID}}-ring' + k, { attr: { cx: EX, cy: EY } });
    for (var f = 2; f < n; f++) {
      var p = (f - 1) / (n - 2), r = R * Math.pow(p, 1.7);
      tl.set('#{{ID}}-g' + k, { clipPath: f === n - 1 ? 'none' : 'circle(' + n1(r) + 'px at ' + EX + 'px ' + EY + 'px)' }, T(S + f));
      tl.set('#{{ID}}-h' + k, { scale: 1 + 0.14 * Math.pow(1 - p, 2) }, T(S + f));
      tl.set('#{{ID}}-ring' + k, { attr: { r: n1(r) } }, T(S + f));
    }
  },
  // nine vertical slats open left to right, the new shot sliding in behind them
  blinds: function (k, C, n) {
    var S = C - n, N = 9, SW = W / N;
    show('#{{ID}}-g' + k, S + 1, C - 1);
    for (var f = 1; f < n; f++) {
      var u = f * 8 / (n - 1), pts = [];
      for (var i = 0; i < N; i++) {
        var p = cl((u - 0.5 * i) / 4), w = SW * (1 - (1 - p) * (1 - p)), cx = SW * i + SW / 2;
        if (f === n - 1) w = SW;
        if (w < 0.5) continue;
        var l = cx - w / 2 - (p >= 1 || f === n - 1 ? 1 : 0), r = cx + w / 2 + (p >= 1 || f === n - 1 ? 1 : 0);
        pts.push([l, 0], [l, H], [r, H], [r, 0]);
      }
      tl.set('#{{ID}}-g' + k, { clipPath: f === n - 1 ? 'none' : (pts.length ? poly(pts) : NONE) }, T(S + f));
      tl.set('#{{ID}}-h' + k, { x: 70 * Math.pow(1 - u / 8, 2) }, T(S + f));
    }
  },
  // the outgoing frame splits down the middle and swings open like two doors; the new shot settles behind them
  doors: function (k, C, n) {
    var S = C - n;
    show('#{{ID}}-g' + k, S, C - 1);
    gsap.set('#{{ID}}-dl' + k, { transformOrigin: '0px ' + H / 2 + 'px' });
    gsap.set('#{{ID}}-dr' + k, { transformOrigin: W / 2 + 'px ' + H / 2 + 'px' });
    gsap.set('#{{ID}}-h' + k, { transformOrigin: W / 2 + 'px ' + H / 2 + 'px' });
    gsap.set('#{{ID}}-g' + k + ' .{{ID}}-shade', { opacity: 0 });
    for (var f = 0; f < n; f++) {
      var u = f * 8 / (n - 1), p = u < 1 ? 0 : Math.pow(u / 8, 1.8), a = 92 * p;
      tl.set('#{{ID}}-dl' + k, { rotationY: a }, T(S + f));
      tl.set('#{{ID}}-dr' + k, { rotationY: -a }, T(S + f));
      tl.set('#{{ID}}-g' + k + ' .{{ID}}-shade', { opacity: 0.8 * Math.pow(p, 0.7) }, T(S + f));
      tl.set('#{{ID}}-h' + k, { scale: 1 + 0.08 * Math.pow(1 - u / 8, 2) }, T(S + f));
    }
    tl.set(['#{{ID}}-dl' + k, '#{{ID}}-dr' + k], { opacity: 0 }, T(C - 1));      // edge-on on the last frame: gone
  },
  // a push into the face on the way out, then the next shot lands face on face and pulls back out
  push: function (k, C, n, fc) {
    var S = C - n, OX = fc[0][0], OY = fc[0][1], IX = fc[1][0], IY = fc[1][1], S0 = 2.0;
    var nOut = Math.max(2, Math.round(n * 4 / 9)), nIn = n - nOut;
    show('#{{ID}}-g' + k, S, C - 1);
    gsap.set('#{{ID}}-o' + k + '0', { transformOrigin: OX + 'px ' + OY + 'px' });
    gsap.set('#{{ID}}-h' + k, { transformOrigin: IX + 'px ' + IY + 'px' });
    gsap.set('#{{ID}}-wi' + k, { opacity: 0 });
    tl.set('#{{ID}}-wo' + k, { opacity: 0 }, T(S + nOut)); tl.set('#{{ID}}-wi' + k, { opacity: 1 }, T(S + nOut));
    for (var f = 0; f < nOut; f++) {
      var po = (f + 1) / nOut;
      tl.set('#{{ID}}-o' + k + '0', { scale: 1 + 0.45 * po * po }, T(S + f));
      blur('#{{ID}}-wo' + k, S + f, po < 0.5 ? 0 : 9 * (po - 0.25) / 0.75);
    }
    for (var g = 0; g < nIn; g++) {
      var e = Math.pow(1 - g / (nIn - 1), 3);
      tl.set('#{{ID}}-h' + k, { scale: 1 + (S0 - 1) * e, x: (OX - IX) * e, y: (OY - IY) * e }, T(S + nOut + g));
      blur('#{{ID}}-wi' + k, S + nOut + g, 9 * Math.max(0, 1 - g / 2));
    }
  },
  // a clock hand sweeps once around the incoming face, the new shot behind it
  clock: function (k, C, n, fc) {
    var S = C - n, CX = fc[1][0], CY = fc[1][1], RR = 2600;
    show('#{{ID}}-g' + k, S, C - 1); show('#{{ID}}-hand' + k, S, C - 2);
    for (var f = 0; f < n; f++) {
      var p = Math.pow((f + 1) / n, 1.25), a = 360 * p, pts = [[CX, CY]];
      for (var d = 0; d <= a; d += 6) pts.push([CX + RR * Math.cos((d - 90) * Math.PI / 180), CY + RR * Math.sin((d - 90) * Math.PI / 180)]);
      var ex = CX + RR * Math.cos((a - 90) * Math.PI / 180), ey = CY + RR * Math.sin((a - 90) * Math.PI / 180);
      pts.push([ex, ey]);
      tl.set('#{{ID}}-g' + k, { clipPath: f === n - 1 ? 'none' : poly(pts) }, T(S + f));
      tl.set('#{{ID}}-hand' + k, { attr: { x1: CX, y1: CY, x2: n1(ex), y2: n1(ey) } }, T(S + f));
    }
  }
};

Array.prototype.forEach.call(document.querySelectorAll('#{{ID}} .{{ID}}-g'), function (g) {
  var k = +g.id.split('-g').pop(), cut = +g.getAttribute('data-cut'), n = +g.getAttribute('data-n');
  var fn = SHAPE[g.getAttribute('data-shape')];
  if (fn && cut > A && cut < B) fn(k, Math.round(cut * FPS), n, faces(cut));
});
