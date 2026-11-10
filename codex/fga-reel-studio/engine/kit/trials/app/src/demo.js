const hoursAgo = (hours) => new Date(Date.now() - hours * 3600_000).toISOString();

export const demoDraftItems = [
  ["Question hook", "/demo/coastal-cliffs.jpg", 18],
  ["Number hook", "/demo/lantern-market.jpg", 24],
  ["Story hook", "/demo/sunset-surf.jpg", 15],
].map(([name, thumbnail, duration]) => ({
  id: `demo-draft-${name}`,
  file: null,
  name,
  thumbnail,
  objectUrl: "",
  duration,
  size: 0,
  errors: [],
  status: "ready",
  progress: 0,
}));

// Fill in the numbers Zernio derives, so the stock demo shows every metric.
function withDerived(a) {
  const engaged = a.likes + a.comments + a.shares + a.saves;
  return {
    igReelsVideoViewTotalTime: Math.round(a.views * a.igReelsAvgWatchTime * 0.97),
    reelsSkipRate: Math.round((80 - a.igReelsAvgWatchTime / 350) * 10) / 10,
    engagementRate: Math.round((engaged / a.reach) * 10000) / 100,
    ...a,
  };
}

function variant(id, label, thumbnail, published, analytics) {
  return {
    id,
    label,
    originalFilename: `${label.toLowerCase().replace(/\s+/g, "-")}.mp4`,
    thumbnail,
    status: "published",
    publishedAt: hoursAgo(published),
    platformPostUrl: "https://www.instagram.com/",
    analytics: withDerived(analytics),
    lastRefreshedAt: hoursAgo(0.3),
  };
}

export const demoExperiments = [
  {
    id: "demo-opening-line",
    name: "Opening line",
    hypothesis: "Leading with the dollar figure beats leading with the question.",
    caption: "I spent $4,000 learning this so you don't have to.\n\nSave this for your next launch.",
    primaryMetric: "views",
    status: "active",
    createdAt: hoursAgo(26),
    variants: [
      variant("demo-a", "Question first", "/demo/rainy-night.jpg", 26, { views: 12940, reach: 11120, likes: 640, comments: 38, saves: 241, shares: 132, igReelsAvgWatchTime: 6100 }),
      variant("demo-b", "Dollar figure first", "/demo/latte-art.jpg", 26, { views: 18420, reach: 15980, likes: 1012, comments: 71, saves: 388, shares: 214, igReelsAvgWatchTime: 7800 }),
      variant("demo-c", "Cold open, no text", "/demo/alpine-hike.jpg", 25, { views: 15110, reach: 13480, likes: 803, comments: 44, saves: 306, shares: 176, igReelsAvgWatchTime: 8300 }),
    ],
  },
  {
    id: "demo-caption-color",
    name: "Caption color",
    hypothesis: "",
    caption: "Same reel, two caption colors. Tell me which one you watched to the end.",
    primaryMetric: "igReelsAvgWatchTime",
    status: "active",
    createdAt: hoursAgo(120),
    variants: [
      variant("demo-d", "White captions", "/demo/coastal-cliffs.jpg", 120, { views: 8210, reach: 7400, likes: 310, comments: 12, saves: 98, shares: 40, igReelsAvgWatchTime: 5200 }),
      variant("demo-e", "Yellow captions", "/demo/sunset-surf.jpg", 120, { views: 9020, reach: 8100, likes: 355, comments: 19, saves: 121, shares: 52, igReelsAvgWatchTime: 5900 }),
    ],
  },
];
