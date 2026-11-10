export const MAX_FILES = 10;
export const MAX_CAPTION = 2200;
export const MAX_FILE_SIZE = 300 * 1024 * 1024;
export const POLL_INTERVAL = 3000;
export const POLL_LIMIT = 30;
export const STALE_AFTER_MS = 10 * 60 * 1000;

export const METRICS = [
  { key: "views", label: "Views" },
  { key: "reach", label: "Reach" },
  { key: "igReelsAvgWatchTime", label: "Avg watch time" },
  { key: "igReelsVideoViewTotalTime", label: "Total watch time" },
  { key: "reelsSkipRate", label: "Skip rate", rate: true, lowerIsBetter: true },
  { key: "likes", label: "Likes" },
  { key: "comments", label: "Comments" },
  { key: "shares", label: "Shares" },
  { key: "saves", label: "Saves" },
  { key: "engagementRate", label: "Engagement rate", rate: true },
];

const metricInfo = (key) => METRICS.find((metric) => metric.key === key) || {};
export const isRate = (key) => Boolean(metricInfo(key).rate);
export const lowerIsBetter = (key) => Boolean(metricInfo(key).lowerIsBetter);

/** A version's number for one metric, or null when there's nothing to compare. A 0% skip rate means "not reported". */
export function metricValue(variant, key) {
  if (!variant.analytics) return null;
  const value = Number(variant.analytics[key] || 0);
  return lowerIsBetter(key) && value === 0 ? null : value;
}

export const PRIMARY_METRICS = METRICS.filter((metric) => ["views", "reach", "igReelsAvgWatchTime", "shares", "saves"].includes(metric.key));

export function metricLabel(key) {
  return METRICS.find((metric) => metric.key === key)?.label || "Views";
}

export function formatMetric(key, value) {
  if (value === null || value === undefined) return "–";
  const number = Number(value || 0);
  if (key === "igReelsAvgWatchTime") return `${(number / 1000).toFixed(1)}s`;
  if (key === "igReelsVideoViewTotalTime") return formatWatchTime(number);
  if (isRate(key)) return `${number.toFixed(1)}%`;
  if (number >= 100_000) return `${Math.round(number / 1000)}k`;
  if (number >= 10_000) return `${(number / 1000).toFixed(1)}k`;
  return number.toLocaleString();
}

function formatWatchTime(ms) {
  const minutes = Math.round(ms / 60_000);
  if (minutes < 1) return `${Math.round(ms / 1000)}s`;
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return hours >= 100 ? `${hours.toLocaleString()}h` : `${hours}h ${minutes % 60}m`;
}

export function letterFor(index) {
  return String.fromCharCode(65 + index);
}

