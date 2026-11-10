import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useTrialr } from "../useTrialr.js";
import { BREAKOUT_VIEWS, HELD_AFTER_HOURS, HELD_UNDER_VIEWS, MAX_CAPTION, MAX_FILES, METRICS, formatClock, formatDuration, formatMetric, heldBack, isRate, letterFor, lowerIsBetter, metricLabel, metricValue, timeAgo } from "../lib.js";
import {
  BackIcon,
  ChevronIcon,
  ConfirmDialog,
  DecidedIcon,
  ExternalIcon,
  KeyIcon,
  MenuIcon,
  OverviewIcon,
  PlayIcon,
  PlusIcon,
  RefreshIcon,
  ResizeHandle,
  SegmentedControl,
  SlidingHighlight,
  StatusPill,
  Tag,
  TestIcon,
  Toast,
  TrashIcon,
  TrophyIcon,
  UploadIcon,
  outlineButton,
  primaryButton,
  quietButton,
  staggerDelay,
  textButton,
} from "./ui.jsx";

const ACCEPT = "video/mp4,video/quicktime,video/x-m4v,.mp4,.mov,.m4v";
const RANK_OPTIONS = [
  { value: "views", label: "Views" },
  { value: "reach", label: "Reach" },
  { value: "igReelsAvgWatchTime", label: "Watch" },
  { value: "shares", label: "Shares" },
  { value: "saves", label: "Saves" },
];
const THEME_OPTIONS = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Auto" },
];
const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

const n = (v) => Number(v || 0).toLocaleString("en-US");
const plural = (v, one, many = `${one}s`) => `${n(v)} ${v === 1 ? one : many}`;
const handleOf = (account) => (account ? `@${String(account.username || account.displayName || "").replace(/^@/, "")}` : "");
const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes("Files");
const ordinal = (i) => ["1st", "2nd", "3rd"][i] || `${i + 1}th`;
const signed = (p) => `${p < 0 ? "−" : "+"}${Math.abs(p)}%`;
const isPublished = (status) => ["published", "success", "completed"].includes(status);

function hoursSince(iso, now) {
  return iso ? (now - new Date(iso).getTime()) / 3600_000 : 0;
}

