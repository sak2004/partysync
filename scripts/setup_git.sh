#!/bin/sh
# One-time Git setup for PartySync (macOS, Linux, or Git Bash on Windows).
set -e
cd "$(dirname "$0")/.."

command -v git >/dev/null 2>&1 || { echo "git is not installed." >&2; exit 1; }

if [ ! -d .git ]; then
  git init -b main 2>/dev/null || { git init && git symbolic-ref HEAD refs/heads/main; }
else
  echo "Repo already initialised."
fi

git config core.hooksPath .githooks
git config commit.template .gitmessage
chmod +x .githooks/* scripts/*.sh 2>/dev/null || true

if [ -z "$(git config user.name)" ] || [ -z "$(git config user.email)" ]; then
  echo "WARNING: git identity is not set. Run:" >&2
  echo '  git config --global user.name "Your Name"' >&2
  echo '  git config --global user.email "you@example.com"' >&2
fi

if ! git rev-parse --verify --quiet HEAD >/dev/null; then
  git add -A
  git commit -m "chore: scaffold PartySync project" -m "Milestone: M0"
  git tag -a v0.0.0 -m "Scaffold"
  git tag -a milestone-M0 -m "M0 Repo scaffold and version control"
else
  echo "Repo already has commits, nothing committed."
fi

echo
echo "Done. Hooks active (.githooks), commit template set."
echo "Next: git switch -c m1-core-dsp   (one branch per milestone)"