export function formatDuration(value) {
  if (!Number.isFinite(value) || value <= 0) return "";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

export function timeAgo(value, now = Date.now()) {
  if (!value) return "";
  const seconds = Math.max(0, Math.round((now - new Date(value).getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function stripExtension(name) {
  return String(name || "").replace(/\.(mp4|mov|m4v)$/i, "");
}

export function errorText(error, fallback = "Something went wrong.") {
  return error instanceof Error && error.message ? error.message : fallback;
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(data.error || `Request failed with HTTP ${response.status}.`), { status: response.status });
  return data;
}

// Versions go out a random 3 to 7 minutes apart. Posted seconds apart, Instagram reads them as duplicates and shows them to almost no one.
export const GAP_MIN_MS = 3 * 60 * 1000;
export const GAP_MAX_MS = 7 * 60 * 1000;
const MIN_LEAD_MS = 60 * 1000;

export function randomGap(random = Math.random) {
  return Math.round(GAP_MIN_MS + random() * (GAP_MAX_MS - GAP_MIN_MS));
}

/** When the next version goes out: a gap after the previous one, and never sooner than a minute from now. Null means post now. */
export function nextPostTime(previous, now = Date.now(), gap = randomGap()) {
  if (!previous || previous + gap <= now) return null;
  return Math.max(previous + gap, now + MIN_LEAD_MS);
}

export function formatClock(value) {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

// A version this far in with this few views has almost certainly been held back by Instagram, not just slow.
export const HELD_AFTER_HOURS = 12;
export const HELD_UNDER_VIEWS = 20;
// Once a sibling has taken off, a version still near zero is held back too, and it shows much sooner.
export const BREAKOUT_VIEWS = 100;
export const BREAKOUT_AFTER_HOURS = 2;

/** Published versions that look held back: old enough, refreshed since, and still under the view floor. */
export function heldBack(variants, now = Date.now()) {
  const hour = 60 * 60 * 1000;
  const views = (variant) => Number(variant.analytics?.views || 0);
  const top = Math.max(0, ...variants.filter((variant) => isLive(variant.status)).map(views));
  const after = (top >= BREAKOUT_VIEWS ? BREAKOUT_AFTER_HOURS : HELD_AFTER_HOURS) * hour;
  return variants.filter((variant) => {
    if (!isLive(variant.status) || !variant.publishedAt || !variant.lastRefreshedAt) return false;
    const published = new Date(variant.publishedAt).getTime();
    if (now - published < after) return false;
    if (new Date(variant.lastRefreshedAt).getTime() - published < after) return false;
    return views(variant) < HELD_UNDER_VIEWS;
  });
}

/**
 * Versions named after their files ("AIVE Full Process (Claude, Navy) v1") with the words they all share dropped,
 * so they read "Navy v1". Names someone typed are left alone, and so is everything if the result would be empty or clash.
 */
export function shortLabels(variants) {
  const words = (text) => text.split(/[\s_]+/).map((word) => word.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "")).filter(Boolean);
  const named = variants.filter((v) => v.originalFilename && v.label === stripExtension(v.originalFilename).replace(/\s+/g, " ").trim());
  if (named.length < 2) return variants;
  const split = named.map((v) => words(v.label));
  const shared = new Set(split[0].map((w) => w.toLowerCase()).filter((w) => split.every((list) => list.some((x) => x.toLowerCase() === w))));
  if (!shared.size) return variants;
  const short = new Map(named.map((v, i) => [v.id, split[i].filter((w) => !shared.has(w.toLowerCase())).join(" ")]));
  const all = [...short.values()];
  if (all.some((label) => !label) || new Set(all.map((l) => l.toLowerCase())).size !== all.length) return variants;
  return variants.map((v) => (short.has(v.id) ? { ...v, label: short.get(v.id) } : v));
}

export function isLive(status) {
  return ["published", "success", "completed"].includes(status);
}

export function isFailed(status) {
  return ["failed", "error", "cancelled"].includes(status);
}

export function platformState(post) {
  const target = post?.platforms?.find((platform) => platform.platform === "instagram") || post?.platforms?.[0];
  return {
    status: target?.status || post?.status || "processing",
    url: target?.platformPostUrl || post?.platformPostUrl || "",
    platformPostId: target?.platformPostId || post?.platformPostId || "",
    publishedAt: target?.publishedAt || post?.publishedAt || "",
    error: target?.error || target?.errorMessage || post?.error || "",
  };
}

// Reads metadata, validates against Instagram's Trial Reel limits and grabs a portrait poster frame.
export function inspectVideo(file) {
  return new Promise((resolve) => {
    const objectUrl = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;
    video.src = objectUrl;
    let done = false;

    const finish = (details) => {
      if (done) return;
      done = true;
      resolve({ objectUrl, ...details });
    };

    video.onerror = () => finish({ thumbnail: "", duration: 0, width: 0, height: 0, errors: ["This file can't be read as a video."] });

    video.onloadedmetadata = () => {
      const errors = [];
      const extension = file.name.split(".").pop()?.toLowerCase();
      const ratio = video.videoWidth / video.videoHeight;
      if (!["mp4", "mov", "m4v"].includes(extension || "")) errors.push("Use an MP4 or MOV file.");
      if (file.size > MAX_FILE_SIZE) errors.push("Over Instagram's 300 MB limit.");
      if (video.duration < 3 || video.duration > 90) errors.push("Trial Reels run 3 to 90 seconds.");
      if (!Number.isFinite(ratio) || ratio < 0.5 || ratio > 0.63) errors.push("Needs to be vertical 9:16.");

      const capture = () => {
        let thumbnail = "";
        try {
          const canvas = document.createElement("canvas");
          canvas.width = 270;
          canvas.height = 480;
          const context = canvas.getContext("2d");
          const target = canvas.width / canvas.height;
          let sw = video.videoWidth;
          let sh = video.videoHeight;
          if (sw / sh > target) sw = sh * target;
          else sh = sw / target;
          context.drawImage(video, (video.videoWidth - sw) / 2, (video.videoHeight - sh) / 2, sw, sh, 0, 0, canvas.width, canvas.height);
          thumbnail = canvas.toDataURL("image/jpeg", 0.8);
        } catch {
          thumbnail = "";
        }
        finish({ thumbnail, duration: video.duration, width: video.videoWidth, height: video.videoHeight, errors });
      };

      video.onseeked = capture;
      video.currentTime = Math.min(1, video.duration / 3);
      setTimeout(capture, 1500);
    };
  });
}

export function uploadVideo(uploadUrl, file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type || "video/mp4");
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`Upload failed with HTTP ${xhr.status}.`)));
    xhr.onerror = () => reject(new Error("Upload failed. Check your connection and retry."));
    xhr.send(file);
  });
}