function span(iso, now) {
  const h = hoursSince(iso, now);
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} minutes`;
  if (h < 48) return plural(Math.round(h), "hour");
  return plural(Math.round(h / 24), "day");
}

/** Versions ranked by a metric. Letters stay with the order they were posted in. Held-back versions don't compete. */
function rank(variants, metric, held = []) {
  const out = new Set(held.map((v) => v.id));
  const rows = variants.map((variant, index) => ({ variant, letter: letterFor(index), value: metricValue(variant, metric), held: out.has(variant.id) }));
  const measured = rows.filter((r) => r.value !== null && !r.held);
  const low = lowerIsBetter(metric);
  // Best first; held-back versions after the rest, versions without a number last.
  const sorted = [...rows].sort((a, b) => (a.value === null) - (b.value === null) || a.held - b.held || (low ? a.value - b.value : b.value - a.value));
  const max = Math.max(0, ...measured.map((r) => r.value));
  const best = measured.length ? sorted[0].value : null;
  const leader = measured.length > 1 && max > 0 ? sorted[0] : null;
  const runnerUp = leader ? sorted[1] : null;
  const margin = leader && runnerUp?.value ? Math.round((Math.abs(leader.value - runnerUp.value) / runnerUp.value) * 100) : null;
  // The one version Instagram is showing while it holds the rest back.
  const lone = measured.length === 1 && out.size ? measured[0] : null;
  return { rows, sorted, max, best, leader, runnerUp, margin, lone, measured: measured.length };
}

const TIME_METRICS = ["igReelsAvgWatchTime", "igReelsVideoViewTotalTime"];

/** The leader's lead: a percent, or both numbers when the runner-up is too small for a percent to mean anything ("4700% more"). */
function leadBy(r, metric) {
  if (r.margin === null || !r.runnerUp) return null;
  if (!isRate(metric) && !TIME_METRICS.includes(metric) && r.runnerUp.value < HELD_UNDER_VIEWS) {
    return { percent: false, text: `${formatMetric(metric, r.leader.value)} to ${formatMetric(metric, r.runnerUp.value)}` };
  }
  return { percent: true, text: `${r.margin}%` };
}

/** How far a version sits from the best: percent for counts, points for rates. */
function gap(metric, value, best) {
  if (value === null || best === null || value === best) return "";
  if (isRate(metric)) {
    const pts = value - best;
    return `${pts < 0 ? "−" : "+"}${Math.abs(pts).toFixed(1)} pts`;
  }
  return best > 0 ? signed(Math.round(((value - best) / best) * 100)) : "";
}

function winnerOf(experiment) {
  return experiment.winnerId ? experiment.variants.find((v) => v.id === experiment.winnerId) || null : null;
}

// A scheduled version past its time is with Instagram, which takes a minute or two to finish it.
const isDue = (status, at) => status === "scheduled" && Date.parse(at) <= Date.now();

function whenLabel(status, at) {
  if (status !== "scheduled") return `Posted ${timeAgo(at)}`;
  return isDue(status, at) ? "Posting now" : `Posts at ${formatClock(at)}`;
}

function firstPost(variants) {
  return variants.reduce((earliest, v) => (!earliest || v.publishedAt < earliest ? v.publishedAt : earliest), "");
}

/* Shell */

function MobileBar({ title, back, onMenu, until = "md" }) {
  return (
    <div className={`sticky top-0 z-30 flex h-12 shrink-0 items-center gap-3 border-b border-line bg-inherit px-4 ${until === "lg" ? "lg:hidden" : "md:hidden"}`}>
      {back ? (
        <button type="button" onClick={back.onClick} className="-ml-2 flex min-h-11 min-w-11 items-center gap-1 rounded-md pl-1 pr-3 text-[14px] text-ink-2 hover:text-ink">
          <BackIcon className="h-4 w-4 shrink-0" />
          <span className="truncate">{back.label}</span>
        </button>
      ) : (
        <>
          <button type="button" onClick={onMenu} aria-label="Open menu" className="-ml-3 flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-ink-2 hover:bg-hover hover:text-ink">
            <MenuIcon className="h-5 w-5" />
          </button>
          <span className="truncate font-display text-[16px] font-semibold tracking-[-0.02em]">{title || "Trials"}</span>
        </>
      )}
    </div>
  );
}

function Nav({ t, home, onHome, onTest, onNew }) {
  const { experiments, experimentsLoading, selectedId, drafts, account, accountsLoading, configured, connectInstagram, saveKey, theme, setTheme, isDemo } = t;
  const [keyOpen, setKeyOpen] = useState(false);
  const newDrafts = drafts.filter((d) => d.key.startsWith("new"));

  const item = (active) =>
    `relative z-[1] flex h-11 w-full shrink-0 items-center gap-[9px] rounded-control px-[9px] text-left text-[14px] transition-colors lg:h-8 lg:text-[13.5px] ${
      active ? "font-medium text-ink" : "text-ink-2 hover:text-ink"
    }`;
  const label = "mb-1 mt-[18px] px-[9px] text-[11.5px] font-medium text-ink-3";
  const count = "ml-auto pl-2 text-[12px] font-normal tabular-nums text-ink-3";

  return (
    <nav aria-label="Main" className="flex h-full flex-col overflow-y-auto bg-canvas px-2.5 pb-2 pt-3 lg:pl-3.5">
      <button type="button" onClick={onHome} className="mb-3 flex min-h-11 shrink-0 items-center gap-[9px] px-2 text-left font-display text-[20px] font-semibold tracking-[-0.03em] text-ink lg:min-h-0 lg:py-1.5">
        <span aria-hidden="true" className="grid h-[26px] w-[26px] place-items-center text-[20px] leading-none">🧪</span>
        Trials
        {isDemo && <span className="ml-auto rounded-full bg-hover px-[7px] font-sans text-[11px] font-medium leading-[18px] tracking-normal text-ink-3">Demo</span>}
      </button>

      <button
        type="button"
        onClick={onNew}
        className="mb-2.5 flex h-11 w-full shrink-0 items-center justify-center gap-1.5 rounded-control bg-accent text-[13.5px] font-medium text-accent-ink transition-[opacity,transform] hover:opacity-90 active:scale-[.98] lg:h-9"
      >
        <PlusIcon className="h-4 w-4" />
        New test
      </button>

      <SlidingHighlight selector="[aria-current]" highlightClassName="rounded-control bg-bg shadow-resting">
        <button type="button" onClick={onHome} aria-current={home ? "page" : undefined} className={item(home)}>
          <OverviewIcon className="h-4 w-4 shrink-0 text-ink-3" />
          <span>Overview</span>
        </button>

        <div className={label}>Tests</div>
        <ul className="space-y-px">
          {experimentsLoading && <li className="px-[9px] py-1.5 text-[12.5px] text-ink-3">Loading</li>}
          {experiments.map((experiment) => {
            const active = !home && selectedId === experiment.id;
            const pending = drafts.find((d) => d.key === experiment.id)?.items.length || 0;
            return (
              <li key={experiment.id}>
                <button type="button" onClick={() => onTest(experiment.id)} aria-current={active ? "page" : undefined} className={item(active)}>
                  {experiment.winnerId ? (
                    <DecidedIcon className="h-4 w-4 shrink-0 text-ink-2" />
                  ) : (
                    <TestIcon className="h-4 w-4 shrink-0 text-ink-3" />
                  )}
                  <span className="min-w-0 truncate">{experiment.name}</span>
                  {pending ? (
                    <span className="ml-auto rounded-full bg-accent px-[7px] text-[11px] font-medium leading-[18px] text-accent-ink tabular-nums">
                      {pending}
                      <span className="sr-only"> waiting</span>
                    </span>
                  ) : (
                    <span className={count}>{experiment.variants.length}</span>
                  )}
                </button>
              </li>
            );
          })}
          {!experimentsLoading && experiments.length === 0 && <li className="px-[9px] py-1.5 text-[12.5px] text-ink-3">None published yet</li>}
        </ul>

        {newDrafts.length > 0 && (
          <>
            <div className={label}>Drafts</div>
            <ul className="space-y-px">
              {newDrafts.map((d) => {
                const active = !home && selectedId === d.key;
                return (
                  <li key={d.key}>
                    <button type="button" onClick={() => onTest(d.key)} aria-current={active ? "page" : undefined} className={item(active)}>
                      <TestIcon className="h-4 w-4 shrink-0 text-ink-3" />
                      <span className={`min-w-0 truncate ${d.name.trim() ? "" : "text-ink-3"}`}>{d.name.trim() || "Untitled test"}</span>
                      {d.items.length > 0 ? (
                        <span className="ml-auto rounded-full bg-accent px-[7px] text-[11px] font-medium leading-[18px] text-accent-ink tabular-nums">
                          {d.items.length}
                          <span className="sr-only"> waiting</span>
                        </span>
                      ) : (
                        <span className={count}>New</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </SlidingHighlight>

      <div className="mt-auto space-y-2 pt-6">
        <SegmentedControl label="Theme" options={THEME_OPTIONS} value={theme} onChange={setTheme} />
        <div className="flex items-center gap-[9px] rounded-control px-2 py-1.5">
          {account?.profilePicture && !isDemo ? (
            <img src={account.profilePicture} alt="" referrerPolicy="no-referrer" className="h-6 w-6 shrink-0 rounded-full object-cover" />
          ) : (
            <span aria-hidden="true" className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-hover-2 font-display text-[11px] font-semibold text-ink-2">
              {(handleOf(account)[1] || "?").toUpperCase()}
            </span>
          )}
          {accountsLoading ? (
            <span className="text-[12.5px] text-ink-3">Loading account</span>
          ) : configured === false ? (
            <span className="text-[12.5px] text-ink-3">Zernio not connected</span>
          ) : account ? (
            <>
              <span className="min-w-0 flex-1 truncate text-[12.5px] text-ink-2">{handleOf(account)}</span>
              <span className="shrink-0 text-[12px] text-ink-3">Instagram</span>
            </>
          ) : (
            <button type="button" onClick={connectInstagram} className="min-h-11 text-[12.5px] text-ink-2 hover:text-ink lg:min-h-0">Connect Instagram</button>
          )}
          {configured && !isDemo && (
            <button type="button" onClick={() => setKeyOpen(true)} title="Change Zernio key" aria-label="Change Zernio key" className="-mr-1 grid h-11 w-11 shrink-0 place-items-center rounded-control text-ink-3 transition-colors hover:bg-hover hover:text-ink lg:h-7 lg:w-7">
              <KeyIcon className="h-[15px] w-[15px]" />
            </button>
          )}
        </div>
      </div>
      <KeyDialog open={keyOpen} onClose={() => setKeyOpen(false)} onSave={saveKey} />
    </nav>
  );
}

/** Sticky bar at the top of a detail pane: crumbs left, status and actions right. Its rule appears once you scroll. */
function DetailBar({ scrolled, crumbs, right }) {
  return (
    <div className={`sticky top-0 z-20 hidden h-[54px] items-center justify-between gap-3 border-b bg-bg px-[22px] transition-colors lg:flex ${scrolled ? "border-line" : "border-transparent"}`}>
      <div className="flex min-w-0 items-center gap-1.5 text-[12.5px] text-ink-3">
        {crumbs.map((crumb, i) => (
          <span key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <span aria-hidden="true">/</span>}
            {crumb.onClick ? (
              <button type="button" onClick={crumb.onClick} className="-ml-1 max-w-[220px] truncate rounded-md px-1 py-0.5 hover:bg-hover hover:text-ink">{crumb.label}</button>
            ) : (
              <span className="truncate font-medium text-ink-2">{crumb.label}</span>
            )}
          </span>
        ))}
      </div>
      <div className="flex shrink-0 items-center gap-3">{right}</div>
    </div>
  );
}

function Detail({ empty, className = "", bar, mobileBar, children }) {
  const [scrolled, setScrolled] = useState(false);
  return (
    <section className={`pane-detail ${empty ? "pane-empty" : ""} ${className}`} onScroll={(e) => setScrolled(e.currentTarget.scrollTop > 4)}>
      {mobileBar}
      {bar && bar(scrolled)}
      {children}
    </section>
  );
}

function Thumb({ src, className = "w-[42px]", children }) {
  return (
    <span className={`relative block aspect-[9/16] shrink-0 overflow-hidden rounded-[7px] bg-hover shadow-[inset_0_0_0_1px_var(--line)] ${className}`}>
      {src && <img src={src} alt="" draggable={false} className="absolute inset-0 h-full w-full object-cover" />}
      {children}
    </span>
  );
}

function Player({ src, poster, label }) {
  const ref = useRef(null);
  const [playing, setPlaying] = useState(false);
  return (
    <div className="relative aspect-[9/16] w-full overflow-hidden rounded-card bg-black shadow-raised">
      <video
        ref={ref}
        src={src}
        poster={poster}
        playsInline
        loop
        controls={playing}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        className="absolute inset-0 h-full w-full object-cover"
        aria-label={label}
      />
      {!playing && src && (
        <button type="button" onClick={() => ref.current?.play()} aria-label={`Play ${label}`} className="group absolute inset-0 grid place-items-center">
          <span className="grid h-12 w-12 place-items-center rounded-full bg-bg/90 text-ink shadow-floating transition-transform duration-[580ms] ease-spring group-hover:scale-105">
            <PlayIcon className="ml-0.5 h-4 w-4" />
          </span>
        </button>
      )}
    </div>
  );
}

/* Overview */

const VIEW_KEY = "trialr-overview-view";
const VIEW_OPTIONS = [
  { value: "page", label: "Page" },
  { value: "chart", label: "Chart" },
];

function OverviewPage({ t, onTest, onMenu, now }) {
  const { experiments, drafts, refreshingId } = t;
  const [view, setViewState] = useState(() => {
    try {
      return localStorage.getItem(VIEW_KEY) === "chart" ? "chart" : "page";
    } catch {
      return "page";
    }
  });
  const setView = (value) => {
    setViewState(value);
    try {
      localStorage.setItem(VIEW_KEY, value);
    } catch {
      // Not remembered, still switches.
    }
  };
  const chart = view === "chart" && experiments.length > 0;
  const allVariants = experiments.flatMap((e) => e.variants);
  const views = allVariants.reduce((sum, v) => sum + Number(v.analytics?.views || 0), 0);
  const best = allVariants.reduce((top, v) => (Number(v.analytics?.views || 0) > Number(top?.analytics?.views || 0) ? v : top), null);
  const bestTest = best ? experiments.find((e) => e.variants.includes(best)) : null;

  const nextUp = [];
  drafts.filter((d) => d.items.length).forEach((d) => {
    const where = d.testId ? experiments.find((e) => e.id === d.testId)?.name : d.name.trim() || "an untitled test";
    nextUp.push({ key: `draft-${d.key}`, text: <>{plural(d.items.length, "version")} {d.items.length === 1 ? "is" : "are"} waiting to post in </>, link: where, id: d.key });
  });
  experiments.forEach((e) => {
    const metric = e.primaryMetric || "views";
    const r = rank(e.variants, metric, heldBack(e.variants, now));
    const lead = leadBy(r, metric);
    const hours = hoursSince(firstPost(e.variants), now);
    if (!e.variants.length || winnerOf(e)) return;
    if (hours < 24) nextUp.push({ key: e.id, text: <>Give it time. Compare after the same 24 hours: check </>, link: e.name, id: e.id, after: ` again in ${plural(Math.ceil(24 - hours), "hour")}.` });
    else if (r.leader && r.margin >= 10) nextUp.push({ key: e.id, text: <>{r.leader.variant.label} is ahead {lead.percent ? `by ${lead.text}` : `(${lead.text} ${metricLabel(metric).toLowerCase()})`} in </>, link: e.name, id: e.id, after: ". Share it with your followers from Instagram." });
  });

  return (
    <div className={`flex h-dvh flex-col overflow-y-auto bg-bg lg:grid lg:grid-rows-1 lg:gap-x-2 lg:overflow-hidden lg:bg-canvas lg:p-2 lg:pl-0 ${chart ? "lg:grid-cols-[minmax(0,1fr)]" : "lg:grid-cols-[var(--list-w,372px)_minmax(0,1fr)]"}`}>
      <MobileBar onMenu={onMenu} />
      <div className={`${chart ? "hidden" : "contents lg:flex"} lg:col-start-1 lg:row-start-1 lg:min-h-0 lg:flex-col lg:overflow-hidden lg:rounded-panel lg:bg-bg lg:shadow-resting`}>
        <header className="px-[18px] pb-3 pt-[18px]">
          <h1 className="font-display text-[19px] font-semibold leading-[1.15] tracking-[-0.03em]">Overview</h1>
          <p className="mt-[3px] text-[13px] leading-[1.45] text-ink-3">
            {experiments.length ? `${plural(experiments.length, "test")}, ${plural(allVariants.length, "Trial Reel")}` : "No tests yet"}
          </p>
        </header>
        <section aria-label="Tests" className="order-2 pb-6 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
          <ul className="flex flex-col gap-0.5 px-2.5 pt-1">
            {experiments.map((e, i) => {
              const r = rank(e.variants, e.primaryMetric || "views", heldBack(e.variants, now));
              const lead = leadBy(r, e.primaryMetric || "views");
              const winner = winnerOf(e);
              const marked = winner?.id || r.leader?.variant.id || r.lone?.variant.id;
              return (
                <li key={e.id} className="card-in" style={{ animationDelay: `${staggerDelay(i)}ms` }}>
                  <button type="button" onClick={() => onTest(e.id)} className="block w-full rounded-card px-3 pb-[11px] pt-3 text-left transition-colors hover:bg-[color-mix(in_oklch,var(--hover)_55%,transparent)]">
                    <div className="flex items-baseline gap-2">
                      <div className="min-w-0 flex-1 truncate text-[13.5px] font-medium leading-[1.3] tracking-[-0.012em] text-ink">{e.name}</div>
                      <span className="shrink-0 text-[11.5px] tabular-nums text-ink-3">{timeAgo(e.createdAt, now)}</span>
                    </div>
                    <div className="mt-1 text-[12.5px] leading-[1.45] text-ink-2">
                      {winner ? <><span className="font-medium text-ink">{winner.label}</span> won</> : r.leader ? <>{r.leader.variant.label} leads on {metricLabel(e.primaryMetric).toLowerCase()}{lead && <>, {lead.percent ? `by ${lead.text}` : lead.text}</>}</> : r.lone ? <>Only {r.lone.variant.label} is getting reach</> : r.rows.some((x) => x.held) ? "Held back by Instagram" : e.variants.length ? "Waiting on stats" : "Nothing posted yet"}
                    </div>
                    <div className="mt-2.5 flex gap-1">
                      {r.rows.map((row) => (
                        <Thumb key={row.variant.id} src={row.variant.thumbnail} className={`w-[26px] ${marked === row.variant.id ? "ring-2 ring-ink ring-offset-1 ring-offset-bg" : ""}`} />
                      ))}
                    </div>
                  </button>
                </li>
              );
            })}
            {!experiments.length && <li className="px-2 py-4 text-[13px] text-ink-3">Your tests show up here once you publish one.</li>}
          </ul>
        </section>
      </div>
      <section aria-label="Summary" className={`bleed-host order-1 px-[18px] pb-10 pt-8 lg:order-none lg:row-start-1 ${chart ? "lg:col-start-1" : "lg:col-start-2"} lg:overflow-y-auto lg:rounded-panel lg:bg-bg lg:p-0 lg:shadow-resting`}>
        <div className="sticky top-0 z-20 hidden h-12 items-center justify-between bg-bg px-5 lg:flex">
          <span className="text-[13px] text-ink-3">Overview</span>
          {refreshingId && <StatusPill tone="busy">Refreshing stats</StatusPill>}
        </div>
        <div key={view} className={`detail-in lg:mx-auto lg:pb-24 lg:pt-[22px] ${chart ? "lg:max-w-[1240px] lg:px-10" : "lg:max-w-[720px] lg:px-12"}`}>
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
            <h2 className="font-display text-[30px] font-semibold leading-[1.15] tracking-[-0.035em] text-ink md:text-[36px]">Your tests</h2>
            {experiments.length > 0 && <SegmentedControl label="Overview layout" options={VIEW_OPTIONS} value={view} onChange={setView} className="w-[156px]" />}
          </div>
          <p className="mt-3 max-w-[640px] text-[16px] leading-[1.6] text-ink-2 md:text-[17px]">
            {allVariants.length === 0 ? (
              "Nothing posted yet. Start a test with two or more versions of the same reel, and Trials will tell you which one wins."
            ) : (
              <>
                You've posted <b className="font-medium text-ink">{plural(allVariants.length, "Trial Reel")}</b> across{" "}
                <b className="font-medium text-ink">{plural(experiments.length, "test")}</b>, for <b className="font-medium text-ink">{plural(views, "view")}</b>.
                {best && bestTest && (
                  <> Your strongest version is <b className="font-medium text-ink">{best.label}</b> from {bestTest.name}, at {n(best.analytics.views)}.</>
                )}
              </>
            )}
          </p>

          {chart && <ChartTable experiments={experiments} onTest={onTest} />}

          {experiments.length > 0 && !chart && (
            <ul className="wide-table mt-[30px]">
              {experiments.map((e) => {
                const metric = e.primaryMetric || "views";
                const r = rank(e.variants, metric, heldBack(e.variants, now));
                const top = r.leader || r.lone;
                const winner = winnerOf(e);
                const cover = winner || top?.variant || e.variants.find((v) => v.thumbnail) || e.variants[0];
                return (
                  <li key={e.id} className="flex gap-4 border-b border-line py-4 sm:gap-5">
                    <button
                      type="button"
                      onClick={() => onTest(e.id)}
                      aria-label={`Open ${e.name}`}
                      title={winner ? `Winner: ${winner.label}` : r.leader ? `Leading: ${r.leader.variant.label}` : e.name}
                      className="relative aspect-[9/16] w-[64px] shrink-0 self-start overflow-hidden rounded-[9px] bg-hover shadow-[inset_0_0_0_1px_var(--line)] transition-transform duration-200 ease-std hover:scale-[1.02] sm:aspect-auto sm:w-[94px] sm:self-stretch"
                    >
                      {cover?.thumbnail && <img src={cover.thumbnail} alt="" draggable={false} className="absolute inset-0 h-full w-full object-cover" />}
                      {winner && <span className="absolute left-1.5 top-1.5"><Tag gold>🏆 Winner</Tag></span>}
                    </button>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-col gap-2 md:flex-row md:items-start md:gap-6">
                        <div className="min-w-0 md:w-[34%] md:shrink-0">
                          <button type="button" onClick={() => onTest(e.id)} className="text-left text-[16.5px] font-medium leading-[1.3] tracking-[-0.015em] text-ink hover:underline hover:decoration-line hover:underline-offset-4">{e.name}</button>
                          <div className="mt-0.5 text-[12px] text-ink-3">
                            {plural(e.variants.length, "version")}, {span(firstPost(e.variants), now)} in
                          </div>
                        </div>
                        <div className="min-w-0 flex-1 md:pt-2">
                          <div className="flex gap-[3px]" role="img" aria-label={`${plural(e.variants.length, "version")} ranked by ${metricLabel(metric).toLowerCase()}`}>
                            {r.sorted.map((row) => (
                              <span
                                key={row.variant.id}
                                title={`${row.letter}, ${row.variant.label}: ${formatMetric(metric, row.value)}`}
                                className={`h-1.5 min-w-2 rounded-full ${top?.variant.id === row.variant.id ? "bg-lead" : "bg-hover-2"}`}
                                style={{ flexGrow: Math.max(row.value || 0, (r.max || 1) * 0.04) }}
                              />
                            ))}
                          </div>
                          <div className="mt-1.5 text-[12px] leading-[1.5] text-ink-3">
                            {winner ? (
                              <>You picked <span className="text-ink-2">{winner.label}</span> as the winner{r.leader && r.leader.variant.id !== winner.id ? <>. {r.leader.variant.label} leads on {metricLabel(metric).toLowerCase()}</> : null}</>
                            ) : r.leader ? <>{r.leader.letter}, {r.leader.variant.label}, leads on {metricLabel(metric).toLowerCase()} with {formatMetric(metric, r.leader.value)}</> : r.lone ? <>{r.lone.letter}, {r.lone.variant.label}, is the only one getting reach</> : r.rows.some((x) => x.held) ? "Held back by Instagram" : "Not enough numbers yet"}
                          </div>
                        </div>
                      </div>
                      <div className="mt-3">
                        <TestTotals variants={e.variants} />
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {nextUp.length > 0 && (
            <div className={`mt-[34px] rounded-card bg-bg px-[18px] py-4 shadow-resting ${chart ? "max-w-[640px]" : ""}`}>
              <h3 className="text-[13px] font-medium text-ink-2">What to do next</h3>
              {nextUp.map((step) => (
                <p key={step.key} className="mt-2 text-[14px] leading-[1.55] text-ink-2">
                  {step.text}
                  <button type="button" onClick={() => onTest(step.id)} className="text-ink underline decoration-line underline-offset-4 hover:decoration-ink-3">{step.link}</button>
                  {step.after || "."}
                </p>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

const CHART_LABELS = {
  views: "Views",
  reach: "Reach",
  igReelsAvgWatchTime: "Avg watch",
  igReelsVideoViewTotalTime: "Watched",
  reelsSkipRate: "Skip rate",
  likes: "Likes",
  comments: "Comments",
  shares: "Shares",
  saves: "Saves",
  engagementRate: "Engagement",
};
const CHART_KEYS = Object.keys(CHART_LABELS);

/** Order two numbers for a column, keeping missing numbers last whichever way it's sorted. */
function byValue(a, b, dir) {
  if (a === null || a === undefined) return b === null || b === undefined ? 0 : 1;
  if (b === null || b === undefined) return -1;
  return dir === "asc" ? a - b : b - a;
}

/** How full a cell's bar is: share of the column's best, inverted for metrics where lower wins. */
function barFill(key, value, best) {
  if (value === null || value === undefined || !best) return 0;
  return lowerIsBetter(key) ? Math.min(1, best / value) : Math.min(1, value / best);
}

function ChartCell({ metric, value, best, strong, bar = "test" }) {
  const fill = barFill(metric, value, best);
  return (
    <td className="whitespace-nowrap px-2.5 py-0 text-right align-middle tabular-nums">
      <span className={strong ? "font-medium text-ink" : "text-ink-2"}>{value === null || value === undefined ? "–" : formatMetric(metric, value)}</span>
      <span aria-hidden="true" className={`mt-1 block overflow-hidden rounded-full ${bar === "version" ? "h-[2px]" : "h-[3px]"}`}>
        <span className={`block h-full origin-left rounded-full ${strong ? "bg-lead" : "bg-line-strong"}`} style={{ transform: `scaleX(${fill})` }} />
      </span>
    </td>
  );
}

/** Overview's chart view: every test as a row of combined stats, opening into its versions. Sortable by any metric. */
function ChartTable({ experiments, onTest }) {
  const [sort, setSort] = useState({ key: "views", dir: "desc" });
  const [open, setOpen] = useState(() => new Set());
  const toggle = (id) => setOpen((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });
  const sortBy = (key) => setSort((current) => (current.key === key
    ? { key, dir: current.dir === "desc" ? "asc" : "desc" }
    : { key, dir: lowerIsBetter(key) ? "asc" : "desc" }));

  const rows = experiments.map((e) => ({ e, totals: totalsFor(e.variants) || {}, winner: winnerOf(e), r: rank(e.variants, e.primaryMetric || "views") }));
  const bestOf = (key, values) => {
    const present = values.filter((v) => v !== null && v !== undefined && !(lowerIsBetter(key) && v === 0));
    if (!present.length) return null;
    return lowerIsBetter(key) ? Math.min(...present) : Math.max(...present);
  };
  const columnBest = Object.fromEntries(CHART_KEYS.map((key) => [key, bestOf(key, rows.map((row) => row.totals[key]))]));
  const sorted = [...rows].sort((a, b) => byValue(a.totals[sort.key], b.totals[sort.key], sort.dir));
  const all = totalsFor(experiments.flatMap((e) => e.variants)) || {};
  const allOpen = open.size === experiments.length;

  return (
    <div className="mt-[30px]">
      <div className="mb-2 flex items-center justify-between gap-4">
        <p className="text-[12.5px] text-ink-3">Combined stats per test. Open a test to compare its versions; click a column to sort.</p>
        <button type="button" onClick={() => setOpen(allOpen ? new Set() : new Set(experiments.map((e) => e.id)))} className="shrink-0 text-[12.5px] text-ink-3 hover:text-ink">
          {allOpen ? "Collapse all" : "Expand all"}
        </button>
      </div>
      <div className="-mx-[18px] overflow-x-auto px-[18px] lg:mx-0 lg:px-0">
        <table className="w-full min-w-[1040px] border-collapse text-[13.5px]">
          <thead>
            <tr className="border-b border-line">
              <th className="sticky left-0 z-[2] bg-bg py-2 pl-2 pr-4 text-left text-[11.5px] font-medium text-ink-3">Test</th>
              {CHART_KEYS.map((key) => {
                const active = sort.key === key;
                return (
                  <th key={key} aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"} className="px-1 py-1.5 text-right">
                    <button type="button" onClick={() => sortBy(key)} className={`inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11.5px] font-medium hover:bg-hover hover:text-ink ${active ? "text-ink" : "text-ink-3"}`}>
                      {CHART_LABELS[key]}
                      <span aria-hidden="true" className={`text-[9px] ${active ? "" : "opacity-0"}`}>{active && sort.dir === "asc" ? "▲" : "▼"}</span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map(({ e, totals, winner, r }) => {
              const isOpen = open.has(e.id);
              const cover = winner || r.leader?.variant || e.variants[0];
              const versions = [...e.variants]
                .map((variant, index) => ({ variant, letter: letterFor(index) }))
                .sort((a, b) => byValue(metricValue(a.variant, sort.key), metricValue(b.variant, sort.key), sort.dir));
              const versionBest = Object.fromEntries(CHART_KEYS.map((key) => [key, rank(e.variants, key).best]));
              return (
                <Fragment key={e.id}>
                  <tr className={`group h-[52px] border-b border-line transition-colors hover:bg-[color-mix(in_oklch,var(--hover)_60%,transparent)] ${isOpen ? "bg-[color-mix(in_oklch,var(--hover)_45%,transparent)]" : ""}`}>
                    <th scope="row" className={`sticky left-0 z-[1] py-0 pl-1 pr-4 text-left font-normal group-hover:bg-[color-mix(in_oklch,var(--hover)_60%,var(--bg))] ${isOpen ? "bg-[color-mix(in_oklch,var(--hover)_45%,var(--bg))]" : "bg-bg"}`}>
                      <div className="flex items-center gap-2.5">
                        <button type="button" onClick={() => toggle(e.id)} aria-expanded={isOpen} aria-label={`${isOpen ? "Hide" : "Show"} versions of ${e.name}`} className="flex h-7 w-6 shrink-0 items-center justify-center rounded-md text-ink-3 hover:bg-hover-2 hover:text-ink">
                          <ChevronIcon className={`h-3.5 w-3.5 transition-transform duration-200 ease-std ${isOpen ? "rotate-90" : ""}`} />
                        </button>
                        <Thumb src={cover?.thumbnail} className="w-[22px] rounded-[4px]" />
                        <span className="min-w-0">
                          <button type="button" onClick={() => onTest(e.id)} className="block max-w-[230px] truncate text-left font-medium text-ink hover:underline hover:decoration-line hover:underline-offset-4">{e.name}</button>
                          <span className="block text-[11.5px] text-ink-3">
                            {plural(e.variants.length, "version")}
                            {winner && <span className="ml-1.5 align-[1px]"><Tag gold>🏆 {winner.label}</Tag></span>}
                          </span>
                        </span>
                      </div>
                    </th>
                    {CHART_KEYS.map((key) => (
                      <ChartCell key={key} metric={key} value={totals[key]} best={columnBest[key]} strong={totals[key] !== undefined && totals[key] === columnBest[key] && rows.length > 1} />
                    ))}
                  </tr>
                  {isOpen && versions.map(({ variant, letter }) => (
                    <tr key={variant.id} className="h-[44px] border-b border-line text-[13px]">
                      <th scope="row" className="sticky left-0 z-[1] bg-bg py-0 pl-[38px] pr-4 text-left font-normal">
                        <button type="button" onClick={() => onTest(e.id)} className="flex items-center gap-2 text-left hover:text-ink">
                          <Thumb src={variant.thumbnail} className="w-[18px] rounded-[3px]" />
                          <span className="text-[11.5px] font-medium text-ink-3">{letter}</span>
                          <span className="max-w-[180px] truncate text-ink-2">{variant.label}</span>
                          {winner?.id === variant.id && <span aria-label="Winner">🏆</span>}
                        </button>
                      </th>
                      {CHART_KEYS.map((key) => {
                        const value = metricValue(variant, key);
                        return <ChartCell key={key} bar="version" metric={key} value={value} best={versionBest[key]} strong={value !== null && value === versionBest[key] && e.variants.length > 1} />;
                      })}
                    </tr>
                  ))}
                </Fragment>
              );
            })}
          </tbody>
          {experiments.length > 1 && (
            <tfoot>
              <tr className="h-[48px] text-[13.5px]">
                <th scope="row" className="sticky left-0 z-[1] bg-bg py-0 pl-[38px] pr-4 text-left font-medium text-ink">All tests</th>
                {CHART_KEYS.map((key) => (
                  <td key={key} className="whitespace-nowrap px-2 text-right font-medium tabular-nums text-ink">{all[key] === null || all[key] === undefined ? "–" : formatMetric(key, all[key])}</td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

/** Every version of a test added up: counts are summed, averages and rates are weighted by views. */
function totalsFor(variants) {
  const measured = variants.filter((v) => v.analytics);
  if (!measured.length) return null;
  const sum = (key) => measured.reduce((total, v) => total + Number(v.analytics[key] || 0), 0);
  const views = sum("views");
  const weighted = (key) => {
    const rows = measured.filter((v) => Number(v.analytics[key]) > 0);
    const weight = rows.reduce((total, v) => total + Number(v.analytics.views || 0), 0);
    return weight ? rows.reduce((total, v) => total + Number(v.analytics[key]) * Number(v.analytics.views || 0), 0) / weight : null;
  };
  return {
    views,
    reach: sum("reach"),
    igReelsAvgWatchTime: weighted("igReelsAvgWatchTime"),
    igReelsVideoViewTotalTime: sum("igReelsVideoViewTotalTime"),
    reelsSkipRate: weighted("reelsSkipRate"),
    likes: sum("likes"),
    comments: sum("comments"),
    shares: sum("shares"),
    saves: sum("saves"),
    engagementRate: weighted("engagementRate"),
  };
}

const TOTAL_LABELS = {
  views: "views",
  reach: "reach",
  igReelsAvgWatchTime: "avg watch",
  igReelsVideoViewTotalTime: "watched",
  reelsSkipRate: "skip rate",
  likes: "likes",
  comments: "comments",
  shares: "shares",
  saves: "saves",
  engagementRate: "engagement",
};

function TestTotals({ variants }) {
  const totals = totalsFor(variants);
  if (!totals) return null;
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 rounded-card bg-canvas px-4 py-3 sm:grid-cols-5" aria-label="All versions combined">
      {Object.entries(TOTAL_LABELS).map(([key, label]) => (
        <div key={key} className="flex min-w-0 flex-col-reverse">
          <dt className="text-[11.5px] text-ink-3">{label}</dt>
          <dd className="truncate text-[14px] font-medium tabular-nums text-ink">{totals[key] === null ? "–" : formatMetric(key, totals[key])}</dd>
        </div>
      ))}
    </dl>
  );
}

/* Cards */

function VersionCard({ row, r, metric, on, onSelect, status, index, winnerId }) {
  const isLeader = r.leader?.variant.id === row.variant.id;
  const delta = row.value !== null && r.max > 0 && r.measured > 1 && !isLeader && !row.held ? Math.round(((row.value - r.max) / r.max) * 100) : null;
  return (
    <li className="card-in" style={{ animationDelay: `${staggerDelay(index)}ms` }}>
      <button
        type="button"
        onClick={onSelect}
        aria-current={on ? "page" : undefined}
        className={`relative z-[1] flex w-full gap-3 rounded-card px-3 pb-[11px] pt-3 text-left transition-colors ${on ? "" : "hover:bg-[color-mix(in_oklch,var(--hover)_55%,transparent)]"}`}
      >
        <Thumb src={row.variant.thumbnail} />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium leading-[1.3] tracking-[-0.012em] text-ink">{row.variant.label}</span>
            <span className="shrink-0 text-[13.5px] font-medium tabular-nums text-ink">{formatMetric(metric, row.value)}</span>
          </span>
          <span className="mt-1 flex items-baseline justify-between gap-2 text-[12.5px] text-ink-3">
            <span className="truncate">{whenLabel(status, row.variant.publishedAt)}</span>
            <span className="shrink-0 text-[11.5px]">{metricLabel(metric).toLowerCase()}</span>
          </span>
          <span className="mt-2 flex flex-wrap gap-[5px]">
            <Tag soft>Version {row.letter}</Tag>
            {winnerId === row.variant.id && <Tag gold>🏆 Winner</Tag>}
            {isLeader && winnerId !== row.variant.id && (winnerId ? <Tag>Leading</Tag> : <Tag accent>Leading</Tag>)}
            {delta !== null && <Tag>{signed(delta)} vs {r.leader.letter}</Tag>}
            {row.held && <Tag dashed>Held back</Tag>}
            {status === "scheduled" && (isDue(status, row.variant.publishedAt) ? <Tag dot="pulse-dot bg-ink-3">Posting</Tag> : <Tag dot="bg-ink-3">Scheduled</Tag>)}
            {status === "processing" && <Tag dot="pulse-dot bg-ink-3">Processing</Tag>}
            {status === "failed" && <Tag danger dot="bg-danger">Failed</Tag>}
            {row.value === null && !["scheduled", "processing", "failed"].includes(status) && <Tag dashed>No stats yet</Tag>}
          </span>
        </span>
      </button>
    </li>
  );
}

function DraftCard({ item, letter, on, onSelect, index, publishing, dragProps }) {
  const busy = item.status === "uploading" || item.status === "publishing";
  return (
    <li className="card-in" style={{ animationDelay: `${staggerDelay(index)}ms` }} onDragEnter={dragProps.onDragEnter} onDragOver={(e) => e.preventDefault()}>
      <button
        type="button"
        onClick={onSelect}
        draggable={!publishing}
        onDragStart={dragProps.onDragStart}
        onDragEnd={dragProps.onDragEnd}
        onKeyDown={(e) => {
          if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
            e.preventDefault();
            dragProps.onNudge(e.key === "ArrowUp" ? -1 : 1);
          }
        }}
        aria-current={on ? "page" : undefined}
        title="Drag to reorder"
        className={`relative z-[1] flex w-full gap-3 rounded-card px-3 pb-[11px] pt-3 text-left transition-colors ${on ? "" : "hover:bg-[color-mix(in_oklch,var(--hover)_55%,transparent)]"} ${dragProps.dragging ? "opacity-40" : ""}`}
      >
        <Thumb src={item.thumbnail}>
          {busy && (
            <span className="absolute inset-x-0 bottom-0 h-[3px] bg-black/40">
              <span className="block h-full origin-left bg-white transition-transform duration-200" style={{ transform: `scaleX(${item.status === "uploading" ? item.progress / 100 : 1})` }} />
            </span>
          )}
        </Thumb>
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13.5px] font-medium leading-[1.3] tracking-[-0.012em] text-ink">{item.name}</span>
            <span className="shrink-0 text-[11.5px] tabular-nums text-ink-3">{formatDuration(item.duration)}</span>
          </span>
          <span className={`mt-1 line-clamp-2 block text-[12.5px] leading-[1.45] ${item.status === "invalid" || item.status === "failed" ? "text-danger" : "text-ink-3"}`}>
            {item.status === "invalid" || item.status === "failed" ? item.error || item.errors?.[0] : "Not posted yet"}
          </span>
          <span className="mt-2 flex flex-wrap gap-[5px]">
            <Tag soft>Version {letter}</Tag>
            {item.status === "ready" && <Tag dot="bg-success">Ready</Tag>}
            {item.status === "checking" && <Tag dot="pulse-dot bg-ink-3">Checking</Tag>}
            {item.status === "uploading" && <Tag dot="pulse-dot bg-ink-3">Uploading {item.progress}%</Tag>}
            {item.status === "publishing" && <Tag dot="pulse-dot bg-ink-3">Sending</Tag>}
            {item.status === "invalid" && <Tag danger dot="bg-danger">Can't post</Tag>}
            {item.status === "failed" && <Tag danger dot="bg-danger">Failed</Tag>}
          </span>
        </span>
      </button>
    </li>
  );
}

function Dropzone({ onPick, dragging, compact = false, disabled }) {
  return (
    <button
      type="button"
      onClick={onPick}
      disabled={disabled}
      className={`mx-2.5 mt-1 flex w-[calc(100%-20px)] flex-col items-center justify-center gap-1.5 rounded-card border border-dashed text-center transition-colors disabled:opacity-50 ${
        dragging ? "border-ink-3 bg-hover" : "border-line-strong hover:bg-hover"
      } ${compact ? "py-4" : "py-12"}`}
    >
      {!compact && <UploadIcon className="mb-1 h-5 w-5 text-ink-3" />}
      <span className="text-[13.5px] font-medium text-ink">{compact ? "Add more versions" : "Drop videos here"}</span>
      <span className="text-[12.5px] text-ink-3">{compact ? "Drop them in or choose files" : "or choose files from your computer"}</span>
      {!compact && <span className="mt-2 px-6 text-[12px] leading-[1.5] text-ink-3">MP4 or MOV, vertical 9:16, 3 to 90 seconds. Up to 10 versions.</span>}
    </button>
  );
}

/* Detail views */

function Field({ label, aside, children }) {
  return (
    <div className="mt-8">
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <span className="text-[11.5px] font-medium text-ink-3">{label}</span>
        {aside}
      </div>
      {children}
    </div>
  );
}

function PublishCard({ t, count, metricFixed }) {
  const { account, publishing, canPublish, blocker, publish, draftItems } = t;
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (!canPublish) setConfirming(false);
  }, [canPublish]);
  const remaining = draftItems.filter((i) => i.status !== "failed").length;
  const noun = count === 1 ? "Trial Reel" : "Trial Reels";

  return (
    <div className="mt-[34px] rounded-card bg-bg px-[18px] py-4 shadow-resting">
      <h3 className="text-[13px] font-medium text-ink-2">{publishing ? "Publishing" : "Ready to post"}</h3>
      <p className="mt-2 text-[14px] leading-[1.55] text-ink-2">
        {publishing ? (
          <>Sending them one at a time, {WORDS[remaining] || remaining} to go. Keep this tab open.</>
        ) : (
          <>
            <b className="font-medium text-ink">{WORDS[count] ? WORDS[count][0].toUpperCase() + WORDS[count].slice(1) : count} {noun}</b> go to{" "}
            <b className="font-medium text-ink">{handleOf(account) || "your account"}</b>, one per version, same caption on each. Non-followers see them first, and you choose when to share each one with followers{metricFixed ? "." : ", from Instagram."}
            {count > 1 && <> They go out 3 to 7 minutes apart, at random, so Instagram doesn't flag them as duplicates.</>}
            {" "}Test before a reel goes to your feed: versions of something you've already posted get almost no reach.
          </>
        )}
      </p>
      {blocker && !publishing && <p className="mt-2 text-[13px] text-danger">{blocker}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-[13px]">
        {confirming ? (
          <>
            <span className="text-ink-2">{count > 1 ? "The first one goes live right away." : "It goes live right away."}</span>
            <button type="button" autoFocus onClick={() => { setConfirming(false); publish(); }} className={primaryButton}>Publish now</button>
            <button type="button" onClick={() => setConfirming(false)} className={textButton}>Cancel</button>
          </>
        ) : (
          <button type="button" disabled={!canPublish} onClick={() => setConfirming(true)} className={primaryButton}>
            {publishing ? "Publishing" : `Publish ${count} ${noun}`}
          </button>
        )}
      </div>
    </div>
  );
}

function Composer({ t, onHome }) {
  const { draft, draftItems, patchDraft, publishing } = t;
  const title = useRef(null);
  useEffect(() => {
    const el = title.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft.name]);
  const ready = draftItems.filter((i) => i.status === "ready").length || draftItems.length;

  return (
    <div className="detail-in mx-auto max-w-[760px] px-6 pb-24 pt-6 md:px-16 md:pt-[30px]">
      <textarea
        ref={title}
        rows={1}
        value={draft.name}
        onChange={(e) => patchDraft({ name: e.target.value.replace(/\s*\n\s*/g, " ") })}
        onKeyDown={(e) => e.key === "Enter" && e.preventDefault()}
        placeholder="Name this test"
        maxLength={100}
        disabled={publishing}
        aria-label="Test name"
        className="block w-full resize-none overflow-hidden bg-transparent font-display text-[30px] font-semibold leading-[1.12] tracking-[-0.035em] text-ink outline-none placeholder:text-ink-3 md:text-[32px]"
      />
      <input
        value={draft.hypothesis}
        onChange={(e) => patchDraft({ hypothesis: e.target.value })}
        placeholder="What do you think wins, and why?"
        maxLength={240}
        disabled={publishing}
        aria-label="Your guess"
        className="mt-2 block w-full bg-transparent text-[16px] leading-[1.6] text-ink-2 outline-none placeholder:text-ink-3 md:text-[17px]"
      />

      <Field label="Winner by">
        <SegmentedControl label="Winner by" options={RANK_OPTIONS} value={draft.metric} onChange={(v) => patchDraft({ metric: v })} disabled={publishing} className="max-w-[440px]" />
      </Field>

      <Field label="Caption" aside={<span className={`text-[12px] tabular-nums ${draft.caption.length > MAX_CAPTION ? "text-danger" : "text-ink-3"}`}>{n(draft.caption.length)} / {n(MAX_CAPTION)}</span>}>
        <textarea
          value={draft.caption}
          onChange={(e) => patchDraft({ caption: e.target.value })}
          placeholder="One caption for every version, so the hook is the only thing that changes."
          disabled={publishing}
          rows={4}
          aria-label="Caption"
          className="caption-field block min-h-[132px] w-full resize-y rounded-card bg-bg px-4 py-3 text-ink shadow-resting outline-none transition-shadow placeholder:text-ink-3 focus:shadow-raised"
        />
      </Field>

      <PublishCard t={t} count={ready} />
      <DeleteDraft t={t} onDone={onHome} />
    </div>
  );
}

/** Throws away an unpublished test. Only local work is lost, so the confirm says that. */
function DeleteDraft({ t, onDone }) {
  const [open, setOpen] = useState(false);
  const { draft, draftItems, publishing } = t;
  if (publishing) return null;
  const name = draft.name.trim() || "this draft";
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="mt-8 inline-flex min-h-11 items-center gap-1.5 text-[13px] text-ink-3 hover:text-danger lg:min-h-0">
        <TrashIcon className="h-3.5 w-3.5" />
        Delete draft
      </button>
      <ConfirmDialog open={open} title={`Delete ${name}?`} confirmLabel="Delete draft" onConfirm={() => { setOpen(false); t.deleteDraft(); onDone(); }} onClose={() => setOpen(false)}>
        <p>
          {draftItems.length ? `This clears the ${plural(draftItems.length, "version")}, name and caption from Trials.` : "This clears the name and caption from Trials."} Nothing has been posted, and the video files stay on your computer.
        </p>
      </ConfirmDialog>
    </>
  );
}

/** The caption every version went out with. Long ones fold to four lines. */
function CaptionBlock({ caption }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const long = caption.length > 260 || caption.split("\n").length > 5;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(caption);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };
  return (
    <figure className="mt-6">
      <div className="mb-1.5 flex items-baseline justify-between gap-4">
        <figcaption className="text-[11.5px] font-medium text-ink-3">Caption, same on every version</figcaption>
        <button type="button" onClick={copy} className="text-[12px] text-ink-3 hover:text-ink" aria-live="polite">{copied ? "Copied" : "Copy"}</button>
      </div>
      <div className="rounded-card bg-canvas px-4 py-3">
        <p className={`caption-field whitespace-pre-line text-ink ${long && !open ? "line-clamp-4" : ""}`}>{caption}</p>
        {long && (
          <button type="button" onClick={() => setOpen((v) => !v)} className="mt-1 text-[12.5px] text-ink-3 hover:text-ink">{open ? "Show less" : "Show all"}</button>
        )}
      </div>
    </figure>
  );
}

/** Deletes a test or a version from Trials, after saying plainly that Instagram keeps the posts. */
function DeleteControl({ kind, name, versions = 0, isWinner = false, onDelete, className = "" }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const isTest = kind === "test";
  const label = isTest ? "Delete test" : "Delete version";
  const confirm = async () => {
    setBusy(true);
    const ok = await onDelete();
    setBusy(false);
    if (ok) setOpen(false);
  };
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={`inline-flex min-h-11 items-center gap-1.5 text-[13px] text-ink-3 hover:text-danger lg:min-h-0 ${className}`}>
        <TrashIcon className="h-3.5 w-3.5" />
        {label}
      </button>
      <ConfirmDialog open={open} title={`Delete ${name}?`} confirmLabel={label} busy={busy} onConfirm={confirm} onClose={() => setOpen(false)}>
        <p>
          {isTest
            ? `This removes the test${versions ? `, its ${plural(versions, "version")}` : ""} and their stats from Trials.`
            : `This removes the version and its stats from this test.${isWinner ? " It's your winner, so the test goes back to undecided." : ""}`}
        </p>
        <p className="rounded-card bg-hover px-3.5 py-3">
          <b className="font-medium text-ink">This won't delete {isTest && versions !== 1 ? "the posts" : "the post"} from Instagram.</b>{" "}
          {isTest && versions !== 1 ? "Your trial reels stay up. To take them down, delete them in the Instagram app." : "The trial reel stays up. To take it down, delete it in the Instagram app."}
        </p>
      </ConfirmDialog>
    </>
  );
}

/** Pick a winner from the summary (the leader is the suggestion), or undo the pick. */
function WinnerActions({ t, experiment, winner, suggestion }) {
  const url = winner && (t.liveStatus[winner.id]?.url || winner.platformPostUrl);
  if (winner) {
    return (
      <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
        {url && (
          <a href={url} target="_blank" rel="noreferrer" className={outlineButton}>
            <ExternalIcon className="h-3.5 w-3.5" />
            Open {winner.label} in Instagram
          </a>
        )}
        <button type="button" onClick={() => t.pickWinner(experiment.id, null)} className={textButton}>Undo winner</button>
      </div>
    );
  }
  if (!suggestion) return null;
  return (
    <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-2">
      <button type="button" onClick={() => t.pickWinner(experiment.id, suggestion.id)} className={primaryButton}>
        <TrophyIcon className="h-3.5 w-3.5" />
        Pick {suggestion.label} as winner
      </button>
      <span className="text-[12.5px] text-ink-3">Or open any version to pick it instead.</span>
    </div>
  );
}

/** Shown when posted versions are stuck near zero views: Instagram has most likely flagged them as duplicates. */
function HeldBackAlert({ held, all, total, top }) {
  const names = held.map((v) => v.label);
  const who = all ? (total === 1 ? "This version has" : `All ${WORDS[total] || total} versions have`) : `${names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`} ${names.length === 1 ? "has" : "have"}`;
  return (
    <div role="status" className="mb-7 rounded-card bg-hover px-4 py-3.5 text-[14px] leading-[1.6] text-ink-2">
      <p className="font-medium text-ink">Instagram is likely holding {all ? (total === 1 ? "this" : "these") : names.length === 1 ? "one" : "some"} back</p>
      <p className="mt-1">
        {who} fewer than {HELD_UNDER_VIEWS} views{top ? <>, while {top.label} has {formatMetric("views", top.analytics.views)}</> : <> after more than {HELD_AFTER_HOURS} hours</>}. That usually means Instagram decided {names.length === 1 && !all ? "it looks" : "they look"} like a reel you've already posted, so it isn't showing {names.length === 1 && !all ? "it" : "them"} to anyone. Check your Instagram notifications for this:
      </p>
      <p className="mt-2 border-l-2 border-line-strong pl-3 text-ink">Your trial reel won't get much reach because it looks like something you shared before.</p>
    </div>
  );
}

