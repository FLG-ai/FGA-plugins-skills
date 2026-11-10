import { useEffect, useLayoutEffect, useRef, useState } from "react";

/* Primitives ported from Brainfile (components/ui, components/panes). */

export const STAGGER_MS = 35;
export const staggerDelay = (i) => Math.min(Math.max(0, Math.floor(i)), 10) * STAGGER_MS;

export const quietButton =
  "inline-flex h-11 items-center gap-1.5 rounded-md border border-line bg-bg px-3 text-[12.5px] text-ink-2 transition-colors hover:bg-hover hover:text-ink disabled:opacity-50 lg:h-7 lg:px-2.5";
export const primaryButton =
  "inline-flex h-11 items-center justify-center gap-1.5 rounded-md bg-accent px-3.5 text-[13px] font-medium text-accent-ink transition-[opacity,transform] hover:opacity-90 active:scale-[.97] disabled:opacity-40 disabled:active:scale-100 lg:h-8";
export const outlineButton =
  "inline-flex h-11 shrink-0 items-center gap-1.5 rounded-control bg-bg px-[11px] text-[12.5px] font-medium text-ink shadow-resting transition-[box-shadow,transform] hover:shadow-raised active:scale-[.97] disabled:opacity-50 lg:h-[30px]";
export const textButton = "inline-flex min-h-11 items-center text-[13px] text-ink-3 hover:text-ink lg:min-h-0";

/** Arc segmented control: the thumb slides between equal-width options on a spring. */
export function SegmentedControl({ label, options, value, onChange, className = "", disabled = false }) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));

  function onKeyDown(e) {
    const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!dir || disabled) return;
    e.preventDefault();
    const next = (index + dir + options.length) % options.length;
    onChange(options[next].value);
    e.currentTarget.querySelectorAll('[role="radio"]')[next]?.focus();
  }

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={`relative grid h-11 rounded-control bg-hover p-[3px] lg:h-8 ${disabled ? "opacity-60" : ""} ${className}`}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-[3px] left-[3px] rounded-[7px] bg-bg shadow-resting transition-transform duration-[580ms] ease-spring"
        style={{ width: `calc((100% - 6px) / ${options.length})`, transform: `translateX(${index * 100}%)` }}
      />
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          tabIndex={o.value === value ? 0 : -1}
          disabled={disabled}
          onClick={() => onChange(o.value)}
          className={`relative z-[1] truncate rounded-[7px] px-1 text-[12px] transition-colors ${o.value === value ? "font-medium text-ink" : "text-ink-2 hover:text-ink"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** One highlight that slides to whichever descendant matches `selector`, on Arc's spring. */
export function SlidingHighlight({ selector = '[aria-current="page"]', className = "", highlightClassName, children }) {
  const ref = useRef(null);
  const [box, setBox] = useState(null);

  useLayoutEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    let placed = false;
    const place = () => {
      const hit = root.querySelector(selector);
      if (!hit || hit.getClientRects().length === 0) {
        placed = false;
        setBox(null);
        return;
      }
      const a = root.getBoundingClientRect();
      const b = hit.getBoundingClientRect();
      const next = { top: b.top - a.top, left: b.left - a.left, width: b.width, height: b.height, animate: placed };
      placed = true;
      setBox((prev) => (prev && prev.top === next.top && prev.left === next.left && prev.width === next.width && prev.height === next.height ? prev : next));
    };
    place();
    const ro = new ResizeObserver(place);
    ro.observe(root);
    const mo = new MutationObserver(place);
    mo.observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["aria-current", "aria-checked", "hidden", "class"] });
    root.addEventListener("animationend", place);
    return () => {
      root.removeEventListener("animationend", place);
      ro.disconnect();
      mo.disconnect();
    };
  }, [selector]);

  return (
    <div ref={ref} className={`relative ${className}`}>
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute left-0 top-0 z-0 ${box?.animate ? "transition-[transform,width,height] duration-[580ms] ease-spring" : ""} ${highlightClassName}`}
        style={box ? { transform: `translateY(${box.top}px)`, left: box.left, width: box.width, height: box.height } : { display: "none" }}
      />
      {children}
    </div>
  );
}

