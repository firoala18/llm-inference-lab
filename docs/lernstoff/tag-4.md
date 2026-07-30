# Lernstoff Tag 4 — Gateway, Governance & Chargeback (Do 30.07.2026)

Heute gebaut: die Schicht, die in der Stellenausschreibung wörtlich steht —
„API-Gateways für KI-Dienste (OpenAI-kompatible Schnittstellen), Routing-,
Quota- und Governance-Mechanismen".

---

## 1. Was ein Gateway ist (und warum die Uni eins braucht)

**Die eine Tür.** Alle KI-Anfragen der Uni gehen durch einen Punkt: das Gateway.
Dahinter können beliebige Backends stehen (unser vLLM, später mehrere Replikas,
andere Modelle) — davor sieht jeder Client dasselbe: eine URL, ein Key,
OpenAI-Format. Das Gateway prüft, zählt, begrenzt, verteilt.

Der Weg eines Requests (auswendig können!):

```
Client (Fakultäts-Key) → Gateway :4000
  → Postgres-Check: Key gültig? Budget übrig? rpm/tpm okay? Modell erlaubt?
  → Alias-Auflösung: "qwen-8b" → hosted_vllm/Qwen/Qwen3-8B @ Pod-URL
  → Call zum Backend (mit dem BACKEND-Key, den der Client nie sieht)
  → Antwort zurück + Verbrauch auf den Fakultäts-Key verbucht
```

## 2. Die drei Key-Schichten (Prüfungsklassiker)

| Key | Besitzer | Zweck |
|---|---|---|
| Backend-Key (`VLLM_API_KEY`) | nur das Gateway | vLLM redet ausschließlich mit dem Gateway |
| Master-Key | nur Admin | erzeugt/sperrt virtuelle Keys, sieht alle Ausgaben |
| Virtuelle Keys | Fakultäten/Nutzer | Anfragen stellen — mit Budget, Limits, Modell-Whitelist |

**Governance-Merksatz:** Technik erzwingt die Regeln (Budgets, Limits im
Gateway), Gremien beschließen sie (wer bekommt wie viel).

## 3. Config-Trennung: Struktur vs. Umgebung

- **`config.yaml`** = Struktur: welche Modelle, welche Aliase, welche Preise.
  Versioniert in Git, für jede Umgebung gleich.
- **`.env`** = Umgebung: Pod-URL (ändert sich bei jedem Deploy!), Secrets.
  Gitignored, pro Maschine verschieden.
- Verkettung: `.env` → Compose `env_file` → Container-Umgebung →
  `os.environ/NAME` in config.yaml → HTTP-Call.
- **Falle:** Env-Variablen werden beim Container-**Erstellen** eingefroren.
  `.env` geändert? → `docker compose up -d --force-recreate <service>`,
  ein bloßes `restart` liest sie nicht neu. (Datei-Mounts wie config.yaml
  dagegen: restart genügt, die Datei wird beim Start neu gelesen.)

## 4. Compose-Konzepte am eigenen Stack

- **Image** (Rezept) → **Container** (laufendes Exemplar) → **Service**
  (Compose-Eintrag) → **Stack** (alle Services zusammen).
- `depends_on` mit `condition: service_healthy`: LiteLLM startet erst, wenn
  Postgres *antwortet* (pg_isready-Healthcheck) — nicht nur „gestartet ist".
  Ohne das: Race Condition, LiteLLM crasht beim Erststart, weil die DB noch
  keine Verbindungen annimmt.
- `:ro` beim Config-Mount: Container darf lesen, nicht schreiben (Least Privilege).
- Benanntes Volume `pgdata`: Keys/Abrechnung überleben `compose down` —
  dasselbe Persistenz-Prinzip wie das Network Volume beim Pod.

## 5. Die zwei Arten von 429 (Betriebs-Prüfungsfrage!)