function TestSummary({ t, experiment, metric, onSelect, onHome, now }) {
  const held = heldBack(experiment.variants, now);
  const live = experiment.variants.filter((v) => v.status === "published");
  const allHeld = held.length > 0 && held.length === live.length;
  // The version that took off, when that's what gave the others away.
  const top = held.length && !allHeld ? live.filter((v) => !held.includes(v)).sort((a, b) => Number(b.analytics?.views || 0) - Number(a.analytics?.views || 0))[0] : null;

  const r = rank(experiment.variants, metric, held);
  const lead = leadBy(r, metric);
  const winner = winnerOf(experiment);
  const started = firstPost(experiment.variants);
  const hours = hoursSince(started, now);
  const unit = metricLabel(metric).toLowerCase();

  let headline = "Waiting on stats.";
  if (allHeld && !winner) headline = "Too few views to compare.";
  else if (winner) headline = `${winner.label} won.`;
  else if (r.leader) headline = `${r.leader.variant.label} is winning.`;
  else if (r.lone) headline = `Only ${r.lone.variant.label} is getting reach.`;
  else if (r.measured === 1) headline = "One version in. Too early to call.";
  else if (!experiment.variants.length) headline = "Nothing posted yet.";

  let advice;
  if (winner) advice = <>Share <b className="font-medium text-ink">{winner.label}</b> with your followers: open it in Instagram and choose to share the trial. The other versions stay as trials, seen only by non-followers.</>;
  else if (allHeld) advice = "Trial reels only get reach when they don't look like something already on your feed. Test new edits before the reel goes to your feed, not after.";
  else if (r.lone) advice = "Instagram only showed one version, so this test can't tell you which edit works. The others most likely look like something you've already posted, on your feed or in another test.";
  else if (!experiment.variants.length) advice = "Add the versions you want to compare, then publish them together so they get the same amount of time.";
  else if (hours < 24) advice = `Compare after the same 24 hours. Check back in ${plural(Math.ceil(24 - hours), "hour")}; early numbers swing.`;
  else if (r.leader && r.margin >= 10) advice = `${r.leader.variant.label} is ${lead.percent ? `${lead.text} ahead` : `ahead, ${lead.text} ${unit}`}. Open it in Instagram and share it with your followers. The others can stay as trials.`;
  else if (r.leader) advice = `It's close: ${r.margin}% between first and second. Give it another day, or call it on a second metric below.`;
  else advice = "Instagram can take an hour or two to report numbers. Refresh later.";

  return (
    <div className="detail-in mx-auto max-w-[720px] px-6 pb-24 pt-6 md:px-12 md:pt-[22px]">
      {held.length > 0 && <HeldBackAlert held={held} all={allHeld} total={live.length} top={top && Number(top.analytics?.views || 0) >= BREAKOUT_VIEWS ? top : null} />}
      <h1 className="font-display text-[30px] font-semibold leading-[1.15] tracking-[-0.035em] text-ink md:text-[36px]">{headline}</h1>
      <p className="mt-3 text-[16px] leading-[1.6] text-ink-2 md:text-[17px]">
        {winner ? (
          <>
            You picked it {timeAgo(experiment.decidedAt, now)}
            {(() => {
              const row = r.rows.find((x) => x.variant.id === winner.id);
              return row?.value !== null && row?.value !== undefined ? <>, with <b className="font-medium text-ink">{formatMetric(metric, row.value)} {metric === "igReelsAvgWatchTime" ? "average watch time" : unit}</b></> : null;
            })()}
            {r.leader && r.leader.variant.id !== winner.id && <>. {r.leader.variant.label} leads on {unit}</>}.
          </>
        ) : allHeld ? (
          <>The gaps between versions are a view or two, so they don't tell you which one works. Check the alert above before you post these again.</>
        ) : r.lone ? (
          <>
            It has <b className="font-medium text-ink">{formatMetric(metric, r.lone.value)} {metric === "igReelsAvgWatchTime" ? "average watch time" : unit}</b>
            {started && <>, <b className="font-medium text-ink">{span(started, now)}</b> in</>}. Instagram is holding the others back, so there's nothing to compare it to.
          </>
        ) : r.leader ? (
          <>
            It has <b className="font-medium text-ink">{formatMetric(metric, r.leader.value)} {metric === "igReelsAvgWatchTime" ? "average watch time" : unit}</b>
            {lead && (lead.percent ? <>, <b className="font-medium text-ink">{lead.text} more</b> than {r.runnerUp.variant.label}</> : <>, against <b className="font-medium text-ink">{formatMetric(metric, r.runnerUp.value)}</b> for {r.runnerUp.variant.label}</>)}
            {started && <>, <b className="font-medium text-ink">{span(started, now)}</b> in</>}.
          </>
        ) : (
          <>{plural(experiment.variants.length, "version")} posted{started ? `, ${span(started, now)} ago` : ""}. Winner by {unit}.</>
        )}
      </p>

      <WinnerActions t={t} experiment={experiment} winner={winner} suggestion={allHeld ? null : (r.leader || r.lone)?.variant} />

      {experiment.hypothesis && (
        <figure className="mt-6">
          <figcaption className="mb-1.5 text-[11.5px] font-medium text-ink-3">Your guess</figcaption>
          <blockquote className="border-l-2 border-line pl-4 font-serif text-[16.5px] leading-[1.68] text-ink-2">{experiment.hypothesis}</blockquote>
        </figure>
      )}

      {experiment.caption && <CaptionBlock caption={experiment.caption} />}

      {r.measured > 0 && (
        <div className="mt-[30px]">
          <h3 className="text-[13px] font-medium text-ink-2">Every metric</h3>
          <div className="wide-table mt-2 overflow-x-auto">
            <table className="w-full border-collapse text-[14px] tabular-nums">
              <thead>
                <tr className="border-b border-line">
                  <th className="pb-3 pl-3 pr-4 text-left align-bottom text-[11.5px] font-medium text-ink-3">Metric</th>
                  {r.rows.map((row) => (
                    <th key={row.variant.id} className="px-3 pb-3 pt-1 text-right align-bottom">
                      <button type="button" onClick={() => onSelect(row.variant.id)} title={`Open ${row.variant.label}`} className="group -mr-1.5 inline-flex flex-col items-end gap-2 rounded-card p-1.5 text-right hover:bg-hover">
                        <Thumb src={row.variant.thumbnail} className={`w-[64px] transition-transform duration-200 ease-std group-hover:scale-[1.03] ${(winner?.id || r.leader?.variant.id) === row.variant.id ? "ring-2 ring-ink ring-offset-2 ring-offset-bg" : ""}`} />
                        <span className="max-w-[96px] leading-[1.25]">
                          <span className="block text-[12.5px] font-medium text-ink">{row.letter}</span>
                          <span className="block truncate text-[11.5px] font-normal text-ink-3">{row.variant.label}</span>
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRICS.map(({ key, label }) => {
                  const mr = rank(experiment.variants, key);
                  return (
                    <tr key={key} className={`border-b border-line ${key === metric ? "bg-hover" : ""}`}>
                      <td className={`whitespace-nowrap py-2.5 pl-3 pr-4 ${key === metric ? "font-medium text-ink" : "text-ink-2"}`}>
                        {label}
                        {lowerIsBetter(key) && <span className="ml-1.5 text-[12px] font-normal text-ink-3">lower wins</span>}
                        {key === experiment.primaryMetric && <span className="ml-2 align-[1px]"><Tag>Goal</Tag></span>}
                      </td>
                      {mr.rows.map((row) => {
                        const best = row.value !== null && mr.measured > 1 && row.value === mr.best;
                        const delta = mr.measured > 1 ? gap(key, row.value, mr.best) : "";
                        return (
                          <td key={row.variant.id} className="whitespace-nowrap px-3 py-2.5 text-right">
                            <span className={best ? "font-medium text-ink" : "text-ink-2"}>{formatMetric(key, row.value)}</span>
                            <span className="ml-1.5 inline-block min-w-[4.6em] text-left text-[11.5px] text-ink-3">{delta}</span>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-[34px] rounded-card bg-bg px-[18px] py-4 shadow-resting">
        <h3 className="text-[13px] font-medium text-ink-2">What to do next</h3>
        <p className="mt-2 text-[14px] leading-[1.55] text-ink-2">{advice}</p>
      </div>

      {t.draftItems.length > 0 && <PublishCard t={t} count={t.draftItems.filter((i) => i.status === "ready").length || t.draftItems.length} metricFixed />}

      <DeleteControl
        kind="test"
        name={experiment.name}
        versions={experiment.variants.length}
        onDelete={async () => {
          const ok = await t.deleteTest(experiment.id);
          if (ok) onHome();
          return ok;
        }}
        className="mt-10"
      />
    </div>
  );
}

/** The test's name in the list header, edited in place like a version name. */
function TestName({ name, onRename }) {
  const [value, setValue] = useState(name);
  const ref = useRef(null);
  useEffect(() => setValue(name), [name]);
  const commit = () => {
    const next = value.replace(/\s+/g, " ").trim();
    if (!next) setValue(name);
    else if (next !== name) onRename(next);
  };
  return (
    <input
      ref={ref}
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        else if (e.key === "Escape") {
          setValue(name);
          requestAnimationFrame(() => ref.current?.blur());
        }
      }}
      onBlur={commit}
      maxLength={100}
      spellCheck={false}
      aria-label="Test name"
      title="Click to rename"
      className="-mx-1.5 -my-0.5 block w-[calc(100%+12px)] truncate rounded-control bg-transparent px-1.5 py-0.5 font-display text-[19px] font-semibold leading-[1.15] tracking-[-0.03em] text-ink outline-none transition-colors hover:bg-hover focus:bg-hover"
    />
  );
}

/** A version's name, edited in place. Enter or click away saves, Escape puts it back. */
function VersionTitle({ label, onRename }) {
  const [value, setValue] = useState(label);
  const ref = useRef(null);
  useEffect(() => setValue(label), [label]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  const commit = () => {
    const next = value.replace(/\s+/g, " ").trim();
    if (!next) setValue(label);
    else if (next !== label) onRename(next);
  };
  return (
    <textarea
      ref={ref}
      rows={1}
      value={value}
      onChange={(e) => setValue(e.target.value.replace(/\s*\n\s*/g, " "))}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          e.currentTarget.blur();
        } else if (e.key === "Escape") {
          setValue(label);
          requestAnimationFrame(() => ref.current?.blur());
        }
      }}
      onBlur={commit}
      maxLength={120}
      spellCheck={false}
      aria-label="Version name"
      title="Click to rename"
      className="-mx-2 block w-[calc(100%+16px)] resize-none overflow-hidden rounded-control bg-transparent px-2 py-0.5 font-display text-[30px] font-semibold leading-[1.12] tracking-[-0.035em] text-ink outline-none transition-colors hover:bg-hover focus:bg-hover md:text-[32px]"
    />
  );
}

function VersionDetail({ variant, letter, experiment, url, status, onRename, onPickWinner, onDelete }) {
  const isWinner = experiment.winnerId === variant.id;
  const total = experiment.variants.length;
  return (
    <div className="detail-in mx-auto max-w-[760px] px-6 pb-24 pt-6 md:px-16 md:pt-[30px]">
      <div className="flex flex-col gap-8 sm:flex-row">
        <div className="w-full max-w-[260px] shrink-0">
          <Player src={variant.mediaUrl} poster={variant.thumbnail} label={variant.label} />
          <div className="mt-3 flex flex-col gap-2">
            {isWinner ? (
              <div className="flex h-11 items-center justify-center gap-1.5 rounded-md bg-gold text-[13px] font-medium text-gold-ink lg:h-8">
                🏆 The winner
              </div>
            ) : (
              <button type="button" onClick={() => onPickWinner(variant.id)} className={`${primaryButton} w-full`}>
                <TrophyIcon className="h-3.5 w-3.5" />
                {experiment.winnerId ? "Make this the winner" : "Pick as winner"}
              </button>
            )}
            {url && (
              <a href={url} target="_blank" rel="noreferrer" className={`${outlineButton} w-full justify-center`}>
                <ExternalIcon className="h-3.5 w-3.5" />
                Open in Instagram
              </a>
            )}
            {isWinner && (
              <button type="button" onClick={() => onPickWinner(null)} className={`${textButton} justify-center`}>Undo winner</button>
            )}
            <DeleteControl kind="version" name={variant.label} isWinner={isWinner} onDelete={onDelete} className="justify-center" />
          </div>
        </div>
        <div className="min-w-0 flex-1">
          <VersionTitle label={variant.label} onRename={onRename} />
          <p className="mt-2 text-[13px] text-ink-3">
            {whenLabel(status, variant.publishedAt)}{variant.originalFilename ? `, from ${variant.originalFilename}` : ""}
          </p>
          <div className="mt-3 flex flex-wrap gap-[5px]">
            <Tag soft>Version {letter}</Tag>
            {isWinner && <Tag gold>🏆 Winner</Tag>}
            {status === "scheduled" && (isDue(status, variant.publishedAt) ? <Tag dot="pulse-dot bg-ink-3">Posting</Tag> : <Tag dot="bg-ink-3">Scheduled</Tag>)}
            {status === "processing" && <Tag dot="pulse-dot bg-ink-3">Processing</Tag>}
            {status === "failed" && <Tag danger dot="bg-danger">Failed</Tag>}
            {status === "published" && <Tag dot="bg-success">Live as a Trial Reel</Tag>}
          </div>

          <dl className="mt-6">
            {METRICS.map(({ key, label }) => {
              const mr = rank(experiment.variants, key);
              const value = metricValue(variant, key);
              // Ties share a place.
              const place = value === null ? -1 : mr.sorted.filter((row) => row.value !== null && (lowerIsBetter(key) ? row.value < value : row.value > value)).length;
              const fill = !value || !mr.best ? 0 : lowerIsBetter(key) ? mr.best / value : value / mr.max;
              return (
                <div key={key} className="grid grid-cols-[1fr_auto] items-baseline gap-x-4 border-b border-line py-2.5">
                  <dt className="text-[14px] text-ink-2">{label}{lowerIsBetter(key) && <span className="ml-1.5 text-[12px] text-ink-3">lower wins</span>}</dt>
                  <dd className="flex items-baseline gap-2 text-[14px] tabular-nums">
                    <span className="font-medium text-ink">{formatMetric(key, value)}</span>
                    <span className="w-[62px] text-right text-[12px] text-ink-3">{value !== null && mr.measured > 1 ? `${ordinal(place)} of ${total}` : ""}</span>
                  </dd>
                  <span aria-hidden="true" className="col-span-2 mt-2 block h-1 overflow-hidden rounded-full bg-hover-2">
                    <span className={`block h-full origin-left rounded-full ${place === 0 && mr.measured > 1 ? "bg-lead" : "bg-line-strong"}`} style={{ transform: `scaleX(${fill})` }} />
                  </span>
                </div>
              );
            })}
          </dl>

        </div>
      </div>
    </div>
  );
}

function DraftItemDetail({ t, item, letter }) {
  const { patchItem, removeItem, publish, publishing } = t;
  const error = item.error || item.errors?.[0];
  return (
    <div className="detail-in mx-auto max-w-[760px] px-6 pb-24 pt-6 md:px-16 md:pt-[30px]">
      <div className="flex flex-col gap-8 sm:flex-row">
        <div className="w-full max-w-[260px] shrink-0">
          <Player src={item.objectUrl} poster={item.thumbnail} label={item.name} />
        </div>
        <div className="group min-w-0 flex-1">
          <input
            value={item.name}
            onChange={(e) => patchItem(item.id, { name: e.target.value })}
            onBlur={(e) => !e.target.value.trim() && patchItem(item.id, { name: `Version ${letter}` })}
            maxLength={120}
            disabled={publishing}
            aria-label="Version name"
            className="-mx-1 w-[calc(100%+8px)] rounded-md bg-transparent px-1 font-display text-[30px] font-semibold leading-[1.12] tracking-[-0.035em] text-ink outline-none placeholder:text-ink-3 hover:bg-hover focus:bg-bg md:text-[32px]"
          />
          <p className="mt-2 text-[13px] text-ink-3">
            Version {letter}
            {formatDuration(item.duration) && `, ${formatDuration(item.duration)}`}
            {item.size ? `, ${(item.size / 1024 / 1024).toFixed(1)} MB` : ""}
            {item.file?.name ? `, ${item.file.name}` : ""}
          </p>
          {error && (item.status === "invalid" || item.status === "failed") && <p role="alert" className="mt-3 text-[13px] text-danger">{error}</p>}
          <p className="mt-6 text-[14px] leading-[1.6] text-ink-2">
            Name each version after the thing that's different about it, like the hook or the first line. That name is what you'll compare later.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px]">
            {item.status === "failed" && !publishing && (
              <button type="button" onClick={() => publish(item)} className={quietButton}>
                <RefreshIcon className="h-3.5 w-3.5" />
                Retry
              </button>
            )}
            {!publishing && (
              <button type="button" onClick={() => removeItem(item.id)} className="flex min-h-11 items-center gap-1.5 text-ink-3 hover:text-danger lg:min-h-0">
                <TrashIcon className="h-3.5 w-3.5" />
                Remove version
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* Test page: list column + detail column */

function TestPage({ t, onMenu, onPick, onHome, fileDrag, now }) {
  const { experiment, draft, draftItems, liveStatus, refreshingId, refreshStats, publishing, moveItem, nudgeItem, selectedId } = t;
  const isNew = !experiment;
  const [selection, setSelection] = useState(null);
  const [metric, setMetric] = useState(experiment?.primaryMetric || "views");
  const [dragId, setDragId] = useState("");

  const variants = experiment?.variants || [];
  const r = rank(variants, metric, heldBack(variants, now));
  const statusOf = (v) => liveStatus[v.id]?.status || (isPublished(v.status) ? "published" : v.status);
  const selectedVariant = variants.find((v) => v.id === selection);
  const selectedItem = draftItems.find((i) => i.id === selection);
  const showDetail = Boolean(selectedVariant || selectedItem || selection === "summary");
  const testName = isNew ? draft.name.trim() || "New test" : experiment.name;
  const totalViews = variants.reduce((s, v) => s + Number(v.analytics?.views || 0), 0);
  const lastRefresh = variants.reduce((latest, v) => (v.lastRefreshedAt > latest ? v.lastRefreshedAt : latest), "");
  const remaining = MAX_FILES - variants.length - draftItems.length;
  const toSummary = () => setSelection(null);

  useEffect(() => {
    if (selection && selection !== "summary" && !selectedVariant && !selectedItem) setSelection(null);
  }, [selection, selectedVariant, selectedItem]);

  const statusRight = isNew ? (
    publishing ? <StatusPill tone="busy">Publishing</StatusPill> : draftItems.some((i) => i.status === "checking") ? <StatusPill tone="busy">Checking videos</StatusPill> : draftItems.length ? <StatusPill tone={t.blocker ? "idle" : "ok"}>{t.blocker ? "Not ready" : `${plural(draftItems.length, "version")} ready`}</StatusPill> : null
  ) : (
    <>
      {variants.length > 0 && (
        <StatusPill tone={refreshingId === experiment.id ? "busy" : lastRefresh ? "ok" : "idle"}>
          {refreshingId === experiment.id ? "Refreshing" : lastRefresh ? `Updated ${timeAgo(lastRefresh, now)}` : "No stats yet"}
        </StatusPill>
      )}
      {variants.length > 0 && (
        <button type="button" onClick={() => refreshStats(experiment.id)} disabled={refreshingId === experiment.id} className="flex h-[30px] items-center gap-1.5 rounded-control px-2.5 text-[12.5px] font-medium text-ink-2 hover:bg-hover hover:text-ink disabled:opacity-50">
          <RefreshIcon className={`h-4 w-4 ${refreshingId === experiment.id ? "animate-spin" : ""}`} />
          Refresh
        </button>
      )}
    </>
  );

  const crumbs = [{ label: testName, onClick: selection && selection !== "summary" ? toSummary : undefined }];
  if (selectedVariant) crumbs.push({ label: selectedVariant.label });
  if (selectedItem) crumbs.push({ label: selectedItem.name });

  let detail;
  if (selectedVariant) {
    detail = <VersionDetail key={selectedVariant.id} variant={selectedVariant} letter={letterFor(variants.indexOf(selectedVariant))} experiment={experiment} url={liveStatus[selectedVariant.id]?.url || selectedVariant.platformPostUrl} status={statusOf(selectedVariant)} onRename={(label) => t.renameVersion(experiment.id, selectedVariant.id, label)} onPickWinner={(id) => t.pickWinner(experiment.id, id)} onDelete={() => t.deleteVersion(experiment.id, selectedVariant.id)} />;
  } else if (selectedItem) {
    detail = <DraftItemDetail key={selectedItem.id} t={t} item={selectedItem} letter={letterFor(variants.length + draftItems.indexOf(selectedItem))} />;
  } else if (isNew && draftItems.length === 0) {
    detail = null;
  } else if (isNew) {
    detail = <Composer t={t} onHome={onHome} />;
  } else {
    detail = <TestSummary t={t} experiment={experiment} metric={metric} onSelect={setSelection} onHome={onHome} now={now} />;
  }

  return (
    <div className="flex h-dvh">
      <section className={`pane-list ${showDetail ? "has-detail" : ""}`} aria-label={`${testName} versions`}>
        <MobileBar onMenu={onMenu} />
        <div className="px-[18px] pb-3 pt-[18px]">
          <div className="flex items-start gap-2.5">
            <div className="min-w-0 flex-1">
              {isNew ? (
                <h1 className={`truncate font-display text-[19px] font-semibold leading-[1.15] tracking-[-0.03em] ${draft.name.trim() ? "text-ink" : "text-ink-3"}`}>{testName}</h1>
              ) : (
                <h1><TestName key={experiment.id} name={experiment.name} onRename={(name) => t.renameTest(experiment.id, name)} /></h1>
              )}
              <p className="mt-1 text-[12.5px] text-ink-3">
                {isNew
                  ? draftItems.length ? `${plural(draftItems.length, "version")} to post` : "Add the versions you want to compare"
                  : `${plural(variants.length, "version")} · ${plural(totalViews, "view")}`}
              </p>
            </div>
            {(variants.length > 0 || draftItems.length > 0) && remaining > 0 && (
              <button type="button" onClick={onPick} disabled={publishing} aria-label="Add a version" className={outlineButton}>
                <PlusIcon className="h-3.5 w-3.5" />
                Version
              </button>
            )}
          </div>
          {!isNew || draftItems.length ? (
            <button type="button" onClick={() => setSelection("summary")} className="mt-3 text-[13px] text-ink-2 underline decoration-line underline-offset-4 lg:hidden">
              {isNew ? "Name it and publish" : "See how it's going"}
            </button>
          ) : null}
        </div>

        {variants.length > 1 && (
          <div className="px-[18px] pb-2.5">
            <SegmentedControl label="Rank versions by" options={RANK_OPTIONS} value={metric} onChange={setMetric} />
          </div>
        )}

        {isNew && draftItems.length === 0 ? (
          <Dropzone onPick={onPick} dragging={fileDrag} />
        ) : (
          <SlidingHighlight highlightClassName="rounded-card bg-hover">
            <ul className="flex flex-col gap-1 px-2.5 pb-3 pt-1">
              {variants.length > 0 && (
                <li>
                  {draftItems.length > 0 && <h2 className="px-3 pb-1.5 pt-2.5 text-[11.5px] font-medium text-ink-3">Posted</h2>}
                  <ul className="flex flex-col gap-0.5">
                    {r.sorted.map((row, i) => (
                      <VersionCard key={row.variant.id} row={row} r={r} metric={metric} index={i} on={selection === row.variant.id} onSelect={() => setSelection(row.variant.id)} status={statusOf(row.variant)} winnerId={experiment?.winnerId} />
                    ))}
                  </ul>
                </li>
              )}
              {draftItems.length > 0 && (
                <li>
                  <h2 className="px-3 pb-1.5 pt-2.5 text-[11.5px] font-medium text-ink-3">{variants.length ? "Not posted yet" : "Versions"}</h2>
                  <ul className="flex flex-col gap-0.5">
                    {draftItems.map((item, i) => (
                      <DraftCard
                        key={item.id}
                        item={item}
                        index={variants.length + i}
                        letter={letterFor(variants.length + i)}
                        on={selection === item.id}
                        onSelect={() => setSelection(item.id)}
                        publishing={publishing}
                        dragProps={{
                          dragging: dragId === item.id,
                          onDragStart: (e) => { setDragId(item.id); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", item.id); },
                          onDragEnter: () => dragId && dragId !== item.id && moveItem(dragId, item.id),
                          onDragEnd: () => setDragId(""),
                          onNudge: (dir) => nudgeItem(item.id, dir),
                        }}
                      />
                    ))}
                  </ul>
                </li>
              )}
            </ul>
          </SlidingHighlight>
        )}
        {draftItems.length > 0 && remaining > 0 && !publishing && (
          <div className="pb-6"><Dropzone onPick={onPick} dragging={fileDrag} compact /></div>
        )}
      </section>
      <ResizeHandle />
      {detail ? (
        <Detail
          key={`${selectedId}:${selection || "root"}`}
          mobileBar={<MobileBar until="lg" back={{ label: testName, onClick: () => setSelection(null) }} />}
          bar={(scrolled) => <DetailBar scrolled={scrolled} crumbs={crumbs} right={statusRight} />}
        >
          {detail}
        </Detail>
      ) : (
        <section className="pane-detail pane-empty flex items-center justify-center">
          <div className="detail-in max-w-[340px] px-6 text-center">
            <p className="font-display text-[19px] font-semibold tracking-[-0.03em] text-ink">Post every version. Let the numbers pick.</p>
            <p className="mt-2 text-[14px] leading-[1.55] text-ink-3">Each version goes out as its own Trial Reel to people who don't follow you yet, and Trials keeps score.</p>
            <button type="button" onClick={onPick} className={`${primaryButton} mt-5`}>Choose videos</button>
            <div className="mt-10 text-left">
              <p className="text-[11.5px] font-medium text-ink-3">How it works</p>
              <ol className="mt-2 space-y-0.5">
                {["Add two or more versions of your reel", "Name the test and pick the metric you're tracking", "Write the caption that goes on every trial reel", "Publish, then compare them after 24 hours"].map((step, i) => (
                  <li key={step} className="flex items-baseline gap-3 rounded-control px-2 py-2 text-[14px] text-ink-2">
                    <span className="w-3 shrink-0 text-[12px] tabular-nums text-ink-3">{i + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
            {isNew && (draft.name.trim() || draft.hypothesis.trim() || draft.caption.trim()) && <DeleteDraft t={t} onDone={onHome} />}
          </div>
        </section>
      )}
    </div>
  );
}

/** The Zernio key box: checked with Zernio before it's saved, so a typo never replaces a key that works. */
function KeyForm({ onSave, onDone, autoFocus = false, note, label = "Connect" }) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!key.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      await onSave(key.trim());
      setKey("");
      setBusy(false);
      onDone?.();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <label htmlFor="zernio-key" className="mb-1.5 block text-[11.5px] font-medium text-ink-3">Zernio API key</label>
      <div className="flex gap-2">
        <input
          id="zernio-key"
          type="password"
          value={key}
          onChange={(e) => { setKey(e.target.value); setError(""); }}
          placeholder="Paste your key"
          autoComplete="off"
          spellCheck={false}
          autoFocus={autoFocus}
          disabled={busy}
          aria-invalid={Boolean(error)}
          aria-describedby="zernio-key-note"
          className="h-10 min-w-0 flex-1 rounded-control bg-hover px-3 font-mono text-[13px] text-ink outline-none placeholder:font-sans placeholder:text-ink-3 focus-visible:ring-2 focus-visible:ring-focus"
        />
        <button
          type="submit"
          disabled={!key.trim() || busy}
          className="h-10 shrink-0 rounded-control bg-accent px-4 text-[13.5px] font-medium text-accent-ink transition-[opacity,transform] hover:opacity-90 active:scale-[.98] disabled:opacity-50"
        >
          {busy ? "Checking" : label}
        </button>
      </div>
      <p id="zernio-key-note" role={error ? "alert" : undefined} className={`mt-2 text-[13px] leading-[1.5] ${error ? "text-danger" : "text-ink-3"}`}>
        {error || note}
      </p>
    </form>
  );
}

function KeyDialog({ open, onClose, onSave }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === e.currentTarget && onClose()}
      className="m-auto w-[min(440px,calc(100vw-32px))] rounded-panel bg-bg p-0 text-ink shadow-floating backdrop:bg-black/25"
    >
      {open && (
        <div className="px-6 pb-6 pt-6">
          <div className="flex items-baseline justify-between gap-4">
            <h2 className="font-display text-[19px] font-semibold tracking-[-0.02em]">Change your Zernio key</h2>
            <button type="button" onClick={onClose} className="text-[13px] text-ink-3 hover:text-ink">Cancel</button>
          </div>
          <p className="mb-5 mt-2 text-[14px] leading-[1.55] text-ink-2">Create a new read-write key in Zernio's Settings, under API Keys, and paste it here.</p>
          <KeyForm onSave={onSave} onDone={onClose} autoFocus label="Save" note="Your current key keeps working until Zernio accepts the new one." />
        </div>
      )}
    </dialog>
  );
}

function Setup({ t, onMenu }) {
  return (
    <div className="flex h-dvh">
      <section className="pane-detail lg:ml-0">
        <MobileBar onMenu={onMenu} />
        <div className="detail-in mx-auto max-w-[560px] px-6 pb-24 pt-16">
          <h1 className="font-display text-[30px] font-semibold leading-[1.15] tracking-[-0.035em] md:text-[36px]">
            {t.keyRejected ? "Your Zernio key stopped working" : "Connect Zernio to start posting"}
          </h1>
          <p className="mt-3 text-[16px] leading-[1.6] text-ink-2">
            {t.keyRejected
              ? "Zernio turned it down, usually because the key was deleted or replaced. Paste a new one below."
              : "Trials posts through Zernio, which handles the Instagram side. It takes about two minutes."}
          </p>
          <ol className="mb-7 mt-8 border-t border-line">
            {[
              <>In Zernio, open Settings, then API Keys, and create a read-write key.</>,
              <>Copy it and paste it below.</>,
            ].map((step, i) => (
              <li key={i} className="flex gap-4 border-b border-line py-3 text-[14px] leading-[1.55] text-ink-2">
                <span className="w-3 shrink-0 tabular-nums text-ink-3">{i + 1}</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <KeyForm onSave={t.saveKey} note="Trials checks it with Zernio, then saves it on this computer, next to your test history. It never leaves your computer except to talk to Zernio." />
        </div>
      </section>
    </div>
  );
}

export function PaneApp() {
  const t = useTrialr();
  const { selectedId, selectTest, startNewTest, addFiles, notice, setNotice, configured, publishing } = t;
  const [home, setHome] = useState(true);
  const [drawer, setDrawer] = useState(false);
  const [fileDrag, setFileDrag] = useState(false);
  const [now, setNow] = useState(Date.now());
  const fileInput = useRef(null);
  const clearNotice = useCallback(() => setNotice(null), [setNotice]);

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);

  // Publishing a new test moves the selection to it: follow along if the overview is showing.
  const lastSelected = useRef(selectedId);
  useEffect(() => {
    if (lastSelected.current !== selectedId && publishing) setHome(false);
    lastSelected.current = selectedId;
  }, [selectedId, publishing]);

  useEffect(() => {
    if (!drawer) return undefined;
    const onKey = (e) => e.key === "Escape" && setDrawer(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  const go = (fn) => {
    fn();
    setDrawer(false);
  };
  const openHome = () => go(() => setHome(true));
  const openTest = (id) => go(() => { setHome(false); selectTest(id); });
  const openNew = () => go(() => { setHome(false); startNewTest(); });
  const pick = () => fileInput.current?.click();
  // Files dropped on the overview start a new test; they are added once that view is current.
  const pending = useRef(null);
  const add = (files) => {
    if (!home) {
      addFiles(files);
      return;
    }
    pending.current = Array.from(files || []);
    setHome(false);
    startNewTest();
  };
  useEffect(() => {
    if (!home && String(selectedId).startsWith("new") && pending.current) {
      const files = pending.current;
      pending.current = null;
      addFiles(files);
    }
  }, [home, selectedId, addFiles]);

  const nav = <Nav t={t} home={home} onHome={openHome} onTest={openTest} onNew={openNew} />;
  const canDrop = configured !== false && !publishing;

  return (
    <div
      className="flex h-dvh bg-canvas"
      onDragEnter={(e) => { if (hasFiles(e) && canDrop) { e.preventDefault(); setFileDrag(true); } }}
      onDragOver={(e) => { if (hasFiles(e)) e.preventDefault(); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setFileDrag(false); }}
      onDrop={(e) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setFileDrag(false);
        if (canDrop) add(e.dataTransfer.files);
      }}
    >
      <input ref={fileInput} type="file" accept={ACCEPT} multiple tabIndex={-1} className="sr-only" onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
      <aside className="hidden h-dvh w-[236px] shrink-0 md:block">{nav}</aside>
      {drawer && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" aria-label="Close menu" onClick={() => setDrawer(false)} className="absolute inset-0 bg-black/20" />
          <aside role="dialog" aria-modal="true" aria-label="Menu" className="absolute inset-y-0 left-0 w-[272px] shadow-floating">{nav}</aside>
        </div>
      )}
      <main className="min-w-0 flex-1">
        {configured === false ? (
          <Setup t={t} onMenu={() => setDrawer(true)} />
        ) : home ? (
          <OverviewPage t={t} onTest={openTest} onMenu={() => setDrawer(true)} now={now} />
        ) : (
          <TestPage key={selectedId} t={t} onMenu={() => setDrawer(true)} onPick={pick} onHome={openHome} fileDrag={fileDrag} now={now} />
        )}
      </main>
      {fileDrag && (
        <div aria-hidden="true" className="pointer-events-none fixed inset-2 z-40 grid place-items-center rounded-panel border-2 border-dashed border-line-strong bg-[color-mix(in_oklch,var(--bg)_82%,transparent)] md:left-[244px]">
          <span className="rounded-[12px] bg-ink px-3.5 py-2 text-[13px] text-bg shadow-floating">Drop to add versions</span>
        </div>
      )}
      <Toast notice={notice} onDone={clearNotice} />
    </div>
  );
}
