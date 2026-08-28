# Conversation Record — References, Crypto Lessons, and Mandatory GitHub Archiving

Date: 2026-08-28
Repository: https://github.com/MSKazemi/idkmesh

## Purpose

This record preserves the substantive content and project actions from the conversation about IDKMesh next steps, reference projects/websites, Bitcoin/crypto-inspired distributed-system ideas, and the project owner's explicit rule that IDKMesh chat content must always be preserved in the public repository.

---

## Project-owner question

The project owner asked what the next steps should be for IDKMesh, what references, websites, projects, and places should be studied, and whether ideas from cryptocurrency and Bitcoin-style distributed systems should be used in the project.

Original visible request:

> https://github.com/MSKazemi/idkmeshwhat are the next steps and which reference we can use or we should use which website which places we should check can we use doing needed to use also the crypto and bitcoins related distributed idea for this project

---

## Assistant findings and recommendation

The repository was inspected first. Existing durable project artifacts already included `ROADMAP.md`, `BLOCKCHAIN_STRATEGY.md`, `MATHEMATICAL_FOUNDATIONS.md`, `SCIENTIFIC_FOUNDATIONS.md`, `RESEARCH_QUESTIONS.md`, `GOALS.md`, and other project records.

The central recommendation was:

> IDKMesh should study Bitcoin and crypto systems deeply, but reuse their distributed-systems ideas before reusing their monetary layer.

### Immediate implementation order

