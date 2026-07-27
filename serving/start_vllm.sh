#!/usr/bin/env bash
# Serve Qwen3-8B on a RunPod A5000 (24 GB), OpenAI-compatible API on :8000.
#
# On the current pod this is not needed: the pod runs the vllm/vllm-openai
# image, which starts the server itself with these flags as the container
# start command. This script documents that configuration and is the startup
# path if the pod is switched to a plain PyTorch template (pip install vllm).
#
# --enforce-eager disables CUDA graphs. The RunPod template sets it; it costs
# throughput. Benchmark both: VLLM_EXTRA_ARGS="--enforce-eager" ./start_vllm.sh
export HF_HOME=/workspace/.huggingface
export VLLM_API_KEY="${VLLM_API_KEY:?set VLLM_API_KEY first}"
vllm serve Qwen/Qwen3-8B \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --dtype auto \
  --gpu-memory-utilization 0.95 \
  --max-model-len 8128 \
  ${VLLM_EXTRA_ARGS:-} \
  2>&1 | tee /workspace/vllm.log
