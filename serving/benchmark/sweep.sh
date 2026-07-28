#!/usr/bin/env bash
# Concurrency sweep against a LOCAL vLLM server — run this ON the pod
# (measuring over the internet would pollute TTFT with network latency).
#
# Prereqs: venv active (vllm CLI on PATH), server running on :8000,
#          VLLM_API_KEY set (comes from /etc/rp_environment in login shells).
# Output:  results/c<N>.json   — latency/throughput metrics per concurrency
#          results/gpu_c<N>.csv — 1 Hz nvidia-smi samples (util %, VRAM MiB)
set -e

export OPENAI_API_KEY="${VLLM_API_KEY:?VLLM_API_KEY must be set}"
cd "$(dirname "$0")"
mkdir -p results

for c in 1 2 4 8 16 32; do
  echo "=== concurrency $c ==="
  nvidia-smi --query-gpu=utilization.gpu,memory.used \
    --format=csv,noheader,nounits -l 1 > "results/gpu_c${c}.csv" &
  GPU_PID=$!

  vllm bench serve \
    --backend openai-chat \
    --model Qwen/Qwen3-8B \
    --host 127.0.0.1 --port 8000 \
    --endpoint /v1/chat/completions \
    --dataset-name random \
    --random-input-len 512 --random-output-len 256 \
    --num-prompts $((c*10)) \
    --max-concurrency "$c" \
    --save-result --result-filename "results/c${c}.json"

  kill "$GPU_PID" 2>/dev/null || true
done

echo "Sweep complete: $(ls results/*.json | wc -l) result files in $(pwd)/results/"
