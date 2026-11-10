import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { demoDraftItems, demoExperiments } from "./demo.js";
import {
  MAX_CAPTION,
  MAX_FILES,
  POLL_INTERVAL,
  POLL_LIMIT,
  STALE_AFTER_MS,
  api,
  errorText,
  formatClock,
  inspectVideo,
  isFailed,
  isLive,
  nextPostTime,
  platformState,
  shortLabels,
  stripExtension,
  uploadVideo,
} from "./lib.js";
import { getReadyItems, reorderItems } from "./publishing.js";

const THEME_KEY = "trialr-theme";
// A new, unpublished test lives under a "new:" key; a draft for an existing test lives under that test's id.
const newKey = () => `new:${crypto.randomUUID().slice(0, 8)}`;
export const isNewKey = (id) => typeof id === "string" && id.startsWith("new");

function emptyDraft(testId = null, caption = "") {
  return { testId, name: "", hypothesis: "", metric: "views", caption, items: [] };
}

function defaultTestName() {
  return `${new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date())} test`;
}

function useTheme() {
  const [preference, setPreference] = useState(() => {
    try {
      const saved = localStorage.getItem(THEME_KEY);
      return ["light", "system", "dark"].includes(saved) ? saved : "system";
    } catch {
      return "system";
    }
  });
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.("(prefers-color-scheme: dark)").matches || false);

  useEffect(() => {
    const query = window.matchMedia?.("(prefers-color-scheme: dark)");
    if (!query) return undefined;
    const update = (event) => setSystemDark(event.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    const resolved = preference === "system" ? (systemDark ? "dark" : "light") : preference;
    document.documentElement.dataset.theme = resolved;
    document.documentElement.style.colorScheme = resolved;
    try {
      localStorage.setItem(THEME_KEY, preference);
    } catch {
      // Theme still applies for this session.
    }
  }, [preference, systemDark]);

  return [preference, setPreference];
}

// Demo edits (renames, winners) live in this browser only, so the sample data stays untouched.
const DEMO_LABELS_KEY = "trialr-demo-labels";
const DEMO_TESTS_KEY = "trialr-demo-tests";
const DEMO_DELETED_KEY = "trialr-demo-deleted";

function readStored(key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || {};
  } catch {
    return {};
  }
}

function saveStored(key, id, value) {
  try {
    localStorage.setItem(key, JSON.stringify({ ...readStored(key), [id]: value }));
  } catch {
    // Storage is off: the edit still holds until reload.
  }
}

function saveTestPatch(testId, patch) {
  saveStored(DEMO_TESTS_KEY, testId, { ...readStored(DEMO_TESTS_KEY)[testId], ...patch });
}

function withDemoEdits(list) {
  const labels = readStored(DEMO_LABELS_KEY);
  const tests = readStored(DEMO_TESTS_KEY);
  const deleted = readStored(DEMO_DELETED_KEY);
  return list.filter((entry) => !deleted[entry.id]).map((entry) => {
    const edited = { ...entry, ...tests[entry.id] };
    if (deleted[edited.winnerId]) Object.assign(edited, { winnerId: null, decidedAt: null });
    return {
      ...edited,
      variants: entry.variants.filter((v) => !deleted[v.id]).map((v) => (labels[v.id] ? { ...v, label: labels[v.id] } : v)),
    };
  });
}

