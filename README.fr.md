# IDKMesh

[![PR Gate](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml/badge.svg?branch=main)](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![good first issues](https://img.shields.io/github/issues/MSKazemi/idkmesh/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)

**Langue :** [English](README.md) · Français

> **État de la traduction :** ce fichier traduit le README anglais au
> commit `e8282fc2635c449d6e485d891e48f8c6657e2269`. La traduction a été
> réalisée avec l'aide de l'IA et ne doit pas encore être considérée
> comme une traduction dont la qualité linguistique est vérifiée ; une
> relecture indépendante par une personne francophone est nécessaire
> avant cela.

> **Je ne sais pas. Tu ne sais pas. Ensemble, le mesh peut découvrir, construire, vérifier et apprendre.**

IDKMesh est un projet de recherche et d'ingénierie open source qui explore comment des humains, des agents d'IA, des outils logiciels et du calcul hétérogène peuvent se coordonner sur des objectifs incertains et transformer des propositions en **travail utile vérifié**.

Le projet est délibérément ambitieux, mais le dépôt ne prétend pas offrir un système achevé à l'échelle planétaire. Aujourd'hui, c'est un **laboratoire de recherche natif de GitHub doté d'une base exécutable de coordination/évidence** et d'un objectif de produit de référence : le Git-native Verified Swarm Runner.

**Une question concrète à laquelle ce dépôt peut déjà répondre :** *combien de votes indépendants votre panel de relecture vaut-il réellement ?* Souvent bien moins que le nombre de relecteurs qui le composent. Dans
[E017](experiments/E017-item-difficulty-and-quorum.md), un panel de 25 vérificateurs — chaque vérificateur étant un programme, chaque erreur un défaut observé et manqué — a mesuré une taille effective de **1,00 sur 25** : sous vote majoritaire, le panel ne valait pas plus qu'un seul membre, alors que la correction largement utilisée
`N/(1+(N-1)rho)` prédisait 1,66. [`idkmesh gate-audit`](#essayez-le-en-cinq-minutes--audit-dune-porte-de-relecture)
exécute cette mesure sur des verdicts que vous avez déjà collectés, et signale les candidats délibérément défectueux que votre panel a laissés passer.

## Essayez la démo du contrat

Avec Git et Python 3.11 ou 3.13, utilisez un environnement virtuel. Exemple pour Linux/macOS :

```bash
git clone https://github.com/MSKazemi/idkmesh && cd idkmesh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

Pour Windows, utilisez les instructions d'environnement dans [CONTRIBUTING.md](CONTRIBUTING.md).
Aucun compte de modèle ni clé d'API n'est nécessaire. Le temps d'installation dépend de votre environnement.

La démo valide des **fixtures synthétiques** déjà intégrées au dépôt avec les validateurs et
schémas réels de [`schemas/`](schemas/) et les entrées de [`examples/`](examples/).
Elle effectue trois vérifications positives et quatre vérifications de rejet délibérées :

| Fixture invalide | Pourquoi elle est rejetée |
| --- | --- |
| Une tâche sans contrat de sécurité | un contrat dispatchable doit déclarer ses limites de sécurité |
| Un résultat de worker qui s'accepte lui-même | qu'un worker termine le travail n'équivaut pas à l'accepter |
| Un vérificateur qui utilise l'identité du worker | le worker ne peut pas satisfaire lui-même le contrat de vérificateur indépendant |
| Une vérification à la provenance non concordante | les preuves doivent être liées aux artefacts fournis |

**Aucun worker réel ni vérificateur externe n'est exécuté.** Qu'une fixture passe la validation
n'est pas une preuve d'indépendance dans le monde réel, de travail correct, ni d'autorisation de fusion (merge).
Des erreurs de processus ou de programmation inattendues font échouer la démo au lieu de compter
comme une preuve de rejet réussie.

Les questions et les « pourquoi cela a-t-il été fait ainsi » relèvent des
[Discussions](https://github.com/MSKazemi/idkmesh/discussions) ; le suivi des issues
est réservé aux défauts et aux tâches de travail délimitées. Pour une tâche concrète ou une
responsabilité technique partagée, voir l'
[invitation aux contributeurs](https://github.com/MSKazemi/idkmesh/issues/407).

## La question centrale

> **Une grande communauté ouverte d'humains et d'agents d'IA peut-elle découvrir des objectifs, décomposer le travail, exécuter des tâches délimitées, vérifier les résultats de manière indépendante et maintenir des systèmes complexes mieux que ne le peuvent des développeurs ou des agents isolés ?**

IDKMesh traite cela comme une question empirique. Plus d'agents, plus d'activité, plus de commits ou plus de votes ne sont pas automatiquement synonymes de mieux.

## État actuel

**Base de recherche exécutable ; le runner de référence reste incomplet.**

Ce qui est déjà présent sur `main` :

- des contrats WorkUnit versionnés, avec `work-unit-v0.2.schema.json` comme contrat sémantique de tâche actuel ;
- des contrats ResultManifest, EvaluatorPlan et VerificationResult qui séparent les affirmations du worker, les preuves du vérificateur et l'autorité d'intégration ;
- une validation de provenance et d'intégrité inter-objets ;
- un contrat de benchmark de décomposition WorkUnit à cinq branches et une frontière stricte entre évidence synthétique et observée ;
- du code d'adaptateur worker neutre vis-à-vis du protocole, plus des bindings A2A/MCP et des aides de SDK/conformité sous [`interop/`](interop/) ;
- du code de simulation et d'expérimentation sous [`sim/`](sim/) et [`experiments/`](experiments/) ;
- des expériences d'admission et de routage de calcul à dépense projet nulle ;
- la modélisation du dépôt IDKGraph, l'observabilité, l'intégrité des liens et la mécanique d'avertissement/relecture ;
- des expériences de croissance communautaire ACE natives de GitHub et des outils de contrôle de l'évolution du dépôt ;
- une première surface de produit installable : `pip install .` fournit la CLI
  `idkmesh`, dont la commande `gate-audit` empaquette les résultats mesurés du panel de
  vérificateurs (E015/E016/E017) sous forme de diagnostic de porte de relecture ;
- `main` protégée avec la porte PR stable requise sur Python 3.11 et 3.13.

Ce qui **n'est pas encore** une capacité aboutie :

- il n'est pas affirmé qu'IDKMesh puisse coordonner en toute sécurité des milliers ou des millions de machines réelles ;
- le Verified Swarm Runner de référence n'est pas encore un produit abouti d'installation-et-exécution avec plusieurs adaptateurs worker de production ;
- l'intégration canonique de nœuds réels reste soumise à ses propres portes de relecture indépendante/évidence, plutôt que déduite de prototypes historiques ;
- le support A2A/MCP est une couche d'interopérabilité, pas une affirmation que tout framework d'agents externe est intégré en production ;
- l'action autonome sur le dépôt/la communauté reste soumise à des politiques et à une autorisation ;
- l'infrastructure de benchmark n'est pas une preuve scientifique tant que des exécutions observées et contrôlées n'existent pas.

Cette distinction est importante : **l'infrastructure implémentée est une preuve de la capacité à mener des expériences, pas une preuve que les hypothèses de recherche sont vraies.**

## Essayez-le en cinq minutes : audit d'une porte de relecture

Le premier outil installable tiré de cette recherche est `idkmesh gate-audit`. Il
mesure ce que vaut réellement un panel de relecteurs/vérificateurs : votes
indépendants effectifs (et non le nombre nominal de membres), la structure de
corrélation des erreurs, et le taux de brèche des candidats délibérément défectueux.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

L'exemple fourni indique qu'un panel de cinq vérificateurs vaut environ **1,69
votes indépendants effectifs**, et que l'heuristique populaire `N/(1+(N-1)ρ)`
le surestime — le phénomène mesuré sur un panel réel de 25 vérificateurs dans
[E017](experiments/E017-item-difficulty-and-quorum.md) et réfuté comme règle
de dimensionnement dans [E015](experiments/E015-verification-phase-diagram.md). Le
contrat est spécifié dans
[`docs/specifications/GATE_AUDIT_V0_1.md`](docs/specifications/GATE_AUDIT_V0_1.md).
L'audit est purement diagnostique : il consomme des verdicts que vous avez collectés
et n'accorde aucune autorité d'acceptation ni de fusion. En CI, le même audit s'exécute comme une GitHub Action :

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

## Commencez ici

Vous n'avez pas besoin de comprendre tout le dépôt avant de contribuer.

1. Lisez ce README.
2. Lisez [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Choisissez une voie de contribution dans [`COMMUNITY.md`](COMMUNITY.md).
4. Parcourez les vues en direct de [`good first issue`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22) et [`help wanted`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22).
5. Avant de commencer, vérifiez les assignations, les commentaires récents et les pull requests liées, puis indiquez le changement délimité que vous comptez faire.

Deux exemples en cours au moment de cet audit :

- [#167 — relecture indépendante de la cohorte orpheline 1 d'IDKGraph](https://github.com/MSKazemi/idkmesh/issues/167), une tâche de preuve/relecture délimitée et adaptée aux nouveaux venus ;
- [#151 — audit indépendant du plan de contrôle de l'évolution mathématique](https://github.com/MSKazemi/idkmesh/issues/151), une tâche de relecture en sécurité/systèmes de contrôle de niveau plus avancé.

L'[ACE Bootstrap Cohort Observatory](https://github.com/MSKazemi/idkmesh/issues/109) est la source de preuves en direct de la cohorte de croissance initiale. Il distingue délibérément l'activité de la participation externe vérifiée.

Si quelque chose est confus, obsolète, contradictoire ou difficile à trouver, le signaler ou le corriger est un travail de projet utile.

## IDKMesh en 60 secondes

- **IDK** signifie *I Don't Know* (Je ne sais pas) : l'incertitude, le désaccord, les hypothèses et les hypothèses concurrentes sont des états de premier ordre.
- **Mesh** signifie un réseau de personnes, d'agents, d'outils, de preuves, de tâches et de calcul plutôt qu'un agent monolithique unique.
- Les workers doivent recevoir des **Work Units** délimitées, pas une autorité illimitée sur le projet.
- Qu'un worker termine le travail n'équivaut pas à l'accepter ; la recommandation d'un vérificateur n'équivaut pas à une autorité de fusion.
- La vérification, la provenance, la reproductibilité et la sécurité doivent évoluer avec le volume de génération.
- La diversité ne compte que lorsqu'elle apporte des preuves utiles suffisamment indépendantes.
- Git/GitHub constituent le substrat actuel de collaboration et d'historique canonique.
- A2A et MCP sont des surfaces d'intégration ; IDKMesh ne devrait pas inventer inutilement des protocoles de transport génériques.
- Le dépôt public est aussi la mémoire du projet : les décisions durables, les découvertes, les preuves et l'historique de collaboration important doivent rester consultables.

## Le produit de référence

La première application de référence est un **Git-native Verified Swarm Runner**.

Le cycle de vie cible est :

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

La règle d'autorité clé est :

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
```

La base de code actuelle implémente déjà des parties substantielles de ce chemin de confiance, mais le produit final destiné aux nouveaux venus est encore en cours de convergence et de validation expérimentale. Voir [`EVOLUTION.md`](EVOLUTION.md), [`ROADMAP.md`](ROADMAP.md) et les issues ouvertes du projet pour les portes en vigueur.

## Exécuter les vérifications du dépôt

Pour le code Python de recherche/contrôle du dépôt, le chemin POSIX pratique et maintenu est :

```bash
make setup
make test
make integration
```

Si `make` n'est pas pratique, le chemin Python direct et portable est :

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
python -m pytest -q
```

`pytest.ini` fournit la racine du dépôt dans `pythonpath`, donc pytest n'a pas besoin du préfixe `PYTHONPATH=.`. Les commandes Windows/PowerShell sont documentées dans [CONTRIBUTING.md](CONTRIBUTING.md) et [`docs/TESTING.md`](docs/TESTING.md).

Validez directement les contrats centraux de la Phase 0 avec :

```bash
python experiments/harness.py validate
```

Les pull requests vers `main`, qui est protégée, exécutent la porte PR stable sur Python 3.11 et 3.13, plus la vérification déterministe de l'intégrité des liens Markdown. Les sous-systèmes individuels disposent également de workflows plus spécifiques.

## Architecture centrale

IDKMesh se comprend mieux comme un système en couches :

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

Le vocabulaire canonique du cycle de vie — événement, action, candidat, itération, génération, apprentissage et amélioration — est défini dans [`ITERATION_MODEL.md`](ITERATION_MODEL.md).

Pour les limites au niveau de l'implémentation, voir [`ARCHITECTURE.md`](ARCHITECTURE.md) et l'index organisé [`docs/architecture/`](docs/architecture/README.md).

## Ce qu'IDKMesh construit vs réutilise

IDKMesh devrait consacrer son budget de complexité aux parties qui expriment sa thèse de recherche :

- objectifs, incertitude et preuves ;
- Work Units délimitées et autorité ;
- décomposition et structure de dépendances ;
- appariement de capacités/ressources ;
- vérification indépendante et agrégation de preuves ;
- provenance et reproductibilité ;
- mécanique d'expérimentation/benchmark ;
- boucles de rétroaction communauté et gouvernance ;
- auto-amélioration mesurée sous contraintes d'autorité externes.

L'infrastructure générique devrait normalement être intégrée plutôt que réinventée. Les exemples actuels incluent Git/GitHub, les modèles d'isolation de type OCI, A2A, MCP et les approches établies de provenance/chaîne d'approvisionnement.

## Discipline de recherche

Le dépôt distingue au moins quatre états :

1. **mécanisme implémenté** — le code/schéma/workflow existe ;
2. **validation synthétique** — des fixtures/simulations déterministes testent la mécanique ;
3. **preuve observée** — des exécutions contrôlées ont mesuré un comportement réel ;
4. **conclusion acceptée** — la preuve est suffisamment solide pour la décision délimitée.

Ne confondez pas ces états. Un simulateur peut valider l'implémentation d'un algorithme sans prouver que l'algorithme améliore la collaboration réelle.

Une famille de recherche phare compare, sous budgets équivalents :

```text
one strong worker
vs one small worker
vs replicated workers
vs heterogeneous workers
vs specialized roles
vs task/evidence DAG teams
```

Parmi les résultats importants figurent la justesse, le succès aux tests cachés, les régressions, la corrélation des erreurs, le temps de relecture humaine, l'utilisation du calcul/des ressources, la latence, les conflits d'intégration, la qualité de la provenance et le travail utile vérifié par unité d'attention/coût rares.

Voir [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md), [`docs/research/`](docs/research/README.md) et [`experiments/`](experiments/).

## Principes du projet

**La communauté d'abord.** L'expérience des contributeurs, la capacité de relecture et l'évolutivité du leadership sont des contraintes d'ingénierie.

**Une proposition n'est pas une preuve.** La confiance humaine ou celle de l'IA ne remplace pas les preuves.

**La popularité n'est pas la justesse.** Les votes, les étoiles, la réputation ou l'accord corrélé des modèles ne peuvent pas invalider des vérifications échouées.

**Plus d'agents n'est pas automatiquement mieux.** La diversité, l'indépendance, la qualité de décomposition et la capacité de vérification comptent plus que le nombre brut.

**L'incertitude est une donnée.** Les objectifs concurrents et les hypothèses non résolues doivent rester explicites lorsque les preuves sont insuffisantes.

**La génération ne doit pas dépasser la vérification.** Le volume de production est nuisible si le projet ne peut pas le relire, le reproduire et le maintenir.

**Intégrer avant de réinventer.** Réutilisez des standards ouverts pour les capacités génériques et gardez la sémantique spécifique à IDKMesh au niveau de la coordination/preuve.

**L'échelle doit se mériter.** Les résultats simulés ou à petite échelle ne doivent pas être présentés comme des garanties à l'échelle d'Internet.

**La provenance cryptographique vient avant la blockchain.** N'ajoutez une infrastructure de confiance plus lourde que lorsqu'un modèle de menace démontré l'exige.

**L'autorité canonique reste externe aux générateurs et aux vérificateurs.** L'intégration protégée est une frontière de décision distincte.

## Guide du dépôt

### Nouveau contributeur

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — flux de contribution et vérifications.
- [`COMMUNITY.md`](COMMUNITY.md) — voies de participation et échelle des contributeurs.
- [`SUPPORT.md`](SUPPORT.md) — comment demander de l'aide.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — attentes de la communauté.
- [`SECURITY.md`](SECURITY.md) — signalement des vulnérabilités.

### Comprendre le système

- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — couches framework, recherche, communauté, application de référence et auto-hébergement.
- [`ITERATION_MODEL.md`](ITERATION_MODEL.md) — vocabulaire canonique de l'évolution et flux d'autorité.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — carte d'architecture actuelle.
- [`EVOLUTION.md`](EVOLUTION.md) — stratégie, base implémentée et prochaines portes.
- [`ROADMAP.md`](ROADMAP.md) — progression conditionnée aux preuves depuis l'état actuel.
- [`docs/README.md`](docs/README.md) — navigation documentaire organisée.

### Contrats et interopérabilité

- [`schemas/README.md`](schemas/README.md) — contrats lisibles par machine actuels et règles de versionnage.
- [`docs/specifications/`](docs/specifications/README.md) — index des protocoles/spécifications.
- [`interop/`](interop/) — frontière d'adaptateur neutre vis-à-vis du protocole, mappings A2A/MCP, liaison d'identité et aides de conformité.
- [`IDKIPS.md`](IDKIPS.md) — processus de proposition d'amélioration majeure.

### Recherche et preuves

- [`docs/research/`](docs/research/README.md) — programmes de recherche et preuves.
- [`sim/`](sim/) — code de simulation/analyse déterministe.
- [`experiments/`](experiments/) — définitions d'expériences, harnais et outils de résultats.
- [`docs/audits/`](docs/audits/) — audits délimités et preuves de santé du dépôt.
- [`docs/findings/`](docs/findings/) — découvertes de recherche et d'ingénierie.

### Communauté, gouvernance et mémoire du projet

- [`GOVERNANCE.md`](GOVERNANCE.md) et [`CONSTITUTION.md`](CONSTITUTION.md) — autorité et principes protégés.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — expérience de croissance communautaire ACE et garde-fous.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — règles de fonctionnement à l'échelle du dépôt.
- [`docs/conversations/`](docs/conversations/README.md) — historique de collaboration structuré et en ajout seul (append-only).

## Registre public du projet

Le dépôt est le registre durable du projet. Les conclusions importantes du travail de projet doivent être promues dans l'architecture, les spécifications, les décisions, les découvertes, les preuves de recherche, la gouvernance ou l'implémentation actuelles — pas seulement rester dans des discussions ou enfouies dans des notes historiques.

Les enregistrements historiques restent précieux, mais ne doivent pas silencieusement l'emporter sur les documents canoniques actuels. Voir [`PROJECT_RULES.md`](PROJECT_RULES.md) et [`docs/README.md`](docs/README.md) pour la hiérarchie documentaire.

## Licence

Apache License 2.0. Voir [`LICENSE`](LICENSE).

## Invitation

IDKMesh part d'un constat simple : **nous ne savons pas encore quelle est la meilleure façon de coordonner l'intelligence à cette échelle.**

Si vous pouvez améliorer une question, réfuter une hypothèse, reproduire une expérience, écrire un test, trouver un problème de sécurité, clarifier un contrat, réduire la charge de relecture, améliorer l'intégration des nouveaux venus ou construire un composant vérifié, vous pouvez contribuer.

> **De l'incertitude à l'intelligence collective — par la preuve.**
