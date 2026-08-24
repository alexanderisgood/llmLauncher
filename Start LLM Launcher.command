#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}

find_launcher_python() {
  local candidate
  local -a candidates
  candidates=(
    "${LLM_LAUNCHER_PYTHON:-}"
    /opt/homebrew/bin/python3
    /usr/local/bin/python3
    "${commands[python3]:-}"
    "${commands[python3.13]:-}"
    "${commands[python3.12]:-}"
    "${commands[python3.11]:-}"
    "${commands[python3.10]:-}"
    /usr/bin/python3
  )
  for candidate in "${candidates[@]}"; do
    [[ -n "$candidate" && -x "$candidate" ]] || continue
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      print -r -- "$candidate"
      return 0
    fi
  done
  return 1
}

if ! PYTHON_BIN=$(find_launcher_python); then
  print -u2 -- "LLM Launcher needs Python 3.10 or newer."
  print -u2 -- "Install current Python from python.org or Homebrew, then open this file again."
  if [[ -t 0 ]]; then read -r "?Press Return to close."; fi
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/launcher.py" "$@"
