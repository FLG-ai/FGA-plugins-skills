import assert from "node:assert/strict";
import test from "node:test";
import { getPublishLabel, getReadyItems, normalizeDisplayName, reorderItems } from "../src/publishing.js";

test("only ready videos are included in the next publish batch", () => {
  const items = [
    { id: "published", status: "published" },
    { id: "ready-1", status: "ready" },
    { id: "ready-2", status: "ready" },
    { id: "ready-3", status: "ready" },
    { id: "failed", status: "failed" },
  ];

  assert.deepEqual(getReadyItems(items).map((item) => item.id), ["ready-1", "ready-2", "ready-3"]);
});

test("publish button count excludes videos already submitted", () => {
  assert.equal(getPublishLabel({
    publishing: false,
    current: 0,
    total: 0,
    readyCount: 3,
  }), "Publish 3 trial reels");
});

test("publishing progress uses the current queue size", () => {
  assert.equal(getPublishLabel({
    publishing: true,
    current: 2,
    total: 3,
    readyCount: 1,
  }), "Publishing 2 of 3");
});

test("dragging a video reorders the batch", () => {
  const items = [{ id: "one" }, { id: "two" }, { id: "three" }];
  assert.deepEqual(reorderItems(items, "three", "one").map((item) => item.id), ["three", "one", "two"]);
});

test("visual video names are trimmed and keep a fallback when blank", () => {
  assert.equal(normalizeDisplayName("  pink text hook  ", "original.mp4"), "pink text hook");
  assert.equal(normalizeDisplayName("   ", "original.mp4"), "original.mp4");
});
