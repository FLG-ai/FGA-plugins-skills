export function getReadyItems(items) {
  return items.filter((item) => item.status === "ready");
}

export function reorderItems(items, draggedId, targetId) {
  const fromIndex = items.findIndex((item) => item.id === draggedId);
  const toIndex = items.findIndex((item) => item.id === targetId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return items;

  const reordered = [...items];
  const [draggedItem] = reordered.splice(fromIndex, 1);
  reordered.splice(toIndex, 0, draggedItem);
  return reordered;
}

export function normalizeDisplayName(value, fallback) {
  const trimmed = String(value || "").trim();
  return trimmed ? trimmed.slice(0, 120) : fallback;
}

export function getPublishLabel({ publishing, current, total, readyCount }) {
  if (publishing) return `Publishing ${current} of ${total}`;
  return `Publish ${readyCount} trial reel${readyCount === 1 ? "" : "s"}`;
}