export function useTrialr() {
  const isDemo = useMemo(() => new URLSearchParams(window.location.search).get("demo") === "1", []);
  const [theme, setTheme] = useTheme();

  const [configured, setConfigured] = useState(isDemo ? true : null);
  // Zernio turned down the saved key (deleted or changed in Zernio): ask for a new one.
  const [keyRejected, setKeyRejected] = useState(false);
  const [accounts, setAccounts] = useState(isDemo ? [{ _id: "demo", username: "your.account", displayName: "Your account" }] : []);
  const [accountId, setAccountId] = useState(isDemo ? "demo" : "");
  const [accountsLoading, setAccountsLoading] = useState(!isDemo);

  const [experiments, setExperiments] = useState(() => (isDemo ? withDemoEdits(demoExperiments) : []));
  const [experimentsLoading, setExperimentsLoading] = useState(!isDemo);
  const firstKey = useMemo(newKey, []);
  const [selectedId, setSelectedId] = useState(isDemo ? demoExperiments[0].id : firstKey);
  const [drafts, setDrafts] = useState(() => ({
    [firstKey]: isDemo ? { ...emptyDraft(), name: "Hook test, round 2", caption: "The one thing I'd tell every solo founder starting with AI.", items: demoDraftItems } : emptyDraft(),
  }));
  const [liveStatus, setLiveStatus] = useState({});
  const [publishing, setPublishing] = useState(false);
  const [refreshingId, setRefreshingId] = useState("");
  const [notice, setNotice] = useState(null);
  const autoRefreshed = useRef(new Set());

  const account = accounts.find((entry) => entry._id === accountId) || null;
  const isNewSelected = isNewKey(selectedId);
  const experiment = isNewSelected ? null : experiments.find((entry) => entry.id === selectedId) || null;
  const blankFor = (key) => emptyDraft(isNewKey(key) ? null : key, experiments.find((entry) => entry.id === key)?.caption || "");
  const draft = drafts[selectedId] || blankFor(selectedId);
  const draftItems = draft.items;
  // Drafts worth listing: anything with videos, or a new test you've started filling in. A blank one isn't a draft.
  const draftList = Object.entries(drafts)
    .filter(([key, entry]) => entry.items.length > 0 || (isNewKey(key) && (entry.name.trim() || entry.hypothesis.trim() || entry.caption.trim())))
    .map(([key, entry]) => ({ key, ...entry }));

  function updateDraft(key, change) {
    setDrafts((current) => ({ ...current, [key]: change(current[key] || blankFor(key)) }));
  }

  function updateItems(change) {
    setDrafts((current) => Object.fromEntries(Object.entries(current).map(([key, entry]) => [key, { ...entry, items: change(entry.items) }])));
  }

  const say = useCallback((type, text) => setNotice({ type, text, id: Date.now() }), []);

  useEffect(() => {
    if (!notice || notice.type === "error") return undefined;
    const timer = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(timer);
  }, [notice]);

  const loadAccounts = useCallback(async () => {
    setAccountsLoading(true);
    try {
      const status = await api("/api/zernio/status");
      setConfigured(status.configured);
      if (!status.configured) return;
      const data = await api("/api/zernio/accounts");
      const list = data.accounts || [];
      setAccounts(list);
      setAccountId((current) => (list.some((entry) => entry._id === current) ? current : list[0]?._id || ""));
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        setConfigured(false);
        setKeyRejected(true);
        return;
      }
      say("error", errorText(error, "Couldn't load your Instagram accounts."));
    } finally {
      setAccountsLoading(false);
    }
  }, [say]);

  const loadExperiments = useCallback(async () => {
    setExperimentsLoading(true);
    try {
      const data = await api("/api/experiments");
      setExperiments(data.experiments || []);
    } catch (error) {
      say("error", errorText(error, "Couldn't load your tests."));
    } finally {
      setExperimentsLoading(false);
    }
  }, [say]);

  // Demo mode prefers a local sample set (public/sample/demo.json, gitignored) over the stock one.
  useEffect(() => {
    if (!isDemo) return;
    fetch("/sample/demo.json")
      .then((response) => (response.ok ? response.json() : null))
      .then((sample) => {
        if (!sample?.experiments?.length) return;
        setExperiments(withDemoEdits(sample.experiments));
        if (sample.account) setAccounts([sample.account]);
        setSelectedId(sample.experiments[0].id);
        if (sample.draft) {
          // The sample set replaces the stock demo draft.
          setDrafts({ [firstKey]: emptyDraft(), "new:sample": {
            ...emptyDraft(),
            name: sample.draft.name || "",
            hypothesis: sample.draft.hypothesis || "",
            caption: sample.draft.caption || "",
            items: (sample.draft.items || []).map((item) => ({ file: null, size: 0, errors: [], status: "ready", progress: 0, ...item })),
          } });
        }
      })
      .catch(() => {});
  }, [isDemo, firstKey]);

  useEffect(() => {
    if (isDemo) return;
    loadAccounts();
    loadExperiments();
    if (new URLSearchParams(window.location.search).get("connected") === "instagram") {
      window.history.replaceState(null, "", window.location.pathname);
      say("success", "Instagram connected.");
    }
  }, [isDemo, loadAccounts, loadExperiments, say]);

  const refreshStats = useCallback(async (testId, { quiet = false } = {}) => {
    if (isDemo) {
      if (!quiet) say("info", "Demo numbers are sample data.");
      return;
    }
    setRefreshingId(testId);
    try {
      const data = await api(`/api/experiments/${testId}/refresh`, { method: "POST", body: "{}" });
      setExperiments((current) => current.map((entry) => (entry.id === testId ? data.experiment : entry)));
      if (data.failures?.length && !quiet) say("error", `${data.failures.length} reel${data.failures.length === 1 ? "" : "s"} didn't return stats yet. Instagram can take a while.`);
    } catch (error) {
      if (!quiet) say("error", errorText(error, "Couldn't refresh stats."));
    } finally {
      setRefreshingId("");
    }
  }, [isDemo, say]);

  // Checks in on the next scheduled version a minute and a half after it was due, and keeps checking until it's live.
  useEffect(() => {
    if (isDemo) return undefined;
    const due = experiments.flatMap((entry) => entry.variants.filter((v) => v.status === "scheduled").map((v) => ({ testId: entry.id, at: Date.parse(v.publishedAt) || 0 })));
    if (!due.length) return undefined;
    const next = due.reduce((soonest, item) => (item.at < soonest.at ? item : soonest));
    const timer = setTimeout(() => refreshStats(next.testId, { quiet: true }), Math.max(60_000, next.at + 90_000 - Date.now()));
    return () => clearTimeout(timer);
  }, [experiments, isDemo, refreshStats]);

  // Rename a posted version. Trials-only: the reel on Instagram is untouched.
  const renameVersion = useCallback(async (testId, variantId, label) => {
    const next = label.replace(/\s+/g, " ").trim().slice(0, 120);
    const before = experiments.find((entry) => entry.id === testId);
    const current = before?.variants.find((entry) => entry.id === variantId);
    if (!next || !current || next === current.label) return;
    const relabel = (list, value) => list.map((entry) => (entry.id === testId
      ? { ...entry, variants: entry.variants.map((v) => (v.id === variantId ? { ...v, label: value } : v)) }
      : entry));
    setExperiments((list) => relabel(list, next));
    if (isDemo) {
      saveStored(DEMO_LABELS_KEY, variantId, next);
      return;
    }
    try {
      const data = await api(`/api/experiments/${testId}/variants/${variantId}`, { method: "PATCH", body: JSON.stringify({ label: next }) });
      setExperiments((list) => list.map((entry) => (entry.id === testId ? data.experiment : entry)));
    } catch (error) {
      setExperiments((list) => relabel(list, current.label));
      say("error", errorText(error, "Couldn't rename that version."));
    }
  }, [experiments, isDemo, say]);

  // Rename a test. Trials-only, like version names.
  const renameTest = useCallback(async (testId, name) => {
    const next = name.replace(/\s+/g, " ").trim().slice(0, 100);
    const before = experiments.find((entry) => entry.id === testId);
    if (!next || !before || next === before.name) return;
    const apply = (value) => setExperiments((list) => list.map((entry) => (entry.id === testId ? { ...entry, name: value } : entry)));
    apply(next);
    if (isDemo) {
      saveTestPatch(testId, { name: next });
      return;
    }
    try {
      const data = await api(`/api/experiments/${testId}`, { method: "PATCH", body: JSON.stringify({ name: next }) });
      setExperiments((list) => list.map((entry) => (entry.id === testId ? data.experiment : entry)));
    } catch (error) {
      apply(before.name);
      say("error", errorText(error, "Couldn't rename the test."));
    }
  }, [experiments, isDemo, say]);

  // Mark one version as the test's winner, or pass null to undo. Trials-only: sharing to followers happens in Instagram.
  const pickWinner = useCallback(async (testId, variantId) => {
    const before = experiments.find((entry) => entry.id === testId);
    if (!before) return;
    const decision = { winnerId: variantId, decidedAt: variantId ? new Date().toISOString() : null };
    const apply = (value) => setExperiments((list) => list.map((entry) => (entry.id === testId ? { ...entry, ...value } : entry)));
    apply(decision);
    const label = before.variants.find((v) => v.id === variantId)?.label;
    if (isDemo) {
      saveTestPatch(testId, decision);
      if (label) say("success", `${label} is the winner.`);
      return;
    }
    try {
      const data = await api(`/api/experiments/${testId}`, { method: "PATCH", body: JSON.stringify({ winnerId: variantId }) });
      setExperiments((list) => list.map((entry) => (entry.id === testId ? data.experiment : entry)));
      if (label) say("success", `${label} is the winner.`);
    } catch (error) {
      apply({ winnerId: before.winnerId ?? null, decidedAt: before.decidedAt ?? null });
      say("error", errorText(error, "Couldn't save the winner."));
    }
  }, [experiments, isDemo, say]);

  // Delete a test from Trials. The reels stay live on Instagram; only our record and its stats go.
  const deleteTest = useCallback(async (testId) => {
    const target = experiments.find((entry) => entry.id === testId);
    if (!target) return false;
    if (isDemo) saveStored(DEMO_DELETED_KEY, testId, true);
    else {
      try {
        await api(`/api/experiments/${testId}`, { method: "DELETE" });
      } catch (error) {
        say("error", errorText(error, "Couldn't delete the test."));
        return false;
      }
    }
    setExperiments((list) => list.filter((entry) => entry.id !== testId));
    setDrafts((current) => {
      const { [testId]: dropped, ...rest } = current;
      dropped?.items.forEach((item) => item.objectUrl?.startsWith("blob:") && URL.revokeObjectURL(item.objectUrl));
      return rest;
    });
    say("success", `Deleted ${target.name}. The reels are still on Instagram.`);
    return true;
  }, [experiments, isDemo, say]);

  // Delete one version from a test. Same rule: the reel stays on Instagram.
  const deleteVersion = useCallback(async (testId, variantId) => {
    const target = experiments.find((entry) => entry.id === testId)?.variants.find((v) => v.id === variantId);
    if (!target) return false;
    let updated = null;
    if (isDemo) saveStored(DEMO_DELETED_KEY, variantId, true);
    else {
      try {
        updated = (await api(`/api/experiments/${testId}/variants/${variantId}`, { method: "DELETE" })).experiment;
      } catch (error) {
        say("error", errorText(error, "Couldn't delete that version."));
        return false;
      }
    }
    setExperiments((list) => list.map((entry) => {
      if (entry.id !== testId) return entry;
      if (updated) return updated;
      const cleared = entry.winnerId === variantId ? { winnerId: null, decidedAt: null } : {};
      return { ...entry, ...cleared, variants: entry.variants.filter((v) => v.id !== variantId) };
    }));
    say("success", `Deleted ${target.label}. The reel is still on Instagram.`);
    return true;
  }, [experiments, isDemo, say]);

  // Pull fresh numbers when a test is opened and its last refresh is stale.
  useEffect(() => {
    if (isDemo || !experiment?.variants.length || autoRefreshed.current.has(experiment.id)) return;
    const last = experiment.variants.reduce((latest, variant) => (variant.lastRefreshedAt > latest ? variant.lastRefreshedAt : latest), "");
    if (last && Date.now() - new Date(last).getTime() < STALE_AFTER_MS) return;
    autoRefreshed.current.add(experiment.id);
    refreshStats(experiment.id, { quiet: true });
  }, [experiment, isDemo, refreshStats]);

  /** Checks the pasted key with Zernio and saves it; throws with a message the setup screen shows. */
  async function saveKey(key) {
    await api("/api/zernio/key", { method: "POST", body: JSON.stringify({ key }) });
    setKeyRejected(false);
    await loadAccounts();
    say("success", "Zernio is connected.");
  }

  async function connectInstagram() {
    try {
      const profiles = await api("/api/zernio/profiles");
      let profileId = profiles.profiles?.[0]?._id;
      if (!profileId) profileId = (await api("/api/zernio/profiles/default", { method: "POST", body: "{}" })).profile?._id;
      const redirectUrl = `${window.location.origin}${window.location.pathname}?connected=instagram`;
      const connection = await api("/api/zernio/connect", { method: "POST", body: JSON.stringify({ profileId, redirectUrl }) });
      window.location.assign(connection.authUrl);
    } catch (error) {
      say("error", errorText(error, "Couldn't start the Instagram connection."));
    }
  }

  function patchDraft(patch) {
    updateDraft(selectedId, (current) => ({ ...current, ...patch }));
  }

  function patchItem(id, patch) {
    updateItems((items) => items.map((item) => (item.id === id ? { ...item, ...patch } : item)));
  }

  function selectTest(id) {
    setSelectedId(id);
  }

  // Reuses an untouched new test if there is one, so repeated clicks don't pile up blanks.
  function startNewTest() {
    const blank = Object.entries(drafts).find(([key, entry]) => isNewKey(key) && !entry.items.length && !entry.name.trim() && !entry.hypothesis.trim());
    if (blank) {
      setSelectedId(blank[0]);
      return;
    }
    const key = newKey();
    setDrafts((current) => ({ ...current, [key]: emptyDraft() }));
    setSelectedId(key);
  }

  async function addFiles(fileList) {
    if (publishing) return;
    const files = Array.from(fileList || []).filter((file) => file.type.startsWith("video/") || /\.(mp4|mov|m4v)$/i.test(file.name));
    if (!files.length) return;

    const key = selectedId;
    const base = draft;
    const publishedCount = experiment?.variants.length || 0;
    const room = MAX_FILES - publishedCount - base.items.length;
    if (room <= 0) {
      say("error", `A test holds up to ${MAX_FILES} versions.`);
      return;
    }
    if (files.length > room) say("info", `Added ${room}. A test holds up to ${MAX_FILES} versions.`);

    const placeholders = files.slice(0, room).map((file) => ({
      id: crypto.randomUUID(),
      file,
      name: stripExtension(file.name),
      size: file.size,
      thumbnail: "",
      objectUrl: "",
      duration: 0,
      errors: [],
      status: "checking",
      progress: 0,
    }));
    updateDraft(key, (current) => ({ ...current, items: [...current.items, ...placeholders] }));

    await Promise.all(placeholders.map(async (placeholder) => {
      const details = await inspectVideo(placeholder.file);
      patchItem(placeholder.id, { ...details, status: details.errors.length ? "invalid" : "ready" });
    }));
  }

  function removeItem(id) {
    if (publishing) return;
    const target = Object.values(drafts).flatMap((entry) => entry.items).find((item) => item.id === id);
    if (target?.objectUrl?.startsWith("blob:")) URL.revokeObjectURL(target.objectUrl);
    updateItems((items) => items.filter((item) => item.id !== id));
  }

  function clearDraft() {
    if (publishing) return;
    draft.items.forEach((item) => item.objectUrl?.startsWith("blob:") && URL.revokeObjectURL(item.objectUrl));
    updateDraft(selectedId, (current) => ({ ...current, items: [] }));
  }

  // Drops an unpublished new test: its videos, name and caption. Nothing was posted, so nothing else changes.
  function deleteDraft(key = selectedId) {
    if (publishing || !isNewKey(key)) return;
    setDrafts((current) => {
      const { [key]: dropped, ...rest } = current;
      dropped?.items.forEach((item) => item.objectUrl?.startsWith("blob:") && URL.revokeObjectURL(item.objectUrl));
      return rest;
    });
    say("success", "Draft deleted.");
  }

  function moveItem(id, targetId) {
    if (publishing) return;
    updateDraft(selectedId, (current) => ({ ...current, items: reorderItems(current.items, id, targetId) }));
  }

  function nudgeItem(id, direction) {
    const index = draft.items.findIndex((item) => item.id === id);
    const target = draft.items[index + direction];
    if (target) moveItem(id, target.id);
  }

  async function pollPost(variantId, postId) {
    for (let attempt = 0; attempt < POLL_LIMIT; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL));
      try {
        const data = await api(`/api/zernio/posts/${postId}`);
        const state = platformState(data.post || data);
        if (isLive(state.status) || isFailed(state.status)) {
          setLiveStatus((current) => ({ ...current, [variantId]: { status: isLive(state.status) ? "published" : "failed", url: state.url, error: state.error } }));
          return;
        }
      } catch {
        return;
      }
    }
  }

  async function publishItem(item, testId, caption, scheduledFor = null) {
    patchItem(item.id, { status: "uploading", progress: 0, error: "" });
    const presigned = await api("/api/zernio/presign", {
      method: "POST",
      body: JSON.stringify({ filename: item.file.name, contentType: item.file.type || "video/mp4", size: item.file.size }),
    });
    await uploadVideo(presigned.uploadUrl, item.file, (progress) => patchItem(item.id, { progress }));
    patchItem(item.id, { status: "publishing", progress: 100 });

    const created = await api("/api/zernio/posts", {
      method: "POST",
      body: JSON.stringify({
        accountId,
        mediaUrl: presigned.publicUrl,
        caption,
        requestId: item.requestId || item.id,
        scheduledFor: scheduledFor ? new Date(scheduledFor).toISOString() : null,
        metadata: { trialrExperimentId: testId, trialrVariantLabel: item.name },
      }),
    });
    const post = created.post || created.existingPost;
    const state = platformState(post);
    if (isFailed(state.status)) throw new Error(state.error || "Instagram rejected this Reel.");
    if (!post?._id) throw new Error("Zernio didn't return a post id.");
    const scheduled = post.status === "scheduled" && post.scheduledFor;

    const tracked = await api(`/api/experiments/${testId}/variants`, {
      method: "POST",
      body: JSON.stringify({
        label: item.name,
        originalFilename: item.file.name,
        zernioPostId: post._id,
        platformPostId: state.platformPostId,
        platformPostUrl: state.url,
        mediaUrl: presigned.publicUrl,
        thumbnail: item.thumbnail,
        status: scheduled ? "scheduled" : isLive(state.status) ? "published" : state.status,
        publishedAt: scheduled ? post.scheduledFor : state.publishedAt || new Date().toISOString(),
      }),
    });

    setExperiments((current) => current.map((entry) => (entry.id === testId ? tracked.experiment : entry)));
    if (!scheduled) setLiveStatus((current) => ({ ...current, [tracked.variant.id]: { status: isLive(state.status) ? "published" : "processing", url: state.url } }));
    updateItems((items) => items.filter((entry) => entry.id !== item.id));
    if (item.objectUrl?.startsWith("blob:")) URL.revokeObjectURL(item.objectUrl);
    if (!scheduled && !isLive(state.status)) pollPost(tracked.variant.id, post._id);
    return scheduled ? Date.parse(post.scheduledFor) : Date.now();
  }

  async function publish(onlyItem) {
    if (isDemo) {
      say("info", "This is the demo. Nothing gets posted from here.");
      return;
    }
    if (publishing || !accountId) return;
    const queue = onlyItem ? [onlyItem] : getReadyItems(draftItems);
    if (!queue.length) return;

    setPublishing(true);
    setNotice(null);
    let testId = draft.testId;
    const caption = draft.caption.trim();

    try {
      if (!testId) {
        const created = await api("/api/experiments", {
          method: "POST",
          body: JSON.stringify({ name: draft.name.trim() || defaultTestName(), hypothesis: draft.hypothesis, primaryMetric: draft.metric, caption }),
        });
        testId = created.experiment.id;
        setExperiments((current) => [created.experiment, ...current]);
        const fromKey = selectedId;
        setDrafts((current) => {
          const { [fromKey]: moved, ...rest } = current;
          return { ...rest, [testId]: { ...moved, testId } };
        });
        autoRefreshed.current.add(testId);
        setSelectedId(testId);
      }
    } catch (error) {
      setPublishing(false);
      say("error", errorText(error, "Couldn't create the test."));
      return;
    }

    // Space versions out, starting after anything this test already has going out.
    const existing = experiments.find((entry) => entry.id === testId)?.variants || [];
    let previous = existing.reduce((latest, v) => Math.max(latest, Date.parse(v.publishedAt) || 0), 0) || null;
    let lastAt = null;
    let failed = 0;
    for (const item of queue) {
      try {
        const at = await publishItem(item, testId, caption, nextPostTime(previous));
        previous = at;
        lastAt = at;
      } catch (error) {
        failed += 1;
        patchItem(item.id, { status: "failed", requestId: item.requestId || item.id, error: errorText(error, "Publishing failed.") });
      }
    }
    setPublishing(false);

    const sent = queue.length - failed;
    const minutes = lastAt ? Math.round((lastAt - Date.now()) / 60000) : 0;
    const spread = minutes >= 1 ? ` They go out a few minutes apart so Instagram doesn't flag them as duplicates. The last one posts at ${formatClock(lastAt)}, about ${minutes} minute${minutes === 1 ? "" : "s"} from now. You can close this tab.` : "";
    if (failed) say("error", `${sent} of ${queue.length} sent. ${failed} failed. Retry from the tile.${spread}`);
    else say("success", `${sent} Trial Reel${sent === 1 ? "" : "s"} sent.${spread || " Stats start showing within the hour."}`);
  }

  const canPublish = !publishing
    && Boolean(accountId)
    && draftItems.length > 0
    && draftItems.every((item) => ["ready", "failed"].includes(item.status))
    && getReadyItems(draftItems).length > 0
    && draft.caption.trim().length > 0
    && draft.caption.length <= MAX_CAPTION;

  let blocker = "";
  if (!accountId) blocker = "Connect an Instagram account first.";
  else if (draftItems.some((item) => item.status === "checking")) blocker = "Checking your videos.";
  else if (draftItems.some((item) => item.status === "invalid")) blocker = "Remove the videos marked in red.";
  else if (!draft.caption.trim()) blocker = "Add a caption.";
  else if (draft.caption.length > MAX_CAPTION) blocker = "Caption is over 2,200 characters.";

  // File-named versions show without the words they all share; the stored names stay whole.
  const shown = useMemo(() => experiments.map((e) => {
    const variants = shortLabels(e.variants);
    return variants === e.variants ? e : { ...e, variants };
  }), [experiments]);

  return {
    isDemo, theme, setTheme,
    configured, keyRejected, saveKey, accounts, account, accountId, setAccountId, accountsLoading,
    experiments: shown, experimentsLoading, selectedId, selectTest, startNewTest, isNewSelected,
    experiment: experiment && shown.find((e) => e.id === experiment.id), draft, draftItems, drafts: draftList, liveStatus, publishing, refreshingId,
    notice, setNotice, canPublish, blocker,
    patchDraft, patchItem, addFiles, removeItem, clearDraft, deleteDraft, moveItem, nudgeItem,
    publish, refreshStats, renameVersion, renameTest, pickWinner, deleteTest, deleteVersion, connectInstagram,
  };
}
