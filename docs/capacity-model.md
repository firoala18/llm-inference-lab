# Capacity Model — How Many Students Does One GPU Serve?

Derived from the [benchmark report](benchmark-report.md) (RTX 3090, Qwen3-8B,
512/256-token chat requests). Every assumption is stated; change an assumption
and the model recomputes trivially.

## SLO

> **P99 time-to-first-token < 2 s** for interactive chat, streaming ITL < 100 ms.

Measured against this SLO:

| Concurrency | P99 TTFT | SLO? |
|---|---|---|
| 8 | 864 ms | ✅ comfortable (57 % headroom) |
| 16 | 1892 ms | ⚠️ passes with 108 ms to spare |
| 32 | 3612 ms | ❌ |

**Operating point: c = 8, burst ceiling c = 16.** Systems are operated *before*
the knee, not on it: the 8→16 gap absorbs load spikes and longer-than-average
prompts. Beyond 16, the gateway must queue or rate-limit (see
[governance.md](governance.md)).

## From concurrency to students

Assumptions (documented, adjustable):

- A chatting student sends one request every **90 s** on average.
- A request occupies a concurrency slot for `TTFT + 256 tokens × ITL`.

| | c=8 | c=16 |
|---|---|---|
| Slot time per request | 0.15 + 256×0.0216 ≈ **5.7 s** | 1.1 + 256×0.024 ≈ **7.2 s** |
| Duty cycle per student | 5.7/90 ≈ 6.3 % | 7.2/90 ≈ 8 % |
| Students per slot | ~16 | ~12.5 |
| **Students per GPU** | **~125** | **~200** |

> **One 24-GB GPU serves roughly 125–200 concurrently active chat users.**
> A course with 1,000 simultaneously active students needs ~5–8 such GPUs
> (plus failover reserve) behind a load-balancing gateway.

## Cost per token

GPU price: $0.50/h (RunPod Secure Cloud; university-owned hardware changes the
constant, not the method).

| Operating mode | Throughput | Tokens/hour | $ / 1M output tokens |
|---|---|---|---|
| c=1 (unbatched) | 48 tok/s | 0.17 M | **$2.89** |
| c=8 (SLO-comfortable) | 338 tok/s | 1.22 M | **$0.41** |
| c=16 (SLO ceiling) | 510 tok/s | 1.84 M | **$0.27** |
| c=32 (batch jobs) | 772 tok/s | 2.78 M | **$0.18** |

**Cost per token is a utilization property, not a hardware property** — the same
GPU is 10× cheaper per token at c=16 than at c=1. This is the economic argument
for a *central* inference platform: pooled load keeps batching high; scattered
per-department GPUs idle at c≈1 economics.

## Scaling levers (in order of preference)

1. **Replicas behind the gateway** — N identical vLLM instances, load-balanced;
   linear capacity growth, no single point of failure.
2. **Quantization (AWQ/GPTQ int4)** — weights shrink ~16 → ~5.5 GB, freeing VRAM
   for KV cache → higher concurrency ceiling per card (quality trade-off to be
   benchmarked per use case).
3. **Batch/interactive separation** — batch workloads (grading, summarization)
   run at c≥32 economics on off-peak hours instead of competing with chat.
4. **Bigger GPUs** — last resort: an A100/H100 raises the ceiling but at
   disproportionate cost; exhaust batching efficiency first.

## Limitations

- Synthetic fixed-length workload; real prompt/response lengths vary widely.
- Single model; multi-model serving shares the KV-cache budget.
- Thinking-mode (Qwen3) inflates output lengths if enabled — benchmarks ran
  with length-capped generation.
- Network latency between user and gateway (~10–50 ms) comes on top of TTFT
  but is independent of GPU load.
