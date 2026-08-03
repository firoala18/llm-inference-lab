# Lernstoff Tag 7 — Kubernetes & GitOps (Sa 01.08.2026, nachmittags)

Der Tag, an dem der Compose-Stack sein drittes Zuhause bekam — und
Deployments zu Git-Commits wurden. Dazu: eine Sicherheitslektion, die
schmerzhafter kaum sein könnte.

---

## 1. Die YAML-Anatomie (gilt für JEDES K8s-Objekt)

```yaml
apiVersion: apps/v1    # welche API-Gruppe das Objekt definiert
kind: Deployment       # WAS es ist
metadata:              # WIE es heißt (name, namespace, labels)
spec:                  # WAS GELTEN SOLL — der Wunschzettel
```

> **`spec` = dein Wunsch. `status` = die Realität** (schreibt der Cluster
> selbst dazu). Der gesamte Kubernetes-Motor ist die Maschine, die status
> an spec angleicht — dauerhaft, nicht einmalig.

Ein Deployment ist eine Matrjoschka: Deployment → `spec.template`
(Pod-Blaupause) → `containers` (image, args, env, mounts, probes).

## 2. Compose → K8s (die Übersetzungstabelle)

| Compose | Kubernetes | OpenShift-Vokabel |
|---|---|---|
| `services: x` | Deployment + Service | dito |
| Servicename als DNS | Service (Cluster-DNS) — `DATABASE_URL` blieb zeichengleich! | dito |
| Bind-Mount `:ro` | ConfigMap als Datei gemountet | dito |
| `env_file: .env` | Secret (`envFrom: secretRef`) | dito |
| Named Volume | PersistentVolumeClaim | dito |
| `healthcheck` + `service_healthy` | readinessProbe (gated Traffic, NICHT Startreihenfolge) | dito |
| — | livenessProbe (hängender Prozess wird ersetzt) | dito |
| — | Namespace | **Project** |
| `docker compose up` | `kubectl apply` → Controller konvergieren | `oc apply` |

**Es gibt kein `depends_on`.** LiteLLM stürzt ohne DB ab, wird neu
gestartet, bleibt not-ready — bis die DB da ist. **Konvergenz statt
Choreografie**: funktioniert auch um 3 Uhr nachts, eine Startreihenfolge
nur beim Start.

## 3. Selbstheilung, gemessen

`kubectl delete pod -l app=litellm` → neuer Pod existierte nach **6
Sekunden**, `1/1` nach dem DB-Connect. Dieselbe Aktion kostete am
Fallback-Tag (tmux/SSH) eine halbe Stunde Handarbeit. Pod-Namensschema:
`litellm-<replicaset-hash>-<zufall>` — gleicher Hash = gleiche Blaupause,
neuer Hash = Rollout.

> Interview-Satz: „Verfügbarkeit ist bei Kubernetes keine Disziplin mehr,
> sondern eine Plattformeigenschaft."

## 4. Die unsichtbaren Fäden (Namen, die zusammenpassen MÜSSEN)

- Deployment `selector.matchLabels` ↔ `template.metadata.labels` ↔ Service
  `selector` — alles `app: litellm`. Tippfehler im Service-Selector =
  **stiller Defekt** (Service ohne Endpoints, keine Fehlermeldung!).
- `envFrom.secretRef.name` ↔ `Secret.metadata.name`
- `volumes.configMap.name` ↔ `ConfigMap.metadata.name`
- `claimName` ↔ PVC-Name; Service-**Name** ↔ DNS-Hostname
- Nichts ist verdrahtet — alles lose gekoppelt über Etiketten.

## 5. GitOps (ArgoCD)

Bisher: DU sagst dem Cluster, was gilt (`kubectl apply`). Jetzt: **das
Repo sagt es** — ArgoCD vergleicht dauernd Git↔Cluster und gleicht ab.

- `syncPolicy.automated`: `prune` (aus Git gelöscht → aus Cluster
  gelöscht) + `selfHeal` (Hand-Änderungen am Cluster werden auf den
  Git-Stand **zurückgedreht**).
- Bewiesen: `replicas: 1→2` als Git-Commit — zweiter Pod erschien ohne
  ein einziges kubectl. **Deployment = Commit; Rollback = git revert;
  Deployment-History = Git-History.**
- **Secrets niemals in den Sync**: unsere Vorlage trug denselben
  `metadata.name` wie das echte Secret — ohne `directory.exclude` hätte
  der Sync echte Zugangsdaten mit Platzhaltern überschrieben. Produktion:
  SealedSecrets / External Secrets Operator.
