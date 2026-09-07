#!/usr/bin/env bash
# Run the agent on issues for several models, sequentially, logging to runs/.
#   tools/run_matrix.sh "1 2 3" qwen3.8:27b gemma4:12b ...
set -u
issues="$1"; shift
cd "$(dirname "$0")/.."
mkdir -p runs
for model in "$@"; do
  slug=$(echo "$model" | tr '/:' '--' | sed 's/^hf.co-//')
  for i in $issues; do
    log="runs/issue$i-$slug.log"
    echo "=== $(date +%T) start issue $i model $model"
    { echo "=== issue $i $(date +%T)"
      PYTHONUNBUFFERED=1 uv run agent.py -- --issue "https://github.com/Ar4l/simple-todo-app/issues/$i" --model "$model"
      echo "exit=$? $(date +%T)"
      echo "--- ollama ps ---"; ollama ps
    } > "$log" 2>&1
    echo "=== $(date +%T) done  issue $i model $model: $(grep -E 'draft PR opened|not approved' "$log" | tail -1)"
  done
done
echo ALL-DONE
