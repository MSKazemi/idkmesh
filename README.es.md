# IDKMesh

[![PR Gate](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml/badge.svg?branch=main)](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![good first issues](https://img.shields.io/github/issues/MSKazemi/idkmesh/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)

**Idioma:** [English](README.md) · Español

> **Estado de la traducción:** este archivo traduce el README en inglés en el
> commit `e8282fc2635c449d6e485d891e48f8c6657e2269`. La traducción se preparó
> con ayuda de IA y todavía no debe considerarse una traducción de calidad
> lingüística verificada; antes de tratarla como tal se necesita la revisión
> independiente de una persona hispanohablante.

> **Yo no sé. Tú no sabes. Juntos, la mesh puede descubrir, construir, verificar y aprender.**

IDKMesh es un proyecto de investigación e ingeniería de código abierto que explora cómo personas, agentes de IA, herramientas de software y cómputo heterogéneo pueden coordinarse sobre objetivos inciertos y convertir propuestas en **trabajo útil verificado**.

El proyecto es intencionalmente ambicioso, pero el repositorio no afirma tener un sistema terminado a escala planetaria. Hoy es un **laboratorio de investigación nativo de GitHub con una base ejecutable de coordinación/evidencia** y un objetivo de producto de referencia: el Git-native Verified Swarm Runner.

**Una pregunta concreta que este repositorio ya puede responder:** *¿cuántos votos independientes vale realmente tu panel de revisión?* A menudo, muchos menos que el número de revisores que lo componen. En
[E017](experiments/E017-item-difficulty-and-quorum.md), un panel de 25 verificadores — cada verificador un programa, cada error un defecto observado y no detectado — midió un tamaño efectivo de **1.00 de 25**: bajo voto mayoritario, el panel valía lo mismo que un solo miembro, mientras que la corrección ampliamente usada
`N/(1+(N-1)rho)` predecía 1.66. [`idkmesh gate-audit`](#pruébalo-en-cinco-minutos-audita-una-puerta-de-revisión)
ejecuta esa medición sobre veredictos que ya hayas recopilado, e informa qué candidatos deliberadamente defectuosos dejó pasar tu panel.

## Prueba la demo del contrato

Con Git y Python 3.11 o 3.13, usa un entorno virtual. Ejemplo para Linux/macOS:

```bash
git clone https://github.com/MSKazemi/idkmesh && cd idkmesh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

Para Windows, usa las instrucciones de entorno en [CONTRIBUTING.md](CONTRIBUTING.md).
No se necesita cuenta de modelo ni clave de API. El tiempo de instalación depende de tu entorno.

La demo valida **fixtures sintéticos** ya incluidos en el repositorio con los validadores y
esquemas reales de [`schemas/`](schemas/) y las entradas de [`examples/`](examples/).
Realiza tres comprobaciones positivas y cuatro comprobaciones de rechazo deliberadas:

| Fixture inválido | Por qué se rechaza |
| --- | --- |
| Una tarea sin contrato de seguridad | un contrato despachable debe declarar sus límites de seguridad |
| Un resultado de worker que se acepta a sí mismo | que un worker complete el trabajo no equivale a aceptarlo |
| Un verificador que usa la identidad del worker | el worker no puede satisfacer por sí mismo el contrato de verificador independiente |
| Una verificación con procedencia no coincidente | la evidencia debe vincularse a los artefactos suministrados |

**No se ejecuta ningún worker real ni verificador externo.** Que un fixture pase la validación
no es prueba de independencia en el mundo real, de trabajo correcto ni de autorización para integrar (merge).
Los errores de proceso o de programación inesperados hacen fallar la demo en lugar de contarse
como evidencia de rechazo exitoso.

Las preguntas y los "por qué se hizo así" pertenecen a
[Discussions](https://github.com/MSKazemi/idkmesh/discussions); el rastreador de issues
es para defectos y piezas de trabajo acotadas. Para una tarea concreta o una responsabilidad
técnica compartida, consulta la
[invitación a colaboradores](https://github.com/MSKazemi/idkmesh/issues/407).

## La pregunta central

> **¿Puede una gran comunidad abierta de personas y agentes de IA descubrir objetivos, descomponer el trabajo, ejecutar tareas acotadas, verificar resultados de forma independiente y mantener sistemas complejos mejor de lo que pueden hacerlo desarrolladores o agentes aislados?**

IDKMesh trata esto como una pregunta empírica. Más agentes, más actividad, más commits o más votos no son automáticamente mejores.

## Estado actual

**Base de investigación ejecutable; el runner de referencia sigue incompleto.**

Lo que ya está presente en `main`:

- contratos de WorkUnit versionados, con `work-unit-v0.2.schema.json` como el contrato semántico de tarea actual;
- contratos de ResultManifest, EvaluatorPlan y VerificationResult que separan las afirmaciones del worker, la evidencia del verificador y la autoridad de integración;
- validación de procedencia e integridad entre objetos;
- un contrato de benchmark de descomposición de WorkUnit de cinco brazos y un límite estricto entre evidencia sintética y observada;
- código de adaptador de worker neutral respecto al protocolo, más bindings A2A/MCP y ayudantes de SDK/conformidad en [`interop/`](interop/);
- código de simulación y experimentos en [`sim/`](sim/) y [`experiments/`](experiments/);
- experimentos de admisión y enrutamiento de cómputo con gasto de proyecto cero;
- modelado del repositorio IDKGraph, observabilidad, integridad de enlaces y maquinaria de advertencias/revisión;
- experimentos de crecimiento comunitario ACE nativos de GitHub y herramientas de control de evolución del repositorio;
- una primera superficie de producto instalable: `pip install .` proporciona la CLI
  `idkmesh`, cuyo comando `gate-audit` empaqueta los resultados medidos del panel de
  verificadores (E015/E016/E017) como un diagnóstico de puerta de revisión;
- `main` protegida con el PR gate estable requerido en Python 3.11 y 3.13.

Lo que **todavía no** es una capacidad terminada:

- no se afirma que IDKMesh pueda coordinar con seguridad miles o millones de máquinas reales;
- el Verified Swarm Runner de referencia aún no es un producto pulido de instalar-y-ejecutar con múltiples adaptadores de worker de producción;
- la integración de nodos reales canónicos sigue sujeta a sus propias puertas de revisión independiente/evidencia, en lugar de inferirse a partir de prototipos históricos;
- el soporte A2A/MCP es una capa de interoperabilidad, no una afirmación de que todo framework de agentes externo esté integrado en producción;
- la actuación autónoma sobre el repositorio/la comunidad sigue sujeta a políticas y autorización;
- la infraestructura de benchmarks no es prueba científica hasta que existan ejecuciones observadas y controladas.

Esta distinción es importante: **la infraestructura implementada es evidencia de la capacidad de ejecutar experimentos, no evidencia de que las hipótesis de investigación sean ciertas.**

## Pruébalo en cinco minutos: audita una puerta de revisión

La primera herramienta instalable extraída de esta investigación es `idkmesh gate-audit`. Mide
cuánto vale realmente un panel de revisores/verificadores: votos independientes efectivos
(no el número nominal de integrantes), la estructura de correlación de errores y la tasa de
brecha de candidatos deliberadamente defectuosos.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

El ejemplo incluido informa que un panel de cinco verificadores vale aproximadamente **1.69
votos independientes efectivos**, y que la popular heurística `N/(1+(N-1)ρ)`
lo sobreestima — el fenómeno medido en un panel real de 25 verificadores en
[E017](experiments/E017-item-difficulty-and-quorum.md) y refutado como regla de
dimensionamiento en [E015](experiments/E015-verification-phase-diagram.md). El
contrato está especificado en
[`docs/specifications/GATE_AUDIT_V0_1.md`](docs/specifications/GATE_AUDIT_V0_1.md).
La auditoría es solo diagnóstica: consume veredictos que tú recopilaste y no otorga
autoridad de aceptación ni de integración (merge). En CI, la misma auditoría se ejecuta como una GitHub Action:

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

## Empieza aquí

No necesitas entender todo el repositorio antes de contribuir.

1. Lee este README.
2. Lee [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Elige una vía de contribución en [`COMMUNITY.md`](COMMUNITY.md).
4. Explora las vistas en vivo de [`good first issue`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22) y [`help wanted`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22).
5. Antes de empezar, revisa asignados, comentarios recientes y pull requests vinculados, y luego indica el cambio acotado que planeas hacer.

Dos ejemplos vigentes al momento de esta auditoría:

- [#167 — revisar de forma independiente la cohorte huérfana 1 de IDKGraph](https://github.com/MSKazemi/idkmesh/issues/167), una tarea de evidencia/revisión acotada y adecuada para quien recién llega;
- [#151 — auditar de forma independiente el plano de control de evolución matemática](https://github.com/MSKazemi/idkmesh/issues/151), una tarea de revisión de seguridad/sistemas de control de mayor nivel de habilidad.

El [ACE Bootstrap Cohort Observatory](https://github.com/MSKazemi/idkmesh/issues/109) es la fuente de evidencia en vivo de la cohorte original de crecimiento. Distingue deliberadamente actividad de participación externa verificada.

Si algo resulta confuso, desactualizado, contradictorio o difícil de encontrar, reportarlo o corregirlo es trabajo útil para el proyecto.

## IDKMesh en 60 segundos

- **IDK** significa *I Don't Know* (No lo sé): la incertidumbre, el desacuerdo, los supuestos y las hipótesis en competencia son estados de primera clase.
- **Mesh** significa una red de personas, agentes, herramientas, evidencia, tareas y cómputo, en lugar de un único agente monolítico.
- Los workers deben recibir **Work Units** acotadas, no autoridad ilimitada sobre el proyecto.
- Que un worker complete el trabajo no equivale a aceptarlo; la recomendación de un verificador no equivale a autoridad de integración (merge).
- La verificación, la procedencia, la reproducibilidad y la seguridad deben escalar junto con el volumen de generación.
- La diversidad importa solo cuando aporta evidencia útil suficientemente independiente.
- Git/GitHub son el sustrato actual de colaboración e historial canónico.
- A2A y MCP son superficies de integración; IDKMesh no debería inventar innecesariamente protocolos de transporte genéricos.
- El repositorio público es también memoria del proyecto: las decisiones duraderas, los hallazgos, la evidencia y el historial de colaboración importante deben permanecer inspeccionables.

## El producto de referencia

La primera aplicación de referencia es un **Git-native Verified Swarm Runner**.

El ciclo de vida objetivo es:

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

La regla clave de autoridad es:

```text
worker success != acceptance
verification recommendation != merge authority
CI success != independent human review
```

La base de código actual ya implementa partes sustanciales de esta ruta de confianza, pero el producto final para quien recién llega todavía se está convergiendo y validando experimentalmente. Consulta [`EVOLUTION.md`](EVOLUTION.md), [`ROADMAP.md`](ROADMAP.md) y los issues abiertos del proyecto para ver las puertas vigentes.

## Ejecuta las comprobaciones del repositorio

Para el código Python de investigación/control del repositorio, la ruta POSIX mantenida y conveniente es:

```bash
make setup
make test
make integration
```

Si `make` no es conveniente, la ruta portable directa con Python es:

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
python -m pytest -q
```

`pytest.ini` proporciona la raíz del repositorio en `pythonpath`, así que pytest no requiere el prefijo `PYTHONPATH=.`. Los comandos de Windows/PowerShell están documentados en [CONTRIBUTING.md](CONTRIBUTING.md) y [`docs/TESTING.md`](docs/TESTING.md).

Valida directamente los contratos centrales de la Fase 0 con:

```bash
python experiments/harness.py validate
```

Los pull requests hacia `main`, que está protegida, ejecutan el PR gate estable en Python 3.11 y 3.13, más la comprobación determinista de integridad de enlaces en Markdown. Los subsistemas individuales también tienen workflows más específicos.

## Arquitectura central

IDKMesh se entiende mejor como un sistema de capas:

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

El vocabulario canónico del ciclo de vida —evento, acción, candidato, iteración, generación, aprendizaje y mejora— se define en [`ITERATION_MODEL.md`](ITERATION_MODEL.md).

Para los límites a nivel de implementación, consulta [`ARCHITECTURE.md`](ARCHITECTURE.md) y el índice curado [`docs/architecture/`](docs/architecture/README.md).

## Qué construye IDKMesh y qué reutiliza

IDKMesh debería gastar su presupuesto de complejidad en las partes que expresan su tesis de investigación:

- objetivos, incertidumbre y evidencia;
- Work Units acotadas y autoridad;
- descomposición y estructura de dependencias;
- emparejamiento de capacidades/recursos;
- verificación independiente y agregación de evidencia;
- procedencia y reproducibilidad;
- maquinaria de experimentos/benchmarks;
- ciclos de retroalimentación de comunidad y gobernanza;
- automejora medida bajo restricciones de autoridad externas.

La infraestructura genérica normalmente debería integrarse en lugar de reinventarse. Los ejemplos actuales incluyen Git/GitHub, patrones de aislamiento al estilo OCI, A2A, MCP y enfoques establecidos de procedencia/cadena de suministro.

## Disciplina de investigación

El repositorio distingue al menos cuatro estados:

1. **mecanismo implementado** — el código/esquema/workflow existe;
2. **validación sintética** — fixtures/simulaciones deterministas prueban la mecánica;
3. **evidencia observada** — ejecuciones controladas midieron comportamiento real;
4. **conclusión aceptada** — la evidencia es suficientemente sólida para la decisión acotada en cuestión.

No colapses estos estados entre sí. Un simulador puede validar la implementación de un algoritmo sin demostrar que el algoritmo mejora la colaboración real.

Una familia de investigación insignia compara, bajo presupuestos equivalentes:

```text
one strong worker
vs one small worker
vs replicated workers
vs heterogeneous workers
vs specialized roles
vs task/evidence DAG teams
```

Entre los resultados importantes se incluyen la corrección, el éxito en pruebas ocultas, las regresiones, la correlación de errores, el tiempo de revisión humana, el uso de cómputo/recursos, la latencia, los conflictos de integración, la calidad de la procedencia y el trabajo útil verificado por unidad de atención/costo escasos.

Consulta [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md), [`docs/research/`](docs/research/README.md) y [`experiments/`](experiments/).

## Principios del proyecto

**La comunidad primero.** La experiencia de los colaboradores, la capacidad de revisión y la escalabilidad del liderazgo son restricciones de ingeniería.

**Una propuesta no es una prueba.** La confianza humana o de la IA no sustituye a la evidencia.

**La popularidad no es corrección.** Los votos, las estrellas, la reputación o el acuerdo correlacionado entre modelos no pueden anular comprobaciones fallidas.

**Más agentes no son automáticamente mejores.** La diversidad, la independencia, la calidad de la descomposición y la capacidad de verificación importan más que el conteo bruto.

**La incertidumbre es un dato.** Los objetivos en competencia y las hipótesis sin resolver deben permanecer explícitos cuando la evidencia es insuficiente.

**La generación no debe superar a la verificación.** El volumen de producción es perjudicial si el proyecto no puede revisarlo, reproducirlo y mantenerlo.

**Integra antes de reinventar.** Reutiliza estándares abiertos para capacidades genéricas y mantén la semántica específica de IDKMesh en la capa de coordinación/evidencia.

**La escala debe ganarse.** Los resultados simulados o a pequeña escala no deben publicitarse como garantías a escala de Internet.

**La procedencia criptográfica va antes que blockchain.** Añade infraestructura de confianza más pesada solo cuando un modelo de amenaza demostrado lo requiera.

**La autoridad canónica permanece externa a generadores y verificadores.** La integración protegida es un límite de decisión separado.

## Guía del repositorio

### Nuevo colaborador

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — flujo de contribución y comprobaciones.
- [`COMMUNITY.md`](COMMUNITY.md) — vías de participación y escalera de colaboradores.
- [`SUPPORT.md`](SUPPORT.md) — cómo pedir ayuda.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — expectativas de la comunidad.
- [`SECURITY.md`](SECURITY.md) — reporte de vulnerabilidades.

### Comprender el sistema

- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — capas de framework, investigación, comunidad, aplicación de referencia y autoalojamiento.
- [`ITERATION_MODEL.md`](ITERATION_MODEL.md) — vocabulario canónico de evolución y flujo de autoridad.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — mapa de arquitectura actual.
- [`EVOLUTION.md`](EVOLUTION.md) — estrategia, base implementada y próximas puertas.
- [`ROADMAP.md`](ROADMAP.md) — progresión condicionada a evidencia desde el estado actual.
- [`docs/README.md`](docs/README.md) — navegación curada de la documentación.

### Contratos e interoperabilidad

- [`schemas/README.md`](schemas/README.md) — contratos legibles por máquina actuales y reglas de versionado.
- [`docs/specifications/`](docs/specifications/README.md) — índice de protocolos/especificaciones.
- [`interop/`](interop/) — límite de adaptador neutral respecto al protocolo, mapeos A2A/MCP, vinculación de identidad y ayudantes de conformidad.
- [`IDKIPS.md`](IDKIPS.md) — proceso de propuestas de mejora mayores.

### Investigación y evidencia

- [`docs/research/`](docs/research/README.md) — programas de investigación y evidencia.
- [`sim/`](sim/) — código de simulación/análisis determinista.
- [`experiments/`](experiments/) — definiciones de experimentos, harnesses y herramientas de resultados.
- [`docs/audits/`](docs/audits/) — auditorías acotadas y evidencia de salud del repositorio.
- [`docs/findings/`](docs/findings/) — hallazgos de investigación e ingeniería.

### Comunidad, gobernanza y memoria del proyecto

- [`GOVERNANCE.md`](GOVERNANCE.md) y [`CONSTITUTION.md`](CONSTITUTION.md) — autoridad y principios protegidos.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — experimento de crecimiento comunitario ACE y salvaguardas.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — reglas de operación de todo el repositorio.
- [`docs/conversations/`](docs/conversations/README.md) — historial de colaboración estructurado y de solo anexado (append-only).

## Registro público del proyecto

El repositorio es el registro duradero del proyecto. Las conclusiones importantes del trabajo del proyecto deben promoverse a la arquitectura, especificaciones, decisiones, hallazgos, evidencia de investigación, gobernanza o implementación actuales — no quedarse solo en chats ni enterradas en notas históricas.

Los registros históricos siguen siendo valiosos, pero no deben anular silenciosamente los documentos canónicos actuales. Consulta [`PROJECT_RULES.md`](PROJECT_RULES.md) y [`docs/README.md`](docs/README.md) para conocer la jerarquía documental.

## Licencia

Apache License 2.0. Consulta [`LICENSE`](LICENSE).

## Invitación

IDKMesh parte de una admisión sencilla: **todavía no sabemos cuál es la mejor manera de coordinar la inteligencia a esta escala.**

Si puedes mejorar una pregunta, refutar un supuesto, reproducir un experimento, escribir una prueba, encontrar un problema de seguridad, aclarar un contrato, reducir la carga de revisión, mejorar la incorporación de nuevos colaboradores o construir un componente verificado, puedes contribuir.

> **De la incertidumbre a la inteligencia colectiva — a través de la evidencia.**
