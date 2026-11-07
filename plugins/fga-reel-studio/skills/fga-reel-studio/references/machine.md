# Running on a laptop (and on a bigger machine)

> In commands, `$STUDIO`, `$BRIDGE`, `$KIT`, `$QUICK`, `$GATES`, `$RUN` and `$PY` stand for the full paths named in SKILL.md. They are not shell variables: write the paths out.

Check which machine this is: `sysctl -n hw.memsize` (bytes). Under about 12 GB is the laptop profile below. `bash "$BRIDGE/health.sh"` says which one it found.

## Laptop profile (8 GB)
Several parallel builds, each with a headless browser and ffmpeg on 4K footage, can push the load past 100 and restart the machine. A restart wipes the temp folder and loses an hour of work.
1. **One heavy job at a time.** Put every render, cutout, sandbox snapshot and big encode through `"$RUN/heavy.sh" <command>`. It holds one lock under `RK_HOME` (lockf on macOS, flock on Linux, and it says so if it has neither). A job whose folder or arguments contain the text in `RK_HOME/PRIORITY` takes the lock first.
2. **Keep proxy encodes to one ffmpeg at 4 threads.**
3. **Keep small work in a persistent folder**, not the temp folder: transcripts, word lists, specs, scripts, mock screens. Only heavy proxies and renders go in temp.
4. **Render in segments with retries.** A single-pass render can stall ("sequential capture stalled" partway through). `"$RUN/render_retry.sh" <project> <name> "<title>"` renders in segments, resumes on retry, muxes the mix, runs QA and copies the result. Set `REEL_OUT` to choose where the copy goes.
5. **Builders (FX and card agents): one video's builders at a time**, five or six agents at most, and look at the plan's usage between waves. Many agents at max effort can use most of a five-hour window in half an hour.
6. **If the usage limit is near**, set up a hands-free path first: builders write their sound lines and edit changes to files, `RUN/autopilot_reel.sh <project> "<builder names>" "<title>"` finishes the video without the main session, and a scheduled restart picks up after the limit resets.
7. **Dense keyframes in every effect video** before rendering, no stacking of live full-size copies, camera-transitions copied into each project, system fonts declared. Details in `references/full-lane.md`.

## Bigger machine (16 GB or more)
Still render in segments. A little parallel work is fine.

## While a job runs
Do not start another heavy job. If health.sh says BUSY, wait or ask. Never run unattended browser or render work that the person did not ask for.
