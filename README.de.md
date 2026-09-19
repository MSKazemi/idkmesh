# IDKMesh

[![PR Gate](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml/badge.svg?branch=main)](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![good first issues](https://img.shields.io/github/issues/MSKazemi/idkmesh/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)

**Sprache:** [English](README.md) · Deutsch

> **Übersetzungsstatus:** Diese Datei übersetzt das englische README im
> Commit `e8282fc2635c449d6e485d891e48f8c6657e2269`. Die Übersetzung wurde
> mit KI-Unterstützung erstellt und sollte noch nicht als sprachlich
> geprüfte Übersetzung gelten; dafür ist eine unabhängige Prüfung durch
> eine deutschsprachige Person erforderlich.

> **Ich weiß es nicht. Du weißt es nicht. Gemeinsam kann das Mesh entdecken, bauen, verifizieren und lernen.**

IDKMesh ist ein Open-Source-Forschungs- und Engineering-Projekt, das untersucht, wie Menschen, KI-Agenten, Software-Tools und heterogene Rechenressourcen sich bei ungewissen Zielen koordinieren und Vorschläge in **verifizierte nützliche Arbeit** umwandeln können.

Das Projekt ist bewusst ambitioniert, aber das Repository beansprucht nicht, ein fertiges System in planetarem Maßstab zu sein. Heute ist es ein **GitHub-natives Forschungslabor mit einer ausführbaren Koordinations-/Evidenzgrundlage** und einem Referenzprodukt-Ziel: dem Git-nativen Verified Swarm Runner.

**Eine konkrete Frage, die dieses Repository bereits beantworten kann:** *Wie viele unabhängige Stimmen ist dein Review-Panel wirklich wert?* Oft deutlich weniger als die Zahl der Prüfer, aus denen es besteht. In
[E017](experiments/E017-item-difficulty-and-quorum.md) maß ein Panel aus 25 Verifizierern — jeder Verifizierer ein Programm, jeder Fehler ein beobachteter, übersehener Defekt — eine effektive Größe von **1,00 von 25**: unter Mehrheitsentscheid war das Panel nicht mehr wert als ein einziges Mitglied, während die weit verbreitete Korrektur
`N/(1+(N-1)rho)` 1,66 vorhersagte. [`idkmesh gate-audit`](#probiere-es-in-fünf-minuten-audit-eines-review-gates)
führt diese Messung auf bereits gesammelten Urteilen durch und meldet, welche absichtlich fehlerhaften Kandidaten dein Panel durchgelassen hat.

## Probiere die Vertrags-Demo aus

Mit Git und Python 3.11 oder 3.13 verwende eine virtuelle Umgebung. Beispiel für Linux/macOS:

```bash
git clone https://github.com/MSKazemi/idkmesh && cd idkmesh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

Für Windows nutze die Umgebungsanleitung in [CONTRIBUTING.md](CONTRIBUTING.md).
Es wird kein Modell-Account und kein API-Schlüssel benötigt. Die Installationszeit hängt von deiner Umgebung ab.

Die Demo validiert im Repository enthaltene **synthetische Fixtures** mit den echten Validatoren und
Schemata aus [`schemas/`](schemas/) sowie den Eingaben aus [`examples/`](examples/).
Sie führt drei positive Prüfungen und vier bewusste Ablehnungsprüfungen durch:

| Ungültige Fixture | Warum sie abgelehnt wird |
| --- | --- |
| Eine Aufgabe ohne Sicherheitsvertrag | ein dispatchfähiger Vertrag muss seine Sicherheitsgrenzen deklarieren |
| Ein Worker-Ergebnis, das sich selbst akzeptiert | dass ein Worker die Arbeit abschließt, bedeutet nicht, dass sie akzeptiert ist |
| Ein Verifizierer, der die Identität des Workers nutzt | der Worker kann den Vertrag für unabhängige Verifizierer nicht selbst erfüllen |
| Eine Verifizierung mit nicht übereinstimmender Herkunft | Belege müssen an die gelieferten Artefakte gebunden sein |

**Es wird kein echter Worker und kein externer Verifizierer ausgeführt.** Dass eine Fixture die Validierung besteht,
ist kein Beweis für Unabhängigkeit in der Praxis, korrekte Arbeit oder eine Freigabe zum Mergen.
Unerwartete Prozess- oder Programmierfehler lassen die Demo scheitern, statt als
erfolgreicher Ablehnungsbeleg zu zählen.

Fragen und das „Warum wurde es so gemacht?" gehören zu
[Discussions](https://github.com/MSKazemi/idkmesh/discussions); der Issue-Tracker
ist für Defekte und abgegrenzte Arbeitsaufgaben. Für eine konkrete Aufgabe oder geteilte
technische Verantwortung siehe die
[Einladung an Mitwirkende](https://github.com/MSKazemi/idkmesh/issues/407).

## Die zentrale Frage

> **Kann eine große, offene Gemeinschaft aus Menschen und KI-Agenten Ziele entdecken, Arbeit zerlegen, abgegrenzte Aufgaben ausführen, Ergebnisse unabhängig verifizieren und komplexe Systeme besser pflegen, als isolierte Entwickler oder Agenten es könnten?**

IDKMesh behandelt das als empirische Frage. Mehr Agenten, mehr Aktivität, mehr Commits oder mehr Stimmen sind nicht automatisch besser.

## Aktueller Stand

**Ausführbare Forschungsgrundlage; der Referenz-Runner ist noch unvollständig.**

Was bereits auf `main` vorhanden ist:

- versionierte WorkUnit-Verträge, mit `work-unit-v0.2.schema.json` als aktuellem semantischem Aufgabenvertrag;
- ResultManifest-, EvaluatorPlan- und VerificationResult-Verträge, die Worker-Behauptungen, Verifizierer-Belege und Integrationsautorität trennen;
- objektübergreifende Herkunfts- und Integritätsvalidierung;
- ein Fünf-Arm-Benchmark-Vertrag zur WorkUnit-Zerlegung und eine strikte Grenze zwischen synthetischer und beobachteter Evidenz;
- protokollneutraler Worker-Adapter-Code plus A2A/MCP-Bindings und SDK-/Konformitätshelfer unter [`interop/`](interop/);
- Simulations- und Experimentcode unter [`sim/`](sim/) und [`experiments/`](experiments/);
- Experimente zur Rechenzulassung und -weiterleitung mit null Projektausgaben;
- IDKGraph-Repository-Modellierung, Observability, Link-Integrität und Warn-/Review-Maschinerie;
- GitHub-native ACE-Community-Wachstumsexperimente und Werkzeuge zur Steuerung der Repository-Evolution;
- eine erste installierbare Produktoberfläche: `pip install .` stellt die CLI
  `idkmesh` bereit, deren Befehl `gate-audit` die gemessenen Verifizierer-Panel-Ergebnisse
  (E015/E016/E017) als Review-Gate-Diagnose verpackt;
- geschütztes `main` mit dem stabilen, auf Python 3.11 und 3.13 erforderlichen PR-Gate.

Was **noch keine** fertige Fähigkeit ist:

- es wird nicht behauptet, dass IDKMesh Tausende oder Millionen echter Maschinen sicher koordinieren kann;
- der Referenz-Verified-Swarm-Runner ist noch kein ausgereiftes Installier-und-Ausführ-Produkt mit mehreren Produktions-Worker-Adaptern;
- die kanonische Integration echter Knoten bleibt ihren eigenen unabhängigen Review-/Evidenz-Gates unterworfen, statt aus historischen Prototypen abgeleitet zu werden;
- A2A/MCP-Unterstützung ist eine Interoperabilitätsschicht, keine Behauptung, dass jedes externe Agenten-Framework produktionsreif integriert ist;
- autonome Repository-/Community-Aktionen bleiben durch Richtlinien und Autorisierung eingeschränkt;
- Benchmark-Infrastruktur ist kein wissenschaftlicher Beweis, bis kontrollierte, beobachtete Läufe existieren.

Diese Unterscheidung ist wichtig: **Implementierte Infrastruktur ist Beleg für die Fähigkeit, Experimente durchzuführen, nicht Beleg dafür, dass die Forschungshypothesen wahr sind.**

## Probiere es in fünf Minuten: Audit eines Review-Gates

Das erste installierbare Werkzeug aus dieser Forschung ist `idkmesh gate-audit`. Es
misst, was ein Panel von Reviewern/Verifizierern wirklich wert ist: effektive
unabhängige Stimmen (nicht die nominelle Kopfzahl), die Fehlerkorrelationsstruktur und
die Durchbruchsrate absichtlich fehlerhafter Probe-Kandidaten.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

Das mitgelieferte Beispiel meldet, dass ein Fünf-Verifizierer-Panel etwa **1,69
effektive unabhängige Stimmen** wert ist, und dass die verbreitete Heuristik `N/(1+(N-1)ρ)`
dies überschätzt — das Phänomen, gemessen an einem echten 25-Verifizierer-Panel in
[E017](experiments/E017-item-difficulty-and-quorum.md) und als Dimensionierungsregel
widerlegt in [E015](experiments/E015-verification-phase-diagram.md). Der
Vertrag ist spezifiziert in
[`docs/specifications/GATE_AUDIT_V0_1.md`](docs/specifications/GATE_AUDIT_V0_1.md).
Das Audit ist rein diagnostisch: Es verarbeitet von dir gesammelte Urteile und erteilt keine
Akzeptanz- oder Merge-Autorität. In CI läuft dasselbe Audit als GitHub Action:

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

## Hier anfangen

Du musst nicht das gesamte Repository verstehen, bevor du beiträgst.

1. Lies dieses README.
2. Lies [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Wähle einen Beitragsweg in [`COMMUNITY.md`](COMMUNITY.md).
4. Durchstöbere die aktuellen Ansichten von [`good first issue`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22) und [`help wanted`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22).
5. Prüfe vor dem Start Zuweisungen, aktuelle Kommentare und verknüpfte Pull Requests, und nenne dann die abgegrenzte Änderung, die du vorhast.

Zwei aktuelle Beispiele zum Zeitpunkt dieses Audits:

- [#167 — unabhängige Überprüfung der IDKGraph-Waisen-Kohorte 1](https://github.com/MSKazemi/idkmesh/issues/167), eine abgegrenzte, für Neueinsteiger geeignete Evidenz-/Review-Aufgabe;
- [#151 — unabhängiges Audit der mathematischen Evolutionskontroll-Ebene](https://github.com/MSKazemi/idkmesh/issues/151), eine anspruchsvollere Sicherheits-/Regelungstechnik-Review-Aufgabe.

Das [ACE Bootstrap Cohort Observatory](https://github.com/MSKazemi/idkmesh/issues/109) ist die Live-Evidenzquelle für die ursprüngliche Wachstums-Kohorte. Es unterscheidet bewusst zwischen Aktivität und verifizierter externer Teilnahme.

Wenn etwas verwirrend, veraltet, widersprüchlich oder schwer auffindbar ist, ist es nützliche Projektarbeit, das zu melden oder zu beheben.

## IDKMesh in 60 Sekunden

- **IDK** steht für *I Don't Know* (Ich weiß es nicht): Unsicherheit, Uneinigkeit, Annahmen und konkurrierende Hypothesen sind Zustände erster Klasse.
- **Mesh** steht für ein Netzwerk aus Menschen, Agenten, Werkzeugen, Belegen, Aufgaben und Rechenleistung statt eines einzelnen monolithischen Agenten.
- Worker sollten abgegrenzte **Work Units** erhalten, keine unbegrenzte Projektautorität.
- Dass ein Worker die Arbeit abschließt, bedeutet nicht Akzeptanz; die Empfehlung eines Verifizierers bedeutet nicht Merge-Autorität.
- Verifikation, Herkunft, Reproduzierbarkeit und Sicherheit müssen mit dem Generierungsvolumen skalieren.
- Vielfalt zählt nur, wenn sie ausreichend unabhängige, nützliche Evidenz hinzufügt.
- Git/GitHub sind das aktuelle Substrat für Zusammenarbeit und kanonische Historie.
- A2A und MCP sind Integrationsoberflächen; IDKMesh sollte nicht unnötig eigene Standard-Transportprotokolle erfinden.
- Das öffentliche Repository ist zugleich Projektgedächtnis: dauerhafte Entscheidungen, Erkenntnisse, Belege und wichtige Kollaborationshistorie sollten einsehbar bleiben.

## Das Referenzprodukt

Die erste Referenzanwendung ist ein **Git-nativer Verified Swarm Runner**.

Der Ziel-Lebenszyklus ist:

```text
bounded repository task
        |
        v
   WorkUnit v0.2
        |
        v
 replaceable worker adapters
        |
        v
 candidate artifacts + ResultManifest
        |
        v
 verifier-owned EvaluatorPlan
        |
        v
 independent VerificationResult
        |
        v
 non-selecting evidence/reporting
        |
        v
 explicit human/governance integration decision
```

Die zentrale Autoritätsregel lautet:

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
```

Die aktuelle Codebasis implementiert bereits wesentliche Teile dieses Vertrauenspfads, aber das Endprodukt für Neueinsteiger wird noch konvergiert und experimentell validiert. Siehe [`EVOLUTION.md`](EVOLUTION.md), [`ROADMAP.md`](ROADMAP.md) und die offenen Projekt-Issues für die aktuellen Gates.

## Die Repository-Prüfungen ausführen

Für den Python-Forschungs-/Kontrollcode des Repositorys ist der gepflegte, bequeme POSIX-Pfad:

```bash
make setup
make test
make integration
```

Falls `make` unpraktisch ist, ist der portable, direkte Python-Pfad:

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
python -m pytest -q
```

`pytest.ini` stellt die Repository-Wurzel in `pythonpath` bereit, sodass pytest kein `PYTHONPATH=.`-Präfix benötigt. Windows-/PowerShell-Befehle sind in [CONTRIBUTING.md](CONTRIBUTING.md) und [`docs/TESTING.md`](docs/TESTING.md) dokumentiert.

Validiere die zentralen Phase-0-Verträge direkt mit:

```bash
python experiments/harness.py validate
```

Pull Requests gegen das geschützte `main` führen das stabile PR-Gate auf Python 3.11 und 3.13 aus, plus die deterministische Markdown-Link-Integritätsprüfung. Einzelne Subsysteme haben zudem engere Workflows.

## Kernarchitektur

IDKMesh versteht man am besten als ein geschichtetes System:

```text
human constitution / governance
           |
           v
 goals + questions + evidence
           |
           v
       Work Units
           |
           v
 capability/resource matching
           |
           v
 isolated humans / agents / tools / compute
           |
           v
 candidate artifacts + provenance
           |
           v
 independent verification / criticism
           |
           v
 explicit integration decision
           |
           v
 canonical state + outcome evidence
           |
           +------> next goals / policy learning
```

Das kanonische Vokabular des Lebenszyklus — Event, Aktion, Kandidat, Iteration, Generation, Lernen und Verbesserung — ist in [`ITERATION_MODEL.md`](ITERATION_MODEL.md) definiert.

Für Grenzen auf Implementierungsebene siehe [`ARCHITECTURE.md`](ARCHITECTURE.md) und den kuratierten Index [`docs/architecture/`](docs/architecture/README.md).

## Was IDKMesh baut vs. wiederverwendet

IDKMesh sollte sein Komplexitätsbudget auf die Teile verwenden, die seine Forschungsthese ausdrücken:

- Ziele, Unsicherheit und Evidenz;
- abgegrenzte Work Units und Autorität;
- Zerlegung und Abhängigkeitsstruktur;
- Fähigkeiten-/Ressourcen-Matching;
- unabhängige Verifikation und Evidenzaggregation;
- Herkunft und Reproduzierbarkeit;
- Experiment-/Benchmark-Maschinerie;
- Community- und Governance-Feedbackschleifen;
- gemessene Selbstverbesserung unter externen Autoritätsbeschränkungen.

Commodity-Infrastruktur sollte normalerweise integriert statt neu erfunden werden. Aktuelle Beispiele sind Git/GitHub, OCI-artige Isolationsmuster, A2A, MCP und etablierte Herkunfts-/Lieferketten-Ansätze.

## Forschungsdisziplin

Das Repository unterscheidet mindestens vier Zustände:

1. **implementierter Mechanismus** — Code/Schema/Workflow existiert;
2. **synthetische Validierung** — deterministische Fixtures/Simulationen prüfen die Mechanik;
3. **beobachtete Evidenz** — kontrollierte Läufe maßen reales Verhalten;
4. **akzeptierte Schlussfolgerung** — die Evidenz ist stark genug für die abgegrenzte Entscheidung.

Diese Zustände dürfen nicht vermischt werden. Ein Simulator kann die Implementierung eines Algorithmus validieren, ohne zu beweisen, dass der Algorithmus reale Zusammenarbeit verbessert.

Eine Flaggschiff-Forschungsfamilie vergleicht unter abgestimmten Budgets:

```text
one strong worker
vs one small worker
vs replicated workers
vs heterogeneous workers
vs specialized roles
vs task/evidence DAG teams
```

Zu den wichtigen Ergebnissen zählen Korrektheit, Erfolg bei versteckten Tests, Regressionen, Fehlerkorrelation, Reviewer-Zeit, Rechen-/Ressourcennutzung, Latenz, Integrationskonflikte, Herkunftsqualität und verifizierte nützliche Arbeit pro Einheit knapper Aufmerksamkeit/Kosten.

Siehe [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md), [`docs/research/`](docs/research/README.md) und [`experiments/`](experiments/).

## Projektprinzipien

**Community zuerst.** Die Erfahrung der Mitwirkenden, die Review-Kapazität und die Skalierbarkeit der Leitung sind Engineering-Beschränkungen.

**Ein Vorschlag ist kein Beweis.** Menschliches oder KI-Vertrauen ersetzt keine Evidenz.

**Popularität ist nicht Korrektheit.** Stimmen, Sterne, Ansehen oder korreliertes Modell-Einverständnis können fehlgeschlagene Prüfungen nicht aufheben.

**Mehr Agenten sind nicht automatisch besser.** Vielfalt, Unabhängigkeit, Zerlegungsqualität und Verifikationskapazität zählen mehr als die rohe Anzahl.

**Unsicherheit ist Daten.** Konkurrierende Ziele und ungelöste Hypothesen sollten explizit bleiben, wenn die Evidenz unzureichend ist.

**Generierung darf die Verifikation nicht überholen.** Ausgabevolumen ist schädlich, wenn das Projekt es nicht überprüfen, reproduzieren und pflegen kann.

**Integrieren vor Neuerfinden.** Nutze offene Standards für Commodity-Fähigkeiten und behalte IDKMesh-spezifische Semantik auf der Koordinations-/Evidenzebene.

**Skalierung muss verdient werden.** Simulierte oder kleinmaßstäbliche Ergebnisse dürfen nicht als Internet-Maßstab-Garantien beworben werden.

**Kryptografische Herkunft kommt vor Blockchain.** Füge schwerere Vertrauensinfrastruktur nur hinzu, wenn ein nachgewiesenes Bedrohungsmodell sie erfordert.

**Kanonische Autorität bleibt außerhalb von Generatoren und Verifizierern.** Geschützte Integration ist eine separate Entscheidungsgrenze.

## Repository-Leitfaden

### Neuer Mitwirkender

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Beitrags-Workflow und Prüfungen.
- [`COMMUNITY.md`](COMMUNITY.md) — Teilnahmewege und Mitwirkenden-Leiter.
- [`SUPPORT.md`](SUPPORT.md) — wie man um Hilfe bittet.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — Erwartungen an die Community.
- [`SECURITY.md`](SECURITY.md) — Meldung von Schwachstellen.

### Das System verstehen

- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — Framework-, Forschungs-, Community-, Referenzanwendungs- und Self-Hosting-Ebenen.
- [`ITERATION_MODEL.md`](ITERATION_MODEL.md) — kanonisches Evolutionsvokabular und Autoritätsfluss.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — aktuelle Architekturübersicht.
- [`EVOLUTION.md`](EVOLUTION.md) — Strategie, implementierte Grundlage und nächste Gates.
- [`ROADMAP.md`](ROADMAP.md) — evidenzgesteuerter Fortschritt vom aktuellen Stand aus.
- [`docs/README.md`](docs/README.md) — kuratierte Dokumentationsnavigation.

### Verträge und Interoperabilität

- [`schemas/README.md`](schemas/README.md) — aktuelle maschinenlesbare Verträge und Versionierungsregeln.
- [`docs/specifications/`](docs/specifications/README.md) — Protokoll-/Spezifikationsindex.
- [`interop/`](interop/) — protokollneutrale Adaptergrenze, A2A/MCP-Mappings, Identitätsbindung und Konformitätshelfer.
- [`IDKIPS.md`](IDKIPS.md) — Prozess für größere Verbesserungsvorschläge.

### Forschung und Evidenz

- [`docs/research/`](docs/research/README.md) — Forschungsprogramme und Evidenz.
- [`sim/`](sim/) — deterministischer Simulations-/Analysecode.
- [`experiments/`](experiments/) — Experimentdefinitionen, Harnesses und Ergebnis-Tools.
- [`docs/audits/`](docs/audits/) — abgegrenzte Audits und Belege zur Repository-Gesundheit.
- [`docs/findings/`](docs/findings/) — Forschungs- und Engineering-Erkenntnisse.

### Community, Governance und Projektgedächtnis

- [`GOVERNANCE.md`](GOVERNANCE.md) und [`CONSTITUTION.md`](CONSTITUTION.md) — Autorität und geschützte Prinzipien.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — ACE-Community-Wachstumsexperiment und Schutzmaßnahmen.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — repository-weite Betriebsregeln.
- [`docs/conversations/`](docs/conversations/README.md) — nur anhängbare, strukturierte Kollaborationshistorie.

## Öffentliches Projektprotokoll

Das Repository ist das dauerhafte Projektprotokoll. Wichtige Schlussfolgerungen aus der Projektarbeit sollten in die aktuelle Architektur, Spezifikationen, Entscheidungen, Erkenntnisse, Forschungsevidenz, Governance oder Implementierung überführt werden — nicht nur in Chats verbleiben oder in historischen Notizen vergraben sein.

Historische Aufzeichnungen bleiben wertvoll, sollten aber die aktuellen kanonischen Dokumente nicht stillschweigend außer Kraft setzen. Siehe [`PROJECT_RULES.md`](PROJECT_RULES.md) und [`docs/README.md`](docs/README.md) für die Dokumentationshierarchie.

## Lizenz

Apache License 2.0. Siehe [`LICENSE`](LICENSE).

## Einladung

IDKMesh geht von einem einfachen Eingeständnis aus: **Wir wissen noch nicht, wie man Intelligenz in diesem Maßstab am besten koordiniert.**

Wenn du eine Frage verbessern, eine Annahme widerlegen, ein Experiment reproduzieren, einen Test schreiben, ein Sicherheitsproblem finden, einen Vertrag klarer machen, die Reviewer-Last verringern, das Onboarding verbessern oder eine verifizierte Komponente bauen kannst, kannst du beitragen.

> **Von der Unsicherheit zur kollektiven Intelligenz — durch Evidenz.**
