# Lernstoff Tag 2 — Benchmarking & Cloud-Kapazität (Di 28.07.2026)

Alles hier hast du heute selbst erlebt — inklusive der Pannen. Gerade die sind
Gesprächsgold: Betreiber-Erfahrung erzählt man am besten als Geschichte.

---

## 1. Die Kapazitäts-Lektion des Vormittags

**Was passiert ist:** Pod über Nacht gestoppt → morgens „not enough free GPUs
on the host machine" — dreimal. Die A5000 auf unserem Host hatte sich jemand
anderes genommen.

**Die Begriffe dahinter:**

| Konzept | Merksatz |
|---|---|
| **Stop ≠ Reservierung** | Stoppen beendet die Abrechnung UND gibt die GPU frei. Wiederbekommen ist Glückssache. |
| **Pod-Volume** | Klebt am Pod, der am Host klebt. Host voll → Daten unerreichbar. |
| **Network Volume** | Eigenständige Ressource, überlebt sogar Pod-Terminierung. Aber: an EIN Rechenzentrum gebunden, nur Secure Cloud. |
| **Der Trade-off** | Persistenz kaufst du mit Ortsbindung: Unser Volume lebt in EU-CZ-1 — GPUs müssen wir künftig DORT finden (dafür ist der GPU-Typ frei wählbar). |

**Wie eine Uni das löst:** Eigene Hardware (OpenShift-Cluster) hat das Problem
„fremde Mieter" nicht — dafür das Pendant: endliche GPUs, die Fakultäten sich
teilen. Antwort dort: Quotas, Scheduling, Kapazitätsplanung — Gateway-Thema ab
Donnerstag.

## 2. Benchmark-Methodik (das Handwerk)

- **Nur eine Variable ändern:** Wir haben ausschließlich die Concurrency
  variiert (1→32). Prompt-Längen fix (512 rein / 256 raus), Modell fix,
  Hardware fix. Sonst weißt du nie, WAS du gemessen hast.
- **Auf localhost messen:** Vom PC aus hätte jede TTFT-Zahl ~30–50 ms
  Atlantik/EU-Latenz + Jitter enthalten. Server-Benchmark ≠ Netzwerk-Benchmark.
- **Perzentile, nicht Mittelwert:** c=1 zeigte Median 153 ms, aber P99 592 ms.
  Der Durchschnitt versteckt die Nutzer, die leiden. SLOs formuliert man als
  „99 % unter X ms".
- **Stationärer Zustand:** `num_prompts = 10 × concurrency` — jede Stufe läuft
  lang genug, dass sich das System einpendelt.
- **Werkzeug:** `vllm bench serve` — spielt einen Schwarm OpenAI-Clients,
  misst TTFT/TPOT/ITL/Durchsatz, schreibt JSON. Parallel loggt `nvidia-smi -l 1`
  GPU-Auslastung und VRAM in CSV.

## 3. Deine Messreihe (RTX 3090, Qwen3-8B, BF16, 512/256)

| Concurrency | TTFT median | TTFT P99 | ITL median | Durchsatz | Requests/s |
|---|---|---|---|---|---|
| 1 | 153 ms | 592 ms | 20,3 ms | 48 tok/s | 0,19 |
| 2 | 128 ms | 286 ms | 20,4 ms | 95 tok/s | 0,37 |
| 4 | 146 ms | 515 ms | 20,9 ms | 182 tok/s | 0,71 |
| 8 | 151 ms | 864 ms | 21,6 ms | 338 tok/s | 1,32 |
| **16** | **1096 ms** | 1892 ms | 24,1 ms | 510 tok/s | 1,99 |
| 32 | 1196 ms | **3612 ms** | 27,1 ms | 772 tok/s | 3,02 |

**Die Geschichte in drei Sätzen (auswendig!):**
1. Bis c=8 ist Batching fast gratis: 7-facher Durchsatz, TTFT bleibt bei
   ~150 ms — Continuous Batching füllt die GPU einfach besser aus.
2. Zwischen 8 und 16 kippt es: TTFT versiebenfacht sich auf über 1 s —
   Requests konkurrieren jetzt spürbar um Rechenzeit/Scheduling.
3. Ab 32 kauft man Durchsatz mit inakzeptabler Schwanz-Latenz (P99 3,6 s):
   gut für Batch-Jobs, schlecht für Chat.

**Warum ITL kaum steigt (20→27 ms), TTFT aber explodiert:** Wer einmal im
Batch IST, wird flüssig weiterbedient — das Warten passiert VOR dem ersten
Token (Scheduling/Prefill-Warteschlange). Deshalb ist TTFT die empfindlichste
Betriebsmetrik.

## 4. Bash-Werkzeugkasten (aus sweep.sh)

- `set -e` — Skript stirbt beim ersten Fehler; verhindert 30 min Messung auf
  kaputtem Zustand.
- `${VAR:?Meldung}` — defensiver Pflicht-Check: fehlt VAR, klare Fehlermeldung
  statt kryptischem 401 später.
- `befehl &` + `$!` + `kill` — Hintergrundprozess starten, PID merken, gezielt
  beenden. So läuft der GPU-Logger parallel zur Messung.
- **tmux-Regel (heute etabliert):** Alles, was länger läuft als ein Kaffee,
  läuft in tmux. Der SSH-Disconnect während pip hat es fast bewiesen.

## 5. Übungsfragen

1. **„Ihr Server schafft 772 tok/s bei c=32 — warum fahren Sie ihn trotzdem
   nur mit c≈8–16?"** → Weil ab da die P99-TTFT jenseits von 2–3 s liegt;
   Durchsatz nützt nichts, wenn interaktive Nutzer warten. SLO vor Auslastung.
2. **„Woran erkennen Sie im Monitoring, dass eine GPU überbucht ist?"** →
   TTFT-P99 steigt sprunghaft, Warteschlange (waiting requests) wächst, ITL
   bleibt zunächst stabil, Durchsatz stagniert.
3. **„Was ist der Unterschied zwischen TTFT und ITL, und welche Metrik gehört
   in ein Chat-SLO?"** → TTFT = Zeit bis zum ersten Token (enthält Warten +
   Prefill), ITL = Takt der Folgetokens. Beide gehören ins SLO, aber TTFT ist
   der Frühindikator für Überlast.
4. **„Wie stellen Sie sicher, dass Benchmark-Ergebnisse vergleichbar sind?"**
   → Eine Variable variieren, Rest fixieren; localhost; Perzentile; Setup
   (GPU, Modell, dtype, Kontextlänge, vLLM-Version) dokumentieren.
5. **„Pod-Volume vs. Network Volume — wann was?"** → Pod-Volume: billig,
   einfach, aber host-gebunden — okay für Wegwerf-Experimente. Network Volume:
   überlebt Pod-Wechsel, GPU-Typ flexibel — Pflicht für alles, was wiederkommen
   soll. Kostenpunkt ~0,07 $/GB/Monat.
