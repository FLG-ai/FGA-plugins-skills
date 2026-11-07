#!/usr/bin/env python3
"""FX sandbox: preview some of a video's motion graphics (edit.FX) without touching the real build, so several agents
can work on one video at once.

Makes <project>/work/sandbox/<name>/ (its own edit.py copy, words/timeline, public/ with every heavy file linked from
the project), builds it with only the FX ids you name (the others are left out, so a broken one can't break yours),
and snapshots the times you ask for. fx/ is the project's own folder (linked), so what you write there is the real file.

Run: PY pipeline/fxsandbox.py <project> <name> --only fx01,fx16 --at 0.5 1.2 2.0 [--fresh]
  --fresh   re-copy edit.py from the project (otherwise your sandbox edit.py edits are kept)
Edit <sandbox>/edit.py to try GRADES / CUT_WINDOWS / CAMERA changes; report them, the real edit.py is merged by hand.
Prints the snapshot paths: read every one at full size.
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import KIT, PY  # noqa: E402


def main():
    a = sys.argv[1:]
    project, name = os.path.abspath(os.path.expanduser(a[0])), a[1]
    only = a[a.index("--only") + 1] if "--only" in a else ""
    times = [float(x) for x in a[a.index("--at") + 1:] if not x.startswith("--")] if "--at" in a else []
    sb = os.path.join(project, "work", "sandbox", name)
    pub, ppub = os.path.join(sb, "public"), os.path.join(project, "public")
    os.makedirs(pub, exist_ok=True)
    for f in ("words.json", "timeline.json"):
        shutil.copy(os.path.join(project, f), os.path.join(sb, f))
    if "--fresh" in a or not os.path.exists(os.path.join(sb, "edit.py")):
        shutil.copy(os.path.join(project, "edit.py"), os.path.join(sb, "edit.py"))
    for link, target in [(os.path.join(sb, "fx"), os.path.join(project, "fx")),
                         (os.path.join(sb, "assets"), os.path.join(project, "assets")),
                         (os.path.join(sb, "audio"), os.path.join(project, "audio")),
                         (os.path.join(sb, "style"), os.path.join(project, "style"))]:   # the project's own pack
        if not os.path.lexists(link):
            os.symlink(target, link)
    for f in os.listdir(ppub):                     # heavy media and vendor: links; index.html and snapshots: own
        if f in ("index.html", "snapshots", "fx"):
            continue
        if not os.path.lexists(os.path.join(pub, f)):
            os.symlink(os.path.join(ppub, f), os.path.join(pub, f))
    env = dict(os.environ, FX_ONLY=only)
    subprocess.run([PY, os.path.join(KIT, "pipeline", "build.py"), sb, "--stills"], check=True, env=env)
    if times:
        sys.path.insert(0, os.path.join(KIT, "pipeline"))
        from storyboard import snapshot
        out = os.path.join(sb, "shots")
        shutil.rmtree(out, ignore_errors=True)
        names = snapshot(sb, times, out)
        for t, n in zip(times, names):
            print(f"{t:7.3f}  {os.path.join(out, n)}")


if __name__ == "__main__":
    main()
