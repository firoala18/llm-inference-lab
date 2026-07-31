# Lernstoff Tag 5 — Fallback, Resilienz & die Kunst des Debuggens (Fr 31.07.2026)

Der chaotischste und lehrreichste Tag der Woche: **acht echte Betriebsfehler**,
jeder über Logs diagnostiziert, jeder mit einer Regel als Ertrag — und am Ende
der komplette Failover-Zyklus, live bewiesen.

---

## 1. Das Endergebnis (was du vorführen kannst)

Ein Request auf `qwen-8b`, drei Systemzustände, erkennbar am `model`-Feld der Antwort:

| Zustand | `model` im Response | Bedeutung |
|---|---|---|
| Normalbetrieb | `qwen-8b` | Primärmodell antwortet |
| 8B getötet | `Qwen/Qwen3-0.6B` | **Gateway failte automatisch over** — Antwort statt Fehler |
| 8B wiederhergestellt | `qwen-8b` | Recovery, Traffic fließt zurück |

Der Nutzer ändert NICHTS — gleiche URL, gleicher Key, gleicher Request.
**Graceful degradation:** Die 0.6B-Antwort war sichtbar schwächer (holpriges
Deutsch) — einfachere Antwort schlägt keine Antwort.

## 2. Die acht Fehler des Tages und ihre Regeln

| # | Fehler | Regel daraus |
|---|---|---|
| 1 | 8B mit 0.72 zu knapp → „1.12 GiB KV needed" | vLLM verweigert Start, wenn nicht EIN voller Request passt. **Fehlermeldungen enthalten die Diagnose auf die Kommastelle.** |
| 2 | Port 8001 belegt → „Address already in use" | **Vor der Portwahl `ss -tlnp`** — Templates bringen eigene Dienste mit (nginx!). |
| 3 | SSH „Connection refused" auf altem Port | TCP-Mappings wechseln bei jedem Containerstart. **Ports niemals cachen, immer frisch abfragen.** |
| 4 | known_hosts voller Müll | **PowerShell `>>` schreibt UTF-16** — Unix-Dateien nur mit Unix-Werkzeugen füttern. |
| 5 | Modell starb lautlos (2×) | Prozess lief in der SSH-Shell statt tmux → **starb mit der Shell (SIGHUP)**. In tmux getippt ≠ in tmux gestartet — Enter in der richtigen Session! |
| 6 | `tmux -t vllm` traf `vllm-small` | **tmux matcht Namen als Präfix.** Exakt: `-t =vllm`. |
| 7 | Paralleler Start beider Modelle → OOM | **Geteilte GPU = serieller Start.** Während der eine lädt, lügt die Speicher-Momentaufnahme des anderen. |
| 8 | curl auf bootendes Modell → 502 | **Ein startender Dienst ist aus Client-Sicht tot.** Darum gibt es Readiness Probes (K8s) — Traffic erst nach Bereit-Meldung. |

## 3. Die Speicher-Eskalationsleiter (Interview-Klassiker „OOM bei geteilter GPU")

1. **Fraktionen prüfen:** Summe ≤ ~0,93 — jeder Prozess ist blind für den
   CUDA-Kontext (~0,5 GiB) des anderen.
2. **Kontextlänge senken** (`--max-model-len`): bestimmt den Mindest-KV-Bedarf.
3. **Batch senken** (`--max-num-seqs`): Sampler-/Aktivierungs-Spitzen skalieren
   mit der maximalen Batchgröße.
4. **`--enforce-eager`**: spart die CUDA-Graph-Reserve (~0,6 GiB) — legitim für
   Fallbacks, die Verfügbarkeit statt Durchsatz liefern.
5. **Kleineres Modell:** Das Primärmodell ist heilig (es trägt Benchmarks und
   SLOs) — der Notnagel schrumpft, nicht umgekehrt.

Dazu die Messung: **Der 8B-Fußabdruck variierte ±1,5 GiB zwischen Boots**
(18,3/19,8/21,4 GiB bei identischer Konfiguration — PyTorchs Allocator behält
Warmup-Spitzen). Nachbarn nie gegen den Bestfall dimensionieren.

## 4. Das Ko-Residenz-Rezept (selbst erarbeitet)

> **Klein zuerst, groß danach.** Die kleine Allokation ist bescheiden und fix;
> das große Modell füllt den tatsächlich freien Rest und passt seinen Cache an.
> Umgekehrt (groß→klein) scheitert an der Allocator-Varianz des Großen;
> parallel scheitert am Race.