/** Pill used on cards. */
export function Tag({ accent, gold, soft, dashed, danger, dot, title, children }) {
  return (
    <span
      title={title}
      className={`inline-flex h-5 max-w-full shrink-0 items-center gap-[5px] rounded-full px-[7px] text-[11px] font-medium tabular-nums ${
        accent
          ? "bg-accent text-accent-ink"
          : gold
            ? "bg-gold text-gold-ink"
            : soft
            ? "bg-hover-2 text-ink"
            : danger
            ? "bg-bg text-danger shadow-[inset_0_0_0_1px_var(--line)]"
            : dashed
              ? "border border-dashed border-line-strong text-ink-3"
              : "bg-bg text-ink-2 shadow-[inset_0_0_0_1px_var(--line)]"
      }`}
    >
      {dot && <i aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />}
      {children}
    </span>
  );
}

/** Status pill from the doc header: a dot and a few words. */
export function StatusPill({ tone = "ok", children }) {
  const dot = tone === "busy" ? "pulse-dot bg-ink-3" : tone === "bad" ? "bg-danger" : tone === "idle" ? "bg-ink-3" : "bg-success";
  return (
    <span className={`inline-flex h-[26px] max-w-[360px] items-center gap-1.5 rounded-full bg-hover px-2.5 text-[12px] ${tone === "bad" ? "text-danger" : "text-ink-3"}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      <span className="truncate">{children}</span>
    </span>
  );
}

/** One toast at a time, bottom center, on the spring. */
export function Toast({ notice, onDone }) {
  const [shown, setShown] = useState(null);
  useEffect(() => {
    if (!notice) return undefined;
    setShown(notice);
    // Longer messages stay up long enough to read.
    const timer = setTimeout(onDone, notice.type === "error" ? 6000 : Math.max(2600, notice.text.length * 55));
    return () => clearTimeout(timer);
  }, [notice, onDone]);
  const on = Boolean(notice);
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4">
      <div
        className={`max-w-full rounded-[12px] px-3.5 py-2 text-[13px] shadow-floating transition-[transform,opacity] duration-[580ms] ease-spring ${
          shown?.type === "error" ? "bg-danger text-white" : "bg-ink text-bg"
        } ${on ? "translate-y-0 scale-100 opacity-100" : "translate-y-4 scale-95 opacity-0"}`}
      >
        {shown?.text || ""}
      </div>
    </div>
  );
}

export const dangerButton =
  "inline-flex h-11 items-center justify-center gap-1.5 rounded-md bg-danger px-3.5 text-[13px] font-medium text-danger-ink transition-[opacity,transform] hover:opacity-90 active:scale-[.97] disabled:opacity-40 lg:h-8";

/** A modal question with a cancel and a confirm. Escape, the backdrop and Cancel all close it. */
export function ConfirmDialog({ open, title, children, confirmLabel, busy = false, onConfirm, onClose }) {
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
      onClick={(e) => e.target === e.currentTarget && !busy && onClose()}
      className="m-auto w-[min(420px,calc(100vw-32px))] rounded-panel bg-bg p-0 text-ink shadow-floating backdrop:bg-black/25"
    >
      <div className="px-6 pb-5 pt-6">
        <h2 className="font-display text-[19px] font-semibold tracking-[-0.02em]">{title}</h2>
        <div className="mt-2.5 space-y-2.5 text-[14px] leading-[1.55] text-ink-2">{children}</div>
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} disabled={busy} className={`${quietButton} justify-center lg:h-8 lg:px-3.5`}>Cancel</button>
          <button type="button" onClick={onConfirm} disabled={busy} className={dangerButton}>{busy ? "Deleting" : confirmLabel}</button>
        </div>
      </div>
    </dialog>
  );
}

const LIST_WIDTH = { min: 300, max: 520, initial: 372 };
const LIST_WIDTH_KEY = "trialr-list-w";
const clamp = (n) => (Number.isFinite(n) ? Math.round(Math.min(LIST_WIDTH.max, Math.max(LIST_WIDTH.min, n))) : LIST_WIDTH.initial);
const applyWidth = (px) => document.documentElement.style.setProperty("--list-w", `${px}px`);
const saveWidth = (px) => {
  try {
    localStorage.setItem(LIST_WIDTH_KEY, String(px));
  } catch {
    // Width still applies for this visit.
  }
};

/** Drags the list pane's width at lg and up. The 8px gutter between the panes is the handle. */
export function ResizeHandle() {
  const ref = useRef(null);
  const width = () => ref.current?.previousElementSibling?.getBoundingClientRect().width ?? LIST_WIDTH.initial;

  useLayoutEffect(() => {
    try {
      const stored = localStorage.getItem(LIST_WIDTH_KEY);
      if (stored !== null) applyWidth(clamp(Number(stored)));
    } catch {
      // Storage blocked.
    }
  }, []);

  function onPointerDown(e) {
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const startX = e.clientX;
    const startW = width();
    let last = startW;
    el.dataset.drag = "";
    const move = (m) => {
      last = clamp(startW + m.clientX - startX);
      applyWidth(last);
    };
    const up = () => {
      el.removeEventListener("pointermove", move);
      el.removeEventListener("pointerup", up);
      el.removeEventListener("lostpointercapture", up);
      delete el.dataset.drag;
      saveWidth(last);
    };
    el.addEventListener("pointermove", move);
    el.addEventListener("pointerup", up);
    el.addEventListener("lostpointercapture", up);
  }

  function onKeyDown(e) {
    const step = e.key === "ArrowLeft" ? -16 : e.key === "ArrowRight" ? 16 : 0;
    if (!step) return;
    e.preventDefault();
    const next = clamp(width() + step);
    applyWidth(next);
    saveWidth(next);
  }

  return (
    <div
      ref={ref}
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize list"
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
      onDoubleClick={() => { applyWidth(LIST_WIDTH.initial); saveWidth(LIST_WIDTH.initial); }}
      className="group relative hidden w-2 shrink-0 cursor-col-resize touch-none lg:block"
    >
      <span aria-hidden="true" className="absolute inset-x-[3px] inset-y-[40%] rounded-full transition-colors group-hover:bg-line-strong group-data-[drag]:bg-line-strong" />
    </div>
  );
}

/* Icons: 20px grid, 1.5 stroke, round caps, like Brainfile's set. */
function Icon({ className = "h-4 w-4", children }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {children}
    </svg>
  );
}
export const OverviewIcon = (p) => <Icon {...p}><path d="M3.5 16.5h13M5.5 13.5v-4M10 13.5v-8M14.5 13.5v-6" /></Icon>;
export const DecidedIcon = (p) => <Icon {...p}><circle cx="10" cy="10" r="7" /><path d="M7 10.2l2.1 2.1L13.2 8" /></Icon>;
export const TestIcon = (p) => <Icon {...p}><rect x="3" y="3.5" width="5.5" height="13" rx="1.5" /><rect x="11.5" y="6.5" width="5.5" height="10" rx="1.5" /></Icon>;
export const PlusIcon = (p) => <Icon {...p}><path d="M10 4.5v11M4.5 10h11" /></Icon>;
export const MenuIcon = (p) => <Icon {...p}><path d="M3.5 6h13M3.5 10h13M3.5 14h13" /></Icon>;
export const ChevronIcon = (p) => <Icon {...p}><path d="M7.5 4.5L13 10l-5.5 5.5" /></Icon>;
export const BackIcon = (p) => <Icon {...p}><path d="M12 4.5L6.5 10l5.5 5.5" /></Icon>;
export const RefreshIcon = (p) => <Icon {...p}><path d="M15.5 8.5A5.75 5.75 0 0 0 5 6.2M4.5 11.5A5.75 5.75 0 0 0 15 13.8" /><path d="M5 3v3.2h3.2M15 17v-3.2h-3.2" /></Icon>;
export const ExternalIcon = (p) => <Icon {...p}><path d="M8 4.5H4.5v11h11V12M11 4.5h4.5V9M15.5 4.5L9 11" /></Icon>;
export const TrophyIcon = (p) => <Icon {...p}><path d="M6.5 3.5h7v4a3.5 3.5 0 0 1-7 0v-4zM6.5 5H4.5a2.25 2.25 0 0 0 2.4 3.4M13.5 5h2a2.25 2.25 0 0 1-2.4 3.4M10 11v3M7 16.5h6M8 14h4" /></Icon>;
export const KeyIcon = (p) => <Icon {...p}><circle cx="7" cy="13" r="3.5" /><path d="M9.5 10.5L16 4M13.2 6.8l2 2M11.5 8.5l1.5 1.5" /></Icon>;
export const TrashIcon = (p) => <Icon {...p}><path d="M4 6h12M8 6V4.5h4V6M5.5 6l.8 9.5h7.4l.8-9.5" /></Icon>;
export const UploadIcon = (p) => <Icon {...p}><path d="M10 13V3.5M6.5 7L10 3.5 13.5 7M4 12.5v3.5h12v-3.5" /></Icon>;
export const PlayIcon = (p) => <svg viewBox="0 0 12 12" aria-hidden="true" className={p.className}><path d="M3.2 1.9v8.2L10 6z" fill="currentColor" /></svg>;