| | Nutzer-Quota | Backend-Schutz (Cooldown) |
|---|---|---|
| Meldung | „Rate limit exceeded for api_key" | „No deployments available … try again in 5s" |
| Ursache | Key hat rpm/tpm/Budget gerissen | Backend-Fehler → Circuit Breaker öffnet |
| Gegenmaßnahme | nichts — gewolltes Verhalten (ggf. Limit anpassen) | Backend heilen, Fallback greifen lassen |

**Warum unterscheiden?** Bei Quota ist das System gesund und tut seinen Job.
Beim Cooldown ist das Backend krank — gleiche HTTP-Nummer, gegenteiliger
Handlungsbedarf.

## 6. Chargeback: Preise aus dem eigenen Capacity Model

Selbst gehostete Modelle stehen in keiner Preisliste — der Betreiber setzt
den internen Verrechnungspreis selbst. Unsere Kette:

> Benchmark (Di) → $/1M Tokens bei Betriebspunkt c=8 (Mi: $0,41 Output) →
> `input_cost_per_token: 1e-07` / `output_cost_per_token: 4.1e-07` in
> config.yaml (Do) → jeder Request wird der Fakultät berechnet.

Beweis: Request mit 24 Prompt- + 200 Output-Tokens → spend $0,0000844 =
24×1e-07 + 200×4.1e-07. **Auf den Cent nachrechenbar.**

Dazu gelernt: Abrechnung ist **batch-verzögert** (LiteLLM sammelt DB-Writes) —
direkt nach dem Request zeigt `key/info` noch alte Zahlen. Eventual Consistency.

## 7. Kleinere Perlen des Tages

- **Thinking-Modelle:** Qwen3 verbrauchte alle 200 max_tokens im `<think>`-Block
  → `finish_reason: "length"`, keine Antwort. Fix: höheres Limit oder Thinking
  per Request abschalten (`chat_template_kwargs: {"enable_thinking": false}`).
- **API-Ebenen:** UI, MCP, SDK sind Hüllen um dieselbe REST-API. Kann die Hülle
  ein Feature nicht (networkVolumeId!), geht man eine Ebene tiefer. Und:
  **stille Parameter-Verluste** (MCP reichte das Feld als Env-Var durch) sind
  gefährlich — Ergebnis immer verifizieren (`mounts` war leer).
- **PowerShell + curl:** PS 5.1 zerhackt `\"`-Escapes → JSON-Body immer als
  Datei übergeben: `-d "@body.json"`.

## 8. Übungsfragen

1. **„Ein Lehrstuhl will direkt auf den vLLM-Server zugreifen, das Gateway sei
   ihm zu langsam. Was antworten Sie?"** → Direktzugriff umgeht Budget,
   Limits, Abrechnung und Auditierbarkeit — genau die Governance, die den
   Betrieb für alle fair macht. Der Latenz-Overhead des Gateways ist minimal
   (lokaler Hop); wenn Latenz wirklich drückt, misst man erst, statt die
   Kontrollschicht zu opfern.
2. **„Woher nehmen Sie Preise für ein selbst gehostetes Modell?"** → Aus der
   eigenen Messung: GPU-Stundenpreis ÷ gemessener Durchsatz am Betriebspunkt
   → $/Token. Bei uns: $0,50/h ÷ 1,22 M Tokens/h ≈ $0,41/M Output.
3. **„Ihr Monitoring zeigt viele 429 — ist das ein Incident?"** → Kommt drauf
   an, welche: Quota-429 = System arbeitet wie designt. Cooldown-429 =
   Backend-Problem, Incident-Verdacht. Erst die Fehlermeldung lesen, dann
   eskalieren.
4. **„Warum liegt Ihre Gateway-Konfiguration in Git, die .env aber nicht?"** →
   Struktur ist reproduzierbar und reviewbar (GitOps-Vorstufe!), Umgebung ist
   maschinen-spezifisch und geheim. Trennung erlaubt: gleiche Config in Dev
   und Prod, nur die .env unterscheidet sich.