- kubeconfig-Lektion: `kubectl` ist nur ein HTTPS-Client; Cluster-URL +
  Zertifikate stehen in `~/.kube/config`. k3d trug `host.docker.internal`
  ein → Timeout; Fix: eine Zeile auf `127.0.0.1`. Adressen in Configs
  sind Behauptungen — geprüft wird gegen die echte Port-Bindung.

## 6. Die Sicherheitslektion des Tages (GitHub-Kuratierung)

Beim Professionalisieren des GitHub-Profils: **Azure-SQL-Connection-String
mit Klartext-Passwort in einem öffentlichen Repo gefunden** (produktive
appsettings + eine committete Tooling-Datei — in ALLEN Commits).

Die Regeln daraus:
1. **Privatstellen heilt kein Leck.** Öffentliche Repos werden binnen
   Minuten von Bots abgegrast — ein je öffentliches Secret ist
   kompromittiert. Einzige echte Abhilfe: **Rotation**.
2. Historie bereinigen = `git filter-repo --invert-paths --path <datei>`
   + Force-Push; GitHub kann alte SHAs trotzdem noch cachen → Rotation
   bleibt Pflicht. Alte lokale Klone enthalten das Secret weiter — nie
   wieder von dort pushen.
3. Das Schutzmuster ist immer dasselbe (im Lab 4× gebaut):
   **committete Struktur + gitignoriertes Secret + `.example`-Vorlage**
   (config.yaml/.env, prometheus.yml/pod-targets.json,
   authorization/credentials_file, ConfigMap/Secret).

## 7. Übungsfragen (mit Antworten)

1. **„Kubernetes hat kein depends_on — wie startet dann eine App vor
   ihrer Datenbank nicht?"** → Tut sie ruhig: Sie crasht/bleibt
   not-ready und wird neu gestartet, bis die DB antwortet. Readiness
   gated den Traffic. Konvergenz statt Startreihenfolge.
2. **„`app: litellm` steht dreimal in litellm.yaml — welche Stelle tut
   was?"** → Deployment-`selector.matchLabels` **zählt** („davon halte
   ich replicas Stück am Leben"), `template.metadata.labels`
   **etikettiert** (Stempel auf jedem erzeugten Pod), Service-`selector`
   **routet** (dorthin fließt Traffic). Tippfehler im Service-Selector =
   **stiller Defekt**: DNS löst auf, aber null Endpoints, Clients laufen
   in Timeouts (`kubectl get endpoints` → leer). Tippfehler zwischen
   Deployment-Selector und Template-Labels = **laut**: Apply wird
   abgelehnt.
3. **„Verfolgen Sie VLLM_API_KEY bis zur Nutzung."** → Deployment:
   `envFrom → secretRef: litellm-secrets` (lädt alle Secret-Schlüssel
   als Env) → Secret `litellm-secrets` (gitignored, .example committed):
   `stringData.VLLM_API_KEY` = echter Wert → Container-Env → ConfigMap:
   `api_key: os.environ/VLLM_API_KEY` liest zur Laufzeit. Struktur
   öffentlich, Wert privat — der echte Schlüssel berührt Git nie.
4. **„Warum `strategy: Recreate` für die DB?"** → PVC ist
   ReadWriteOnce: nur ein Pod darf schreibend mounten. RollingUpdate
   startet neu NEBEN alt → Multi-Attach-Hänger oder (lokal) zwei
   Postgres-Prozesse auf denselben Dateien → Korruption. Recreate: erst
   töten, dann starten — kurzer Ausfall als bewusster Preis; echte HA
   macht Replikation, nicht Update-Strategie.
5. **„Jemand skaliert von Hand auf 5 Replikas — was passiert?"** →
   Kurz existieren 5 Pods, dann stellt ArgoCD Drift fest (Git: 2 ≠
   Cluster: 5) und **`selfHeal: true`** dreht auf den Git-Stand zurück.
   Die Hand-Änderung verliert immer — wer skalieren will, committet.
   Genau dadurch bleibt der Cluster-Zustand auditierbar: ein Eingang.
6. **„Ein Secret lag im öffentlichen Repo, Sie haben es gelöscht und
   die Historie bereinigt — fertig?"** → Nein. Rotation ist Pflicht:
   Bots scrapen öffentliche Repos in Minuten, GitHub cacht alte SHAs,
   alte Klone existieren. Bereinigung verhindert künftiges Finden,
   Rotation entwertet das Gefundene.