1. Complete WorkUnit v0 and ResultManifest v0 (issue #3).
2. Complete ProjectManifest and DomainPack interfaces (issue #6).
3. Build the single-machine multi-worker orchestrator (issue #4).
4. Build an independent validator and benchmark set (issue #5).
5. Run Experiment #2: many small coding agents versus one strong model.
6. Add cryptographic provenance: hashes, signatures, signed WorkUnits/results, append-only event records/transparency mechanisms.
7. Build a first 3–10 node network using an existing P2P stack rather than inventing a transport protocol.
8. Run adversarial tests for churn, partitions, poisoned outputs, Sybil workers, collusion, replay, malicious coordinators, and forged contribution claims.
9. Only after useful distributed work exists, investigate compute credits, markets, economic settlement, and possible blockchain use.

### Core architectural principle

The project should follow roughly:

`verification -> schemas -> reproducible execution -> signatures/hashes -> local mesh -> decentralized networking -> multi-operator trust -> economic settlement if required`

The project should not begin with a custom token, proof-of-work mining, or mandatory public-chain dependency.

---

## Bitcoin / crypto lessons identified as useful now

The assistant recommended adopting or studying the following mechanisms early:

- public/private-key identities for workers, verifiers, and coordinators;
- digital signatures on WorkUnits and ResultManifests;
- cryptographic hashes for artifact identity and integrity;
- Merkle trees for compact inclusion/provenance proofs;
- peer discovery;
- gossip-style propagation;
- content addressing;
- explicit adversarial threat models;
- public improvement-proposal processes;
- lightweight inclusion proofs;
- adaptive load/rate-control ideas inspired by difficulty adjustment.

Important distinction:

Bitcoin solves agreement over a shared monetary history among mutually distrustful parties. IDKMesh must solve a different core problem: how to produce and independently verify useful work produced by heterogeneous humans, agents, and computers. Blockchain consensus does not establish whether software, a model output, a scientific claim, or an artifact is correct.

---

## Bitcoin mechanisms mapped to IDKMesh

| Bitcoin / crypto mechanism | IDKMesh analogue | Current recommendation |
|---|---|---|
| peer discovery | worker/coordinator discovery | use early through existing libraries |
| gossip/relay | liveness, task announcements, capability/load summaries | use for selected state |
| public/private keys | worker/verifier/coordinator identity | use early |
| signatures | signed WorkUnits and ResultManifests | use early |
| transaction/content hashes | artifact/result identity | use immediately |
| Merkle trees | provenance/inclusion proofs | use early |
| SPV-like proof idea | lightweight inclusion verification | useful later |
| mempool | pending WorkUnit/task market analogy | useful concept, not direct copy |
| fee market | task priority / scarce-resource bidding | later experiment |
| redundant mining competition | independent redundant solvers | useful only with independent verification |
| proof of work | anti-abuse/resource-cost mechanism | not default execution model |
| difficulty adjustment | adaptive admission/verification requirements | strong control-system inspiration |
| Nakamoto consensus | global canonical adversarial ledger | not needed for early scheduler or verification |
| confirmations | accumulating evidence/confidence | analogy only; not mechanical voting |
| accounting model | contribution/credit accounting | possibly later |
| BIP process | IDKMesh protocol evolution | recommended immediately |

---

## Broader crypto/decentralized projects to study

### Lightning Network

Relevant ideas:

- do not globally settle every local interaction;
- keep frequent interactions local/off-chain;
- route over a graph;
- publish/settle only compact globally important facts.

IDKMesh implication:

`local work interactions -> compact signed provenance/settlement checkpoints`

This supports hierarchical architecture rather than global consensus on every agent message or scheduler update.

### Golem Network

Study:

- requestor/provider abstraction;
- heterogeneous volunteer compute;
- task execution runtimes and isolation;
- provider reputation;
- off-chain compute with economic settlement.

### Akash Network

Study:

- compute-resource marketplaces;
- provider/requestor offers and bids;
- leases;
- economic settlement separated from execution.

### Bittensor

Study cautiously:

- separation between output-producing participants and scoring validators;
- subnet specialization;
- incentive mechanisms tied to scoring.

Primary warning: if the scoring function is gameable, the network rewards gaming rather than useful intelligence. This strongly reinforces IDKMesh's verification-first design.

### Nostr / ActivityPub / federation-style protocols

Study for relays/federation, interoperable protocols, and communities operating independent infrastructure while exchanging standardized messages.

---

## Non-crypto distributed systems to study

### libp2p

Primary networking candidate for experimentation:

- transports;
- peer discovery;
- NAT traversal;
- DHT;
- secure channels;
- multiplexing;
- gossip/pubsub.

### IPFS

Relevant for:

- content addressing;
- CIDs;
- Merkle DAGs;
- DHT content routing;
- peer-to-peer artifact distribution.

### BitTorrent

Relevant for scalable swarming distribution of datasets, models/model pieces, build outputs, benchmark bundles, and large artifacts.

### Raft / Paxos family

Relevant for trusted/known coordinator clusters requiring replicated authoritative state. Do not use Byzantine consensus when crash-fault consensus is sufficient.

### PBFT/BFT systems

Relevant later when multiple bounded operators may be malicious and need ordered shared state.

### CRDTs

Relevant for replicated state that can tolerate eventual consistency. Consensus should be reserved for facts that truly require one globally authoritative order.

---

## Distributed computing / AI projects identified as important references

### BOINC

A major historical reference because it addresses:

- heterogeneous volunteer hosts;
- unreliable computers;
- work distribution;
- redundancy;
- result validation;
- accounting/credits;
- malicious or faulty hosts.

### Folding@home

Important operational reference for very large-scale volunteer scientific computing.

### Hivemind / Learning@home

Important for decentralized ML across unreliable Internet-connected computers, including DHT-based coordination and peer-to-peer optimization/averaging.

### Petals

Important for distributed large-model inference/fine-tuning across Internet peers.

### Bacalhau

Important for distributed execution, data locality, intermittent/edge nodes, cross-organization execution, and container/WASM-style workloads.

---

## Software provenance/security references

Recommended systems and standards:

- Sigstore / Rekor;
- in-toto;
- SLSA;
- NIST software-supply-chain and blockchain publications;
- OpenSSF.

Recommended first provenance path:

`hashes -> signatures -> attestations -> append-only transparency log -> independent monitors`

Blockchain is optional later if multi-party trust/settlement requirements cannot be satisfied more simply.

---

## Open-source governance references

Important organizational/governance inspirations:

- Apache Software Foundation;
- Kubernetes community structure and KEP process;
- Bitcoin BIPs;
- BitTorrent BEPs;
- Python PEPs;
- IETF RFC/standards process.

The recommended pattern is:

`idea -> public proposal -> criticism/alternatives -> implementation/experiment -> evidence -> adoption/rejection/supersession`

This was identified as particularly important because IDKMesh intentionally allows contributors with different understandings of the project's evolving goals.

---

## IDKMesh Improvement Proposals (IDKIPs)

The assistant proposed creating an IDKMesh-native improvement-proposal mechanism modeled on BIPs/BEPs/KEPs/PEPs/RFCs.

A proposal should contain:

- problem;
- motivation;
- scope and non-goals;
- proposal;
- alternatives;
- measurable success criteria;
- security/abuse analysis;
- compatibility/migration;
- experiments/evidence;
- dissent/unresolved questions;
- status;
- implementation links.

Repository action completed:

- GitHub issue #7 created: **P0: Establish IDKMesh Improvement Proposal (IDKIP) process**.

---

## Suggested crypto-inspired experiments

### C001 — P2P discovery

Compare static coordinators, bootstrap + peer exchange, and libp2p DHT/rendezvous. Measure join latency, partition recovery, bandwidth, and eclipse-attack susceptibility.

### C002 — Gossip control plane

Propagate selected summaries only: availability, coarse load, capabilities, task digests. Measure convergence and duplicate traffic.

### C003 — Merkle provenance

Build an append-only Merkle log of signed WorkUnit/Result/Verification events. Measure proof size, append throughput, audit cost, and tampering detection.

### C004 — Proof of Verified Useful Work

Do not create a cryptocurrency. Test whether contribution can be scored from independently verified marginal value rather than raw CPU-hours or task counts.

Illustrative form:

`score = verified usefulness - compute cost - review cost - duplication penalty`

### C005 — Adaptive difficulty/admission

Borrow the feedback-control idea from Bitcoin difficulty adjustment. Increase verification/admission requirements when low-quality submissions overwhelm the system and relax them when useful capacity is underutilized. Test stability and gaming resistance.

### C006 — Compute auction

Compare FIFO, priority scoring, auction/bidding, multi-objective scheduling, and fairness constraints for scarce GPU or verifier capacity. No blockchain is required for the initial experiment.

### C007 — Transparency log vs blockchain

When multiple independent operators exist, compare:

1. signed centralized/federated event database;
2. Merkle transparency log;
3. BFT replicated state machine;
4. permissioned ledger;
5. public-chain/L2 anchoring only if justified.

---

## Repository artifact created from this research

A durable findings document was added:

`docs/findings/2026-08-28-reference-map-and-crypto-lessons.md`

Commit:

`9eccab0421431c0475747fc0e688655c251d3f05`

The file contains the reference map, next-step ordering, crypto/Bitcoin lessons, project/reference list, experiments, and current architectural decision.

---

## Project-owner repository rule

The project owner then explicitly clarified that all substantive content from IDKMesh ChatGPT conversations must always be placed in the project's public GitHub repository.

Original visible instruction:

> @GitHub Did you put all of this inside the...https://github.com/MSKazemi/idkmesh Always, this is the rule, always you need to put anything inside this chat, inside the chat in this project in the Git hub repository.

### Interpretation adopted

For every IDKMesh chat where GitHub access is available:

1. preserve substantive user messages and assistant outputs under `docs/conversations/`;
2. promote durable findings/decisions/architecture/code into their canonical project files as appropriate;
3. do this in the same turn where practical;
4. never publish secrets, sensitive/private material, hidden chain-of-thought/internal reasoning, confidential third-party material, or content that cannot legally be redistributed.

### Repository action completed

`PROJECT_RULES.md` was strengthened from a general 'useful outputs should be reflected' rule to a mandatory chat-to-repository preservation rule.

Commit:

`dd2d3c23d6815192af12c48a58551d712a4756db`

This conversation record itself is part of implementing that rule.

---

## Current standing decision

For IDKMesh, the durable project-record rule is now:

> The public GitHub repository is the durable record of substantive IDKMesh conversations. Visible project-relevant chat content should be archived there by default, and lasting findings/decisions should also be integrated into the appropriate canonical project files. Safety, privacy, confidentiality, hidden reasoning, and redistribution constraints override verbatim publication.

