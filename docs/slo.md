# Service Level Objectives — LLM Inference Lab

SLOs sind Zielwerte auf messbaren Größen (SLIs), gegen die der Betrieb
entscheidet: Ist das System *gut genug*, oder muss jemand handeln? Jede
Schwelle hier stammt aus eigenen Messungen ([benchmark-report](benchmark-report.md)),
nicht aus dem Bauchgefühl — und jede ist als Prometheus-Regel hinterlegt
([alerts.yml](../monitoring/prometheus/alerts.yml)).

## Die SLIs (was wir messen — und warum genau diese)

| SLI | Quelle | Was der Nutzer davon spürt |
|---|---|---|
| **TTFT P99** | `vllm:time_to_first_token_seconds` | „Reagiert es?" — enthält die Wartescklangenzeit, sieht Überlast daher zuerst |
| **ITL P99** | `vllm:inter_token_latency_seconds` | „Fließt die Antwort?" — Streaming-Ruckler, z. B. durch Preemption |
| **Verfügbarkeit** | `up` (Prometheus-Scrape) | „Ist es da?" — der Wächter gegen den lautlosen Prozess-Tod |
| **Fehlerrate** | Gateway-Statuscodes | 5xx = unser Problem; 429 = Governance arbeitet (bewusst KEIN SLO-Verstoß) |

**Warum P99 statt Mittelwert:** Der Mittelwert versteckt die Opfer. Beim
Lastlauf (unten) lag der TTFT-*Mittelwert* bei 12,9s und der P99 bei 18,1s —
aber schon ein „gesunder" Mittelwert kann bedeuten, dass jeder hundertste
Nutzer unbrauchbar bedient wird. SLOs beschreiben das schlechteste noch
akzeptierte Erlebnis, nicht das durchschnittliche.

## Die SLOs (Chat-Dienst `qwen-8b`, interaktive Nutzung)

| Ziel | Wert | Herleitung |
|---|---|---|
| TTFT P99 | **≤ 2,5 s** (5-Min-Fenster) | Benchmark: am Betriebspunkt c=8 liegt P99 weit darunter; ab dem Knick (c=16) reißt die Marke. Der Alert markiert also exakt „Concurrency über dem Knick". |
| ITL P99 | ≤ 200 ms | Flüssiges Streaming; gesunder Betrieb liegt bei ~30–70 ms, 568 ms unter Überlast war sichtbar ruckelig. |
| Verfügbarkeit | 99 % / Monat | Lab-Ziel. Entspricht einem Fehlerbudget von ~7,2 h/Monat — Wartung und Modellwechsel müssen da hineinpassen. |
| Fehlerrate (5xx) | < 1 % | 429 zählt nicht: Quota-Ablehnung ist gewollte Politik, kein Ausfall. |

## Belegmessung: SLO-Verletzung, absichtlich herbeigeführt

Lastlauf c=32 (320 Requests, 512 in / 256 out) gegen das ko-residente 8B
(KV-Pool durch den Fallback auf ~1,4 GiB geschrumpft):

| Messgröße | Solo (Di, c=32) | Ko-resident (heute, c=32) |
|---|---|---|
| Output-Durchsatz | 772 tok/s | 334 tok/s |
| TTFT P99 | 3,6 s | **18,1 s** — SLO-Bruch, Alert `TTFTP99AboveSLO` feuerte |
| TPOT P99 | gesund | 73 ms — **weiter gesund!** |
| Gleichzeitig aktiv | ~32 | Ø ~14, Peak 18; Warteschlange bis 20, KV-Cache 100 % |

Zwei Lehren daraus:

1. **Überlast trifft die Wartenden, nicht die Laufenden.** vLLM schützt
   aktive Requests (TPOT blieb bei 73 ms) und parkt den Überschuss in der
   Queue — die TTFT der Wartenden explodiert. Deshalb ist TTFT das
   Frühwarn-SLI und TPOT das Gesundheits-SLI.
2. **Kosten pro Token sind blind für Qualität.** Der überlastete Lauf
   erreichte $0,42/M Output-Tokens — exakt der Preis des Capacity Models —
   bei fünffach gerissenem SLO. Erst SLO-Panel *und* Kosten-Panel zusammen
   beschreiben den Betriebszustand.
