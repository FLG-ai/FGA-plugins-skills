// LIBRARY COPY, written by gen.py on the kit's stand-in line so this folder renders as it is. For a video, run
// gen.py on the project: it rewrites this file.
// post-wall: written by gen.py (rerun it when the window, the cut, the dates or the numbers change). The calendar
// draws up the wall, a square per day lands in date order, faster and faster, the counter rolls to the total, the last
// square pops in the accent on the word. Frames are counted from A's frame; colours are the pack's tokens.
var R = '#{{ID}}-', S = '#{{ID}} .{{ID}}-', FPS = 30, F0 = Math.round(A * FPS);
var T = { grid: 0.0700, out: 2.7600 };   // s after A: the calendar draws, the wipe out starts
var IN = 'cut', OUT = 'wipe', WIPE = 0.14, CLIP = [194, 717];   // the wipe runs between these two lines (y px)
var CUTF = [];   // picture cuts inside the window
var LIGHT_WALL = false;   // read off the footage: the squares' ramp and the leading edge run away from the wall's tone
var PAD = 3;
// per day, oldest first: [frame after A it lands, level 0-4 by posts that day (-1 = before the dates reach), room light %, warm %]
var CELLS = [[6,2,98,0],[8,0,99,0],[8,1,99,0],[9,2,100,0],[10,1,100,0],[10,1,100,0],[11,2,100,0],[11,1,100,0],[12,1,100,0],[12,1,100,0],[13,0,99,0],[13,0,99,0],[13,1,99,0],[14,0,98,0],[14,0,98,0],[14,1,97,0],[15,0,96,0],[15,1,96,0],[15,1,95,0],[16,1,94,0],[16,0,94,0],[16,1,92,0],[17,1,93,0],[17,1,94,0],[17,2,94,0],[17,1,95,0],[18,1,96,0],[18,1,97,0],[18,1,97,0],[19,1,98,0],[19,0,98,0],[19,0,99,0],[19,1,99,0],[20,1,99,0],[20,1,100,0],[20,1,100,0],[20,3,100,0],[21,0,100,0],[21,1,100,0],[21,0,100,0],[21,1,99,0],[21,0,99,0],[22,1,99,0],[22,1,98,0],[22,2,98,0],[22,0,97,0],[23,2,96,0],[23,3,96,0],[23,1,95,0],[23,1,94,0],[23,1,93,0],[24,1,93,0],[24,0,92,0],[24,1,93,0],[24,1,94,0],[24,1,94,0],[25,3,95,0],[25,1,96,0],[25,1,96,0],[25,1,97,0],[25,1,98,0],[26,1,98,0],[26,1,99,0],[26,2,99,0],[26,2,99,0],[26,1,99,0],[27,1,100,0],[27,1,100,0],[27,1,100,0],[27,1,100,0],[27,1,99,0],[28,1,99,0],[28,1,99,0],[28,1,98,0],[28,3,98,0],[28,1,97,0],[28,2,97,0],[29,1,96,0],[29,1,96,0],[29,1,95,0],[29,0,94,0],[29,1,93,0],[30,1,93,0],[30,1,92,0],[30,1,93,0],[30,1,93,0],[30,1,94,0],[30,2,95,0],[31,1,96,0],[31,1,96,0],[31,0,97,0],[31,1,97,0],[31,1,98,0],[31,3,98,0],[32,0,99,0],[32,0,99,0],[32,0,99,0],[32,1,99,0],[32,1,99,0],[32,1,99,0],[33,1,99,0],[33,0,99,0],[33,1,99,0],[33,1,99,0],[33,1,98,0],[33,0,98,0],[33,1,97,0],[34,3,97,0],[34,1,96,0],[34,0,95,0],[34,2,95,0],[34,1,92,0],[34,1,92,0],[35,1,93,0],[35,1,94,0],[35,1,95,0],[35,1,95,0],[35,0,96,0],[35,2,96,0],[35,0,97,0],[36,1,98,0],[36,0,98,0],[36,0,98,0],[36,2,99,0],[36,2,99,0],[36,0,99,0],[36,2,99,0],[37,1,99,0],[37,0,99,0],[37,1,99,0],[37,1,99,0],[37,0,98,0],[37,0,98,0],[38,1,97,0],[38,2,97,0],[38,1,96,0],[38,1,96,0],[38,0,95,0],[38,0,94,0],[38,1,94,0],[39,1,93,0],[39,0,92,0],[39,0,91,0],[39,1,92,0],[39,1,93,0],[39,0,94,0],[39,0,94,0],[39,0,95,0],[40,2,96,0],[40,1,96,0],[40,0,97,0],[40,1,97,0],[40,1,98,0],[40,2,98,0],[40,1,98,0],[41,0,98,0],[41,0,99,0],[41,1,99,0],[41,1,99,0],[41,1,99,0],[41,1,98,0],[41,2,98,0],[42,1,98,0],[42,2,97,0],[42,1,97,0],[42,1,96,0],[42,0,96,0],[42,0,95,0],[42,1,95,0],[42,1,94,0],[43,1,93,0],[43,0,93,0],[43,0,91,0],[43,0,92,0],[43,1,93,0],[43,1,93,0],[43,1,94,0],[43,2,95,0],[44,0,95,0],[44,1,96,0],[44,0,96,0],[44,2,97,0],[44,2,97,0],[44,0,97,0],[44,3,98,0],[44,1,98,0],[45,0,98,0],[45,1,98,0],[45,1,98,0],[45,3,98,0],[45,2,98,0],[45,1,98,0],[45,1,97,0],[45,1,97,0],[46,1,97,0],[46,1,96,0],[46,1,96,0],[46,0,95,0],[46,1,94,0],[46,1,94,0],[46,1,93,0],[46,1,92,0],[47,2,92,0],[47,1,91,0],[47,0,91,0],[47,1,92,0],[47,1,93,0],[47,0,93,0],[47,0,94,0],[47,1,95,0],[48,1,95,0],[48,2,96,0],[48,1,96,0],[48,0,97,0],[48,1,97,0],[48,1,97,0],[48,0,97,0],[48,1,98,0],[49,1,98,0],[49,1,98,0],[49,3,98,0],[49,2,97,0],[49,1,97,0],[49,1,97,0],[49,1,96,0],[49,1,96,0],[49,1,96,0],[50,1,95,0],[50,0,94,0],[50,1,94,0],[50,1,93,0],[50,1,93,0],[50,0,92,0],[50,1,90,0],[50,1,91,0],[50,1,92,0],[51,2,92,0],[51,1,93,0],[51,1,94,0],[51,2,94,0],[51,1,95,0],[51,1,95,0],[51,1,96,0],[51,1,96,0],[52,1,96,0],[52,1,97,0],[52,0,97,0],[52,0,97,0],[52,2,97,0],[52,1,97,0],[52,0,97,0],[52,1,97,0],[52,1,97,0],[53,2,96,0],[53,0,96,0],[53,0,96,0],[53,0,95,0],[53,2,95,0],[53,1,94,0],[53,1,93,0],[53,1,93,0],[53,1,92,0],[54,2,92,0],[54,0,91,0],[54,0,90,0],[54,2,91,0],[54,1,91,0],[54,1,92,0],[54,1,93,0],[54,1,93,0],[54,1,94,0],[55,1,94,0],[55,1,95,0],[55,1,95,0],[55,1,95,0],[55,1,96,0],[55,1,96,0],[55,0,96,0],[55,1,96,0],[55,1,96,0],[55,1,96,0],[56,1,96,0],[56,1,96,0],[56,1,96,0],[56,1,96,0],[56,0,95,0],[56,2,95,0],[56,1,94,0],[56,2,94,0],[56,1,93,0],[57,1,93,0],[57,1,92,0],[57,0,92,0],[57,0,91,0],[57,1,90,0],[57,1,90,0],[57,0,90,0],[57,1,91,0],[57,1,91,0],[57,0,92,0],[58,1,93,0],[58,1,93,0],[58,0,94,0],[58,1,94,0],[58,3,94,0],[58,3,95,0],[58,1,95,0],[58,1,95,0],[58,0,96,0],[59,1,96,0],[59,1,96,0],[59,2,96,0],[59,2,96,0],[59,1,95,0],[59,2,95,0],[59,1,95,0],[59,1,95,0],[59,1,94,0],[59,0,94,0],[60,0,93,0],[60,0,93,0],[60,0,92,0],[60,0,92,0],[60,1,91,0],[60,2,91,0],[60,2,89,0],[60,1,90,0],[60,0,90,0],[60,1,91,0],[61,3,91,0],[61,0,92,0],[61,1,92,0],[61,1,93,0],[61,0,93,0],[61,1,94,0],[61,0,94,0],[61,1,94,0],[61,0,95,0],[61,1,95,0],[62,0,95,0],[62,0,95,0],[62,2,95,0],[62,1,95,0],[62,0,95,0],[62,2,95,0],[62,2,94,0],[62,1,94,0],[62,1,94,0],[62,1,93,0],[63,1,93,0],[63,1,92,0],[63,1,92,0],[63,0,91,0],[63,1,91,0],[63,1,90,0],[63,2,90,0],[63,0,89,0],[63,0,89,0],[63,3,90,0],[64,1,90,0],[64,1,91,0],[64,0,91,0],[64,1,92,0],[64,1,92,0],[64,0,93,0]];
var COUNT = [[6,2,1],[8,3,3],[9,5,4],[10,7,6],[11,10,8],[12,12,10],[13,13,13],[14,14,16],[15,16,19],[16,18,22],[17,23,26],[18,26,29],[19,28,33],[20,34,37],[21,36,42],[22,40,46],[23,49,51],[24,53,56],[25,61,61],[26,68,66],[27,73,71],[28,83,77],[29,87,82],[30,94,88],[31,102,94],[32,105,100],[33,110,107],[34,119,113],[35,125,120],[36,132,127],[37,135,133],[38,141,140],[39,144,148],[40,152,155],[41,158,162],[42,165,170],[43,171,178],[44,181,186],[45,192,194],[46,199,202],[47,205,210],[48,212,218],[49,225,227],[50,232,236],[51,242,244],[52,249,253],[53,257,262],[54,266,271],[55,275,281],[56,285,290],[57,291,300],[58,304,309],[59,316,319],[60,323,329],[61,331,339],[62,341,349],[63,352,359],[64,356,365]];   // [frame after A, the counter, the day]
var REACH = [[6,654],[16,622],[24,590],[30,558],[34,526],[39,494],[43,462],[47,430],[50,398],[54,366],[57,334],[60,302],[63,270]];   // [frame after A, y]: the shadow reaches no higher than the squares
var LAST = CELLS.length - 1;
function at(f) { return q((F0 + f) / FPS); }
function tok(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function rgb(c) {
  if (c[0] === '#') {
    if (c.length === 4) c = '#' + c[1] + c[1] + c[2] + c[2] + c[3] + c[3];
    return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
  }
  var m = c.match(/[\d.]+/g);
  return m && m.length >= 3 ? [+m[0], +m[1], +m[2]] : [128, 128, 128];
}
function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
var DK = rgb(tok('--c-dark')), LT = rgb(tok('--c-light')), AC = tok(LIGHT_WALL ? '--c-accent-light' : '--c-accent');
var LO = LIGHT_WALL ? LT : DK, HI = LIGHT_WALL ? DK : LT, EDGE = LIGHT_WALL ? rgb(tok('--c-ink')) : LT;
var LEVEL = [LO, mix(LO, HI, 0.38), mix(LO, HI, 0.68), HI, rgb(AC)];   // none, 1, 2, 3-4, 5+ posts that day
function colour(c) {
  var v = LEVEL[c[1]], f = c[2] / 100, w = c[3] / 100;
  var k = [f * (1 + 0.10 * w), f * (1 + 0.01 * w), f * (1 - 0.12 * w)];
  return 'rgb(' + v.map(function (x, i) { return Math.max(0, Math.min(255, Math.round(x * k[i]))); }).join(',') + ')';
}
function comma(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
function pad(n) { var s = String(n); while (s.length < PAD) s = '0' + s; return '\u200b' + s; }

// in: with the picture cut, or one wipe up the wall that carries the squares, the patch, the shadow and the labels
tl.set([S + 'day', S + 'post', S + 'key'], { opacity: 1 }, q(A + T.grid));
tl.fromTo(S + 'tpl', { opacity: 1, clipPath: 'inset(100% 0px 0px 0px)' }, { clipPath: 'inset(0% 0px 0px 0px)', duration: 0.2, ease: 'power2.out', immediateRender: false }, q(A + T.grid));
if (IN === 'wipe') {
  gsap.set([S + 'sheet', S + 'labels'], { clipPath: 'inset(' + CLIP[1] + 'px 0px 0px 0px)' });
  tl.fromTo([S + 'sheet', S + 'labels'], { clipPath: 'inset(' + CLIP[1] + 'px 0px 0px 0px)' }, { clipPath: 'inset(' + CLIP[0] + 'px 0px 0px 0px)', duration: WIPE, ease: 'power2.out', immediateRender: false }, q(A));
}
if (OUT === 'wipe') {          // the same wipe carries on upward and hands the wall back
  tl.fromTo([S + 'sheet', S + 'labels'], { clipPath: 'inset(' + CLIP[0] + 'px 0px ' + (1920 - CLIP[1]) + 'px 0px)' }, { clipPath: 'inset(' + CLIP[0] + 'px 0px ' + (1920 - CLIP[0]) + 'px 0px)', duration: WIPE, ease: 'power1.in', immediateRender: false }, q(A + T.out));
}

// a picture cut inside the window: on its frame the footage can still show the shot before and no cutout plays, so
// the wall sits that one frame out (never over the head)
CUTF.forEach(function (f) { tl.set(S + 'cutw', { opacity: 0 }, at(f)); tl.set(S + 'cutw', { opacity: 1 }, at(f + 1)); });

// the squares land behind a one-frame light leading edge
CELLS.forEach(function (c, i) {
  if (i === LAST) return;
  var el = R + 'c' + i;
  if (c[1] < 0) { tl.set(el, { opacity: 1 }, at(c[0])); return; }
  tl.set(el, { opacity: 1, backgroundColor: 'rgb(' + EDGE.join(',') + ')' }, at(c[0]));
  tl.set(el, { backgroundColor: colour(c) }, at(c[0] + 1));
});
// the speaker's shadow falls on the squares that have landed (its mask is the filled squares; this clip keeps it
// off the rows still to come)
if (document.querySelector(S + 'shw')) {
  gsap.set(S + 'shw', { clipPath: 'inset(1920px 0px 0px 0px)' });
  REACH.forEach(function (r) { tl.set(S + 'shw', { clipPath: 'inset(' + r[1] + 'px 0px 0px 0px)' }, at(r[0])); });
}
COUNT.forEach(function (c) {
  tl.set(R + 'n', { textContent: comma(c[1]) }, at(c[0]));
  tl.set(R + 'd', { textContent: pad(c[2]) }, at(c[0]));
});

// the last square pops in the accent on the word, the counter lands with it
var L = R + 'c' + LAST, SNAP = CELLS[LAST][0];
gsap.set(L, { backgroundColor: AC, transformOrigin: '50% 50%' });
tl.set(L, { opacity: 1 }, at(SNAP));
tl.fromTo(L, { scale: 3.6 }, { scale: 1, duration: 0.2, ease: 'back.out(1.7)', immediateRender: false }, at(SNAP));
tl.set([R + 'n', R + 'd'], { color: AC }, at(SNAP));
gsap.set(R + 'n', { display: 'inline-block', transformOrigin: '100% 100%' });
tl.fromTo(R + 'n', { scale: 1.14 }, { scale: 1, duration: 0.2, ease: 'back.out(1.8)', immediateRender: false }, at(SNAP));
