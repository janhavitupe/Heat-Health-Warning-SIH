#!/bin/sh
# Copy the files the Docker image needs into a Hugging Face Space and push it.
# Usage (Git Bash, macOS or Linux, from the project folder):
#   sh deploy/huggingface/push_to_space.sh https://huggingface.co/spaces/<user>/<space-name>
# Needs: git, git-lfs (https://git-lfs.com), and a Hugging Face access token with write
# permission (git asks for it as the password when pushing).
set -eu
SPACE_URL="${1:?give the Space URL, e.g. https://huggingface.co/spaces/<user>/heat-health}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${TMPDIR:-/tmp}/heat-space-$$"

git lfs version >/dev/null 2>&1 || { echo "git-lfs is not installed: https://git-lfs.com" >&2; exit 1; }
git clone "$SPACE_URL" "$WORK"
cd "$WORK"
git lfs install --local
git lfs track "*.parquet" "*.pkl" "*.png" "*.jpg"

# Only what the image needs (see Dockerfile). Personal and secret files are never copied.
cd "$ROOT"
git ls-files -z -- Dockerfile .dockerignore pyproject.toml config.yaml heatrisk api resources docker \
  frontend data/processed data/manual backtest/results/may2024_city.csv scripts/demo_setup.py \
  | xargs -0 -I{} sh -c 'mkdir -p "$(dirname "$1/$2")" && cp "$2" "$1/$2"' _ "$WORK" {}
rm -f "$WORK/data/manual/test_recipients.csv" "$WORK/data/processed/walk_graph.graphml"
for f in Dockerfile docker/entrypoint.sh data/processed/access_cache.pkl data/processed/wards.parquet \
         frontend/package-lock.json scripts/demo_setup.py backtest/results/may2024_city.csv; do
  [ -f "$WORK/$f" ] || { echo "Missing $f in git: commit (and pull) the latest project first." >&2; rm -rf "$WORK"; exit 1; }
done
# The Space card: this header is what tells Hugging Face to build the Dockerfile and use port 8000
cat deploy/huggingface/SPACE_README.md > "$WORK/README.md"

cd "$WORK"
git add -A
git commit -m "Deploy Heat-Health Early Warning Platform" || echo "nothing new to commit"
git push
echo
echo "Pushed. The Space now builds (about 5-10 minutes); watch the Logs tab on the Space page."
echo "Then open: ${SPACE_URL}?replay=may2024   (direct app URL: see the Space's 'Embed this Space' menu)"
rm -rf "$WORK"
