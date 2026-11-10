import assert from "node:assert/strict";
import test from "node:test";
import { GAP_MAX_MS, GAP_MIN_MS, heldBack, nextPostTime, randomGap, shortLabels } from "../src/lib.js";

const minute = 60 * 1000;
const hour = 60 * minute;

test("gaps between versions stay between 3 and 7 minutes", () => {
  assert.equal(randomGap(() => 0), GAP_MIN_MS);
  assert.equal(randomGap(() => 1), GAP_MAX_MS);
  for (let i = 0; i < 200; i += 1) {
    const gap = randomGap();
    assert.ok(gap >= GAP_MIN_MS && gap <= GAP_MAX_MS);
  }
});

test("the first version posts now, the next one waits its gap", () => {
  const now = Date.UTC(2026, 9, 29, 17);
  assert.equal(nextPostTime(null, now), null);
  assert.equal(nextPostTime(now, now, 5 * minute), now + 5 * minute);
});

test("a slow upload never squeezes the gap or schedules into the past", () => {
  const first = Date.UTC(2026, 9, 29, 17);
  const later = first + 4 * minute;
  // The gap was 5 minutes, but the upload took 4: still 5 after the first, still a minute out.
  assert.ok(nextPostTime(first, later, 5 * minute) - first >= 5 * minute);
  assert.ok(nextPostTime(first, later, 5 * minute) >= later + minute);
});

test("a version added long after the last one posts right away", () => {
  const last = Date.UTC(2026, 9, 29, 17);
  assert.equal(nextPostTime(last, last + 2 * hour), null);
});

test("flags versions with almost no views half a day in, only after a fresh refresh", () => {
  const now = Date.UTC(2026, 9, 29, 17);
  const posted = new Date(now - 40 * hour).toISOString();
  const fresh = new Date(now - 5 * minute).toISOString();
  const variants = [
    { id: "held", status: "published", publishedAt: posted, lastRefreshedAt: fresh, analytics: { views: 3 } },
    { id: "doing-fine", status: "published", publishedAt: posted, lastRefreshedAt: fresh, analytics: { views: 5200 } },
    { id: "stale", status: "published", publishedAt: posted, lastRefreshedAt: new Date(now - 39 * hour).toISOString(), analytics: { views: 2 } },
    { id: "too-new", status: "published", publishedAt: new Date(now - 1 * hour).toISOString(), lastRefreshedAt: fresh, analytics: { views: 1 } },
    { id: "scheduled", status: "scheduled", publishedAt: posted, lastRefreshedAt: fresh, analytics: { views: 0 } },
  ];
  assert.deepEqual(heldBack(variants, now).map((v) => v.id), ["held"]);
});

test("a version near zero beside one that took off is flagged after two hours, not twelve", () => {
  const now = Date.UTC(2026, 9, 29, 17);
  const posted = new Date(now - 5 * hour).toISOString();
  const fresh = new Date(now - 5 * minute).toISOString();
  const quiet = [
    { id: "a", status: "published", publishedAt: posted, lastRefreshedAt: fresh, analytics: { views: 0 } },
    { id: "b", status: "published", publishedAt: posted, lastRefreshedAt: fresh, analytics: { views: 40 } },
  ];
  assert.deepEqual(heldBack(quiet, now), []);
  const breakout = [quiet[0], { ...quiet[1], analytics: { views: 254 } }];
  assert.deepEqual(heldBack(breakout, now).map((v) => v.id), ["a"]);
});

test("file names lose the words every version shares; typed names stay", () => {
  const v = (id, label, file = `${label}.mp4`) => ({ id, label, originalFilename: file });
  const short = shortLabels([
    v("a", "AIVE Full Process (ChatGPT, Navy) v1"),
    v("b", "AIVE Full Process (ChatGPT, Oxblood) v1"),
    v("c", "AIVE Full Process (ChatGPT) v3"),
  ]).map((x) => x.label);
  assert.deepEqual(short, ["Navy v1", "Oxblood v1", "v3"]);
  assert.deepEqual(shortLabels([v("a", "Original", "x.mp4"), v("b", "Updated Text", "x2.mp4")]).map((x) => x.label), ["Original", "Updated Text"]);
  // Nothing left, or two the same: keep the full names.
  assert.deepEqual(shortLabels([v("a", "Reel v1"), v("b", "Reel v1 copy"), v("c", "Reel")]).map((x) => x.label), ["Reel v1", "Reel v1 copy", "Reel"]);
});
