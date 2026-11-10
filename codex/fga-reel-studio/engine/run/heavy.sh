#!/bin/sh
# One heavy job at a time on a low-memory laptop (several parallel builds can restart an 8 GB machine).
# Every render, cutout, sandbox snapshot and big ffmpeg encode goes through this lock: heavy.sh <command> [args...]
# Jobs whose folder or arguments contain the text in $REEL_KIT_HOME/PRIORITY take the lock first.
# macOS uses lockf and Linux uses flock. With neither, the job runs unlocked and says so.
# already inside a heavy job (the autopilot calls heavy.sh itself): the lock is held, so just run
[ -n "$HEAVY_HELD" ] && exec "$@"
export HEAVY_HELD=1
RKH="${REEL_KIT_HOME:-$HOME/reel-kit}"
L="$RKH/heavy.lock"; Q="$RKH/prio"; P="$RKH/PRIORITY"
mkdir -p "$Q"

if [ -x /usr/bin/lockf ]; then LK=lockf
elif command -v flock >/dev/null 2>&1; then LK=flock
else LK=none; echo "heavy.sh: no lockf or flock found, running without the one-job-at-a-time lock" >&2; fi

lock_wait() { case "$LK" in lockf) /usr/bin/lockf -k "$L" "$@";; flock) flock "$L" "$@";; *) "$@";; esac; }
lock_try()  { case "$LK" in lockf) /usr/bin/lockf -k -s -t 0 "$L" "$@";; flock) flock -n -E 75 "$L" "$@";; *) "$@";; esac; }

pat=""; [ -f "$P" ] && pat=$(head -1 "$P")
prio="$HEAVY_PRIORITY"
if [ -n "$pat" ]; then
  case "$PWD $*" in *"$pat"*) prio=1 ;; esac
fi
if [ -n "$prio" ]; then
  touch "$Q/$$"
  trap 'rm -f "$Q/$$"' EXIT INT TERM HUP
  lock_wait /bin/sh -c 'rm -f "$0"; exec nice -n 5 "$@"' "$Q/$$" "$@"
  exit $?
fi
waiting() {   # a priority job is queued (markers of dead jobs are cleared)
  for f in "$Q"/*; do
    [ -e "$f" ] || continue
    if kill -0 "${f##*/}" 2>/dev/null; then return 0; fi
    rm -f "$f"
  done
  return 1
}
while :; do
  if ! waiting; then
    lock_try nice -n 5 "$@"
    rc=$?
    [ "$rc" -ne 75 ] && exit "$rc"
  fi
  sleep 2
done
