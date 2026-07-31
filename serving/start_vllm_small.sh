#!/usr/bin/env bash
# Fallback model: Qwen3-0.6B on :8002, sharing the GPU with the 8B on :8000.
#
# Sizing history (the hard-won lessons):
# - Port 8002, not 8001: the template's nginx already owns 8001 (`ss -tlnp`).
# - Qwen3-0.6B, not 1.7B: after the 8B takes its share (~19-20 GiB incl. CUDA
#   context, varies ~1 GiB between boots), only ~4 GiB remain. The 1.7B needed
#   ~4.6 GiB real and OOM'd three times. The primary model's config is
#   sacrosanct — the fallback shrinks, not the other way around.
# - max-num-seqs 4: sampler/activation peaks scale with max batch size.
# - enforce-eager: no CUDA-graph memory; a fallback is sized for availability,
#   not throughput.
export HF_HOME=/workspace/.huggingface
export VLLM_API_KEY="${VLLM_API_KEY:?set VLLM_API_KEY first}"
vllm serve Qwen/Qwen3-0.6B \
  --host 0.0.0.0 \
  --port 8002 \
  --api-key "$VLLM_API_KEY" \
  --dtype auto \
  --gpu-memory-utilization 0.14 \
  --max-model-len 2048 \
  --max-num-seqs 4 \
  --enforce-eager \
  2>&1 | tee /workspace/vllm_small.log