Produktionsempfehlung trotzdem: Fallback auf eigene Instanz/GPU — Ko-Residenz
kostet ~70 % der KV-Parallelität des Primärmodells und verlangt
Startreihenfolge-Disziplin, die nur ein Orchestrator garantiert.

## 5. Offene Frage von gestern (Selbststudium — im Gespräch beantworten können)

**„Welcher Fehler wäre im echten Betrieb der schlimmste, und womit bemerkt man
ihn am schnellsten?"** → Der lautlose Prozess-Tod (Nr. 5): kein Fehler, kein
Log, der Dienst ist einfach weg — Nutzer merken es vor dem Betreiber. Antwort
darauf: **Monitoring mit Alerting** (P99-Latenz, Fehlerrate, Prozess-/
Endpoint-Checks) — exakt der Samstags-Block. Alle anderen Fehler melden sich
selbst beim Start; der lautlose Tod meldet sich nie.

## 6. Bonus-Thema: Quantisierung (BF16 → FP8 → INT4)

**Was:** Gewichte mit weniger Bits speichern. Qwen3-8B: BF16 = 16,4 GB,
FP8 = 8,2 GB, INT4 (AWQ) = 4,6 GB. Freiwerdender VRAM wird KV-Cache →
**~3× mehr parallele Nutzer** mit AWQ auf unserer 3090. Und weil Decoding
bandbreiten-limitiert ist: weniger Bytes pro Token → auch einzelne
Anfragen werden schneller.

**Qualitätskosten:** FP8 praktisch verlustfrei (<1 %, wird Serving-Standard).
INT4/AWQ moderat (~1–3 %), spürbar bei harten Fällen (Mathe, Code, lange
Reasoning-Ketten, seltene Sprachen). AWQ = activation-aware: schützt die
wichtigsten Gewichte, rundet den Rest. Große Modelle verkraften es besser
als kleine.

**Warum nicht immer? Drei Gründe:**
1. **Eval-Pflicht:** Benchmark-Prozente ≠ eigene Workloads. Nie quantisiert
   ausrollen ohne Eval auf ECHTEN Aufgaben (Betreiber-Regel).
2. **Hardware:** Natives FP8-Rechnen erst ab Hopper/Ada (H100, 4090+). Auf
   Ampere (unsere 3090) bringt AWQ INT4 den Gewinn, FP8 kaum.
3. **Regime:** Bei Volllast-Batches wird das System rechenlimitiert — dann
   kostet Ent-Quantisieren Rechenzeit, der Vorteil schrumpft.

**Plattform-Formulierung fürs Gespräch:** *„Gestuftes Angebot: FP8 als
Standard auf moderner Hardware, INT4 für kostensensitive Dienste und
Fallbacks, BF16 wo Qualität auditiert wird — und jeder Wechsel geht durch
ein Eval-Gate mit fachspezifischen Testfällen."*

**Direkte Wirkung aufs Capacity Model:** „Studierende pro GPU" ~×3 (größerer
KV-Pool → höhere Concurrency-Decke), $/Mio Tokens sinkt entsprechend. Zu
prüfende Annahme vor dem Umstieg: Antwortqualität auf realen Fach-Workloads.

## 7. Übungsfragen

1. **„Woran erkennen Sie in der API-Antwort, dass ein Fallback griff?"** →
   Am `model`-Feld (tatsächliches Serving-Modell statt Alias) — plus Latenz
   (Retry + Umweg) und ggf. schlichtere Antwortqualität.
2. **„Ihr Fallback-Modell ist selbst gestorben — was lernen Sie daraus?"** →
   Verfügbarkeit braucht Überwachung auf JEDER Schicht: auch der Notnagel
   braucht Supervision (systemd/K8s-Restart-Policy) und Readiness-Checks.
3. **„Warum antwortet ein bootender vLLM-Server mit Fehlern, obwohl der
   Prozess läuft?"** → Prozess ≠ Dienst: Bis Gewichte geladen und Engine
   initialisiert sind, lauscht der Port nicht. Deshalb Readiness Probes.
4. **„Zwei vLLM-Instanzen auf einer GPU — welche drei Stellschrauben machen
   das möglich?"** → Fraktionssumme ≤ 0,93, Fallback klein und gedrosselt
   (max-len, max-num-seqs, enforce-eager), serieller Start klein→groß.
