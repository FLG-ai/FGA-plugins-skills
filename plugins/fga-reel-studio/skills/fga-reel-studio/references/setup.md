# What the computer needs, and every download

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

**From nothing:** `bash "$BRIDGE/install.sh" plan <quick|full|all>` lists what is missing in order. `bash "$BRIDGE/install.sh" run <item>` installs one item after the person said yes to it. Apple's command line tools and Homebrew are the person's own to run, because they need a click or a password. The tables below are the same list in full.

Nothing here is installed or downloaded without a clear yes. Before each one say what it is, where it comes from, how big it is, and that it happens once. `bash "$BRIDGE/health.sh" all` shows what is already there and prints the fix for anything missing.

The Python environment, style and projects go in `RK_HOME` (default `~/reel-kit`). Homebrew tools and model caches use their usual locations. Allow several gigabytes for a new setup, plus space for your footage and renders. Both lanes use Python 3.12+ in `RK_HOME/.venv`. Run `install.sh run venv` after Python is available.

## For every lane
| What | Why | Command or source | Size |
|---|---|---|---|
| A Mac | The Quick lane uses Apple's face detection and text reading. Linux and Windows have not been tested for this release. | | |
| Xcode Command Line Tools | Gives python3 and the Swift compiler | `xcode-select --install` | Apple's installer, about 1 to 2 GB |
| Homebrew | Installs the next lines | https://brew.sh | small |
| ffmpeg | Every cut, zoom, mix and frame grab | `brew install ffmpeg` | about 100 MB |

## Quick lane
| What | Why | Command or source | Size |
|---|---|---|---|
| Google Chrome | Draws captions, hooks and style previews in their fonts | https://www.google.com/chrome/ | about 200 MB |
| faster-whisper | Speech to timed words, on their Mac | `"$PY" -m pip install faster-whisper pillow numpy scipy yt-dlp` after creating the environment | about 50 MB |
| Speech model (small.en) | The words | Downloads by itself on the first transcription, from Hugging Face | about 480 MB, once |

## Showcase, Hi-fi and Lo-fi lanes
Run `python3 "$KIT/setup/setup.py" --check` first. It reports only. Then `python3 "$KIT/setup/setup.py"` installs the missing pieces and ends with READY when it can render a test frame.
| What | Why | Command or source | Size |
|---|---|---|---|
| Python 3.12 or newer | The kit's own environment. Older versions pass setup and then crash at the storyboard step | `brew install python@3.12` | about 100 MB |
| Node 22 or newer | The render engine | `brew install node` | about 100 MB |
| The kit's Python environment | numpy, scipy, pillow, faster-whisper, yt-dlp | `setup.py` makes it in `RK_HOME/.venv` | about 400 MB |
| GSAP 3.15.0 | The animation library the effects use. Not bundled, downloaded for them | `setup.py`, from cdn.jsdelivr.net | under 1 MB |
| HyperFrames 0.8.139 | Turns the HTML effects into video | Fetched by `npx` on first use | small |
| HyperFrames' render browser (Chrome for rendering) | Draws every frame | Downloads on the first render | about 190 MB |
| Speech model (Whisper medium) | The transcript with word times | `setup.py` | about 1.5 GB, once |

### Optional
| What | Why | Command or source | Size |
|---|---|---|---|
| Smoother cutouts (RVM matte) | Softer hair edges when type sits behind the head | `python3 "$KIT/setup/setup.py" --matte` (PyTorch, then the model) | about 1 GB plus about 100 MB. The model is GPL-3.0: for their own use, never bundle it |
| HyperFrames background removal | The default cutout | Downloads the first time a cutout runs | about 380 MB |
| yt-dlp | Downloading reel links to study them | Already in the kit's environment | Only with a yes, naming the link, the file and the size. Instagram usually needs a login, so ask them to save the reel and send the file |
| Extra Google Fonts | The fonts in their style | `style.py` fetches them | a few MB, free licence |

## For the checks (gates)
| What | Why | Command | Size |
|---|---|---|---|
| OpenCV | `eyecheck.py` finds look-downs | `"$PY" -m pip install opencv-python-headless numpy` after creating the environment | about 60 MB |
| PyTorch and transformers, in the kit's environment | The word-level checks: `joinaudit.py`, `fixjoins.py`, `align.py`, `capcheck.py`, `look.py` | `"$PY" -m pip install torch transformers` | about 1 GB |
| wav2vec2 model (facebook/wav2vec2-base-960h) | Hears where words start and stop | Downloads on first use, from Hugging Face | about 360 MB, once |

## First use: downloads that happen by themselves
These start the first time a step needs them. Say so and ask before that step, once.
| What | Triggered by | Size |
|---|---|---|
| Speech model small.en | The first Quick-lane transcription | about 480 MB |
| Whisper medium | `setup.py` (kit lanes) | about 1.5 GB |
| A second, multilingual Whisper "small" | `onboarding/refs.py`, when measuring their example reels | about 480 MB |
| wav2vec2-base-960h | The first `joinaudit`, `fixjoins`, `align`, `capcheck` or `look` | about 360 MB |
| HyperFrames' render browser | The first render | about 190 MB |
| Background removal model and onnxruntime | The first cutout | about 380 MB |
| Google Fonts | Style previews and every Quick-lane caption render (needs internet each time) | a few MB |
`python3 "$KIT/setup/setup.py" --check` reports only and now skips the render-engine test, because that test would download HyperFrames. `refs.py` needs the kit's environment (numpy, scipy, pillow), so run it with `"$PY"`.

## Supported session

Use local Claude Code, in Terminal or the Code tab of Claude Desktop. Quick needs macOS. Linux support remains in the kit but has not been validated for this release. A cloud session does not share the local installation.

The library ships as ordinary files. `bridge/unpack.sh` is a read-only check retained for compatibility. It checks each path in `bridge/library-files.txt`.

Full setup writes `.setup-complete-0.3.3` only after its dependency, model and render checks pass. The installer also runs the read-only setup checks before treating a previous full setup as complete. If a tool or browser later stops working, run setup again after approval and review its output.
