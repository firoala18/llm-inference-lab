# Governance & Resilience — Keys, Budgets, Limits, Fallback

How the gateway turns one GPU into a governed, multi-tenant, failure-tolerant
service. Everything below is implemented and was demonstrated live; raw
evidence is quoted from actual responses.

## 1. The three key layers

| Key | Holder | Purpose |
|---|---|---|
| Backend key (`VLLM_API_KEY`) | gateway only | vLLM talks exclusively to the gateway; the public port is useless without it |
| Master key (`LITELLM_MASTER_KEY`) | platform admin | mints/revokes virtual keys, reads spend across all tenants |
| Virtual keys | faculties / apps | end-user credential with budget, rate limits, model whitelist |

Clients never see the backend key or the pod URL — the gateway is the only door.

## 2. Per-faculty governance (implemented)

| Alias | Budget | rpm | tpm | Models |
|---|---|---|---|---|
| fakultaet-informatik | $5.00 / 30d | 30 | 20,000 | qwen-8b |
| fakultaet-jura | $1.00 / 30d | 3 | 2,000 | qwen-8b |

- **Rate limiting proven:** 6 rapid requests on the jura key → requests 1–3
  served, 4–6 rejected `429 "Rate limit exceeded for api_key"`.
- **Chargeback proven:** internal prices derived from our own
  [capacity model](capacity-model.md) ($0.10/M input, $0.41/M output at the
  c=8 operating point). A 24-in/200-out request billed **$0.0000844** —
  arithmetic checks exactly. Self-hosted models have no market price; the
  operator's benchmark *is* the price list.
- Spend accounting is **batch-written** (eventual consistency): `key/info`
  directly after a request still shows the old total.

**Two kinds of 429 (operations essential):** user-quota 429 ("Rate limit
exceeded…") means the system works as designed; cooldown 429 ("No deployments
available…") means a backend is unhealthy and the circuit breaker opened.
Same status code, opposite required action.

## 3. Fallback chain (implemented & demonstrated)

```yaml
router_settings:
  fallbacks:
    - qwen-8b: ["qwen-mini"]   # Qwen3-0.6B on :8002
  num_retries: 1
```

Live demonstration (single request, no client change):

| Phase | Response `model` field | Observation |
|---|---|---|
| Normal | `qwen-8b` | primary answers |
| Primary killed | `Qwen/Qwen3-0.6B` | gateway retried, then failed over — user got an answer, not an error |
| Primary restored | `qwen-8b` | recovery, traffic returns |

The fallback answer is visibly simpler (the 0.6B's German is shaky) —
**graceful degradation**: a simpler answer beats no answer.

## 4. Co-residency on one 24-GB GPU — findings

Getting an 8B primary and a fallback model onto one RTX 3090 failed four ways
before it worked. The distilled rules:

1. **Combined memory fractions must stay ≤ ~0.93**, not ≤ 1.0 — each vLLM
   process budgets against *total* VRAM and is blind to the other's CUDA
   context (~0.5 GiB each) and allocator cache.
2. **The big model's footprint varies ±1.5 GiB between boots** (PyTorch's
   caching allocator retains warmup spikes: we measured 18.3 / 19.8 / 21.4 GiB
   for identical config). Never size the neighbor against the best case.
3. **Start order matters: small first, big second.** The small model's
   allocation is modest and fixed; the big one then fills what is actually
   free. The reverse order failed repeatedly; parallel start races and fails.
4. **Cap the fallback aggressively:** `--max-model-len 2048 --max-num-seqs 4
   --enforce-eager` — sampler and activation peaks scale with batch size, and
   a fallback is sized for availability, not throughput.
5. **Check what already listens before picking ports** (`ss -tlnp`) — the
   RunPod template's nginx owned :8001.

**Production recommendation:** run the fallback on a separate instance/GPU or
a managed platform (Kubernetes/OpenShift with readiness probes and restart
policies). Same-GPU co-residency works — we run it — but it trades ~70 % of
the primary's KV-cache headroom and depends on start-order discipline that
only an orchestrator can guarantee.

## 5. What the university deployment adds on top

- Quotas decided by governance bodies, enforced by the gateway; IT provides
  transparency (per-faculty spend dashboards) rather than making policy.
- Virtual keys replaced by SSO/LDAP-integrated identity.
- Readiness probes so a booting model receives no traffic (we hit this: a
  starting service is indistinguishable from a dead one without them).
- Process supervision (systemd/K8s) instead of tmux sessions.
