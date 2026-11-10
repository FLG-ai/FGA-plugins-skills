# FGA Reel Studio 0.4.0

A local Claude Code skill for editing talking-to-camera reels. Read START-HERE.md to install it.

The download contains the complete effects library as ordinary files. Run install-claude-code.sh after extracting the ZIP. The installed folder contains SKILL.md at its top level.

## Folder map

| Path | Purpose |
| --- | --- |
| SKILL.md | Claude's editing workflow |
| references/ | Style, editing and setup guidance |
| bridge/ | Installation, health checks and style conversion |
| engine/quick/ | Quick editing steps, including Mac face detection |
| engine/kit/ | Storyboards, motion graphics and the bundled library |
| engine/gates/ | Checks on cuts, captions and sound |
| engine/run/ | Render helpers |

## Changes in 0.4.0

The editing engine is now reel-kit 1.2.0: 71 effects, 27 more than before (a front page with you in the photo, paper tearing, a blade slicing the frame, the Vertigo shot, a cursor dragging you across the room and more, each listed in `engine/kit/fx/LIBRARY.md` under "Added in 1.2.0"). They pre-render clips from your own take, so face and hand tracking (about 400 MB) and a depth model (about 100 MB) install the first time one is picked, and five of them want 5 seconds of the empty room at the end of the take. Setup runs once more after you update. Your style, projects and finished videos stay as they are.

## Changes in 0.3.3

The library is unpacked in the release. Installation preserves an existing copy. Both lanes use a Python 3.12+ environment, and full setup records success only after its checks pass. A failed command or failed post-install check returns an error.

The editing engines and existing creative assets are retained. Packaging and setup checks do not establish the quality of a finished reel. Run a sample edit before distributing this version widely.

Original credits and licence files are included.
