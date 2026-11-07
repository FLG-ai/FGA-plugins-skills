# Credits and licences

## reel-kit (the Lo-fi, Hi-fi and Showcase lanes)
`engine/kit/` is **reel-kit** by Justyn Berk, MIT licence, Copyright (c) 2026 Justyn Berkovits. https://github.com/justynberk/reel-kit
The licence text is in `LICENSE-reel-kit.txt` and `engine/kit/LICENSE`. The kit's sound effects are CC0 1.0. The upstream commit this snapshot started from and the local changes to it are in `engine/kit/patches/`.

## The Quick lane
`engine/quick/` is the FGA IG Reel Designer + Editor plugin by Farris Green (farrisgreen.ai): ten small steps from a raw take to a finished reel. Its starter sounds were made for it.

## What was added to join them
`bridge/` (the style bridge in both directions and the health check), `engine/gates/` (look-down, join, caption-timing and alignment checks), `engine/run/` (the lock, segmented render and autopilot scripts) and the reference files. Written by Farris Green with Claude.

## Not bundled
GSAP (GreenSock), HyperFrames, the RVM matte model, speech and alignment model weights, and Google Fonts are downloaded on the person's own computer from their own sources, under their own licences. See `references/setup.md`.
