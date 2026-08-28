# Science and Blockchain Source Notes — 2026-08-28

These notes capture external sources used to refine the scientific/physical and blockchain strategy for IDKMesh. They are evidence references, not claims that the source authors endorse IDKMesh.

## Statistical mechanics and optimization

### Kirkpatrick, Gelatt, Vecchi — Optimization by Simulated Annealing

- Science 220, 671–680 (1983)
- DOI: https://doi.org/10.1126/science.220.4598.671
- Relevance: establishes the explicit connection between statistical mechanics/annealing and large combinatorial optimization.
- IDKMesh use: candidate-search, scheduling/configuration experiments, and the exploration-temperature concept.

## Distributed gossip and spectral convergence

### Boyd, Ghosh, Prabhakar, Shah — Randomized Gossip Algorithms

- Stanford project page: https://web.stanford.edu/~boyd/papers/gossip.html
- Relevance: distributed information exchange/averaging under topology changes and limited resources; convergence is linked to spectral properties of the update/network structure.
- IDKMesh use: decentralized summaries, load/liveness propagation, and spectral performance analysis.

## Network robustness and percolation

### Cohen, Erez, ben-Avraham, Havlin — Resilience of the Internet to Random Breakdowns

- Physical Review Letters: https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.85.4626
- Relevance: applies percolation theory to network robustness under random node removal.
- IDKMesh use: churn/failure simulations and critical-connectivity studies.

### Gao, Buldyrev, Havlin, Stanley — Robustness of a Network of Networks

- Physical Review Letters: https://journals.aps.org/prl/abstract/10.1103/PhysRevLett.107.195701
- Relevance: interdependent networks can exhibit cascading failures different from isolated-network behavior.
- IDKMesh use: model dependencies between intelligence, knowledge/task, and compute networks.

## Synchronization

### Rodrigues et al. — The Kuramoto Model in Complex Networks

- Physics Reports: https://www.sciencedirect.com/science/article/pii/S0370157315004408
- Relevance: surveys synchronization of heterogeneous oscillators on complex networks.
- IDKMesh use: research model for local/partial coordination cadence and the costs of over-synchronization.

## Multiscale / renormalization

### Gabrielli et al. — Network Renormalization

- Nature Reviews Physics (2025): https://www.nature.com/articles/s42254-025-00817-5
- Relevance: surveys methods and open challenges for coarse-graining complex networks across levels of resolution.
- IDKMesh use: worker -> local group -> compute island -> regional/global hierarchical architecture and experiments on which information can be safely aggregated.

### Villegas et al. — Laplacian Renormalization Group for Heterogeneous Networks

- Nature Physics: https://www.nature.com/articles/s41567-022-01866-8
- Relevance: diffusion/Laplacian-based coarse graining for heterogeneous networks.
- IDKMesh use: candidate mathematical tool for hierarchy/coarse-graining experiments.

## Thermodynamics of computation

### Bennett — Notes on Landauer's Principle, Reversible Computation, and Maxwell's Demon

- IBM Research: https://research.ibm.com/publications/notes-on-landauers-principle-reversible-computation-and-maxwells-demon
- Relevance: explains the relationship between logically irreversible information operations and entropy generation.
- IDKMesh use: conceptual foundation for treating compute/communication as physical resources and measuring energy per verified useful result. It is not a practical scheduling formula for present laptops.

## Quantum-inspired / tensor methods

### Orús — Tensor Networks for Complex Quantum Systems

- Nature Reviews Physics: https://www.nature.com/articles/s42254-019-0086-7
- Relevance: tensor-network representations developed in quantum many-body physics have applications beyond their original domain.
- IDKMesh use: later research candidate for structured high-order correlations; not a P0 requirement.

### Tensor Networks for Quantum Computing

- Nature Reviews Physics (2025): https://www.nature.com/articles/s42254-025-00853-1
- Relevance: recent review of tensor-network methods across quantum-computing tasks.
- IDKMesh use: keeps future quantum/tensor research grounded in actual technical literature.

### D-Wave — What Is Quantum Annealing?

- https://support.dwavesys.com/hc/en-us/articles/360003680954-What-Is-Quantum-Annealing
- Relevance: describes quantum annealing as a heuristic for combinatorial optimization and sampling through low-energy solutions.
- IDKMesh use: optional future backend for suitable QUBO problems. Strong classical baselines are required before claiming benefit.

## Blockchain and distributed ledgers

### NIST IR 8202 — Blockchain Technology Overview

- NIST: https://www.nist.gov/publications/blockchain-technology-overview
- CSRC: https://csrc.nist.gov/pubs/ir/8202/final
- Relevance: defines blockchains as distributed tamper-evident/tamper-resistant ledgers using validation and consensus, and emphasizes understanding applicability rather than treating blockchain as universal.
- IDKMesh use: foundation for the decision framework in `BLOCKCHAIN_STRATEGY.md`.

### NIST IR 8500A initial public draft — Blockchain-Based Secure Software Assets Management (BloSS@M)

- CSRC: https://csrc.nist.gov/pubs/ir/8500/a/ipd
- Publication date: 2026-05-19
- Relevance: a current NIST concept applying blockchain to software-asset lifecycle provenance, auditability, and security/compliance management.
- IDKMesh use: evidence that cross-organization software provenance is a plausible ledger use case; not evidence that IDKMesh needs blockchain now.

## Transparency logs as a simpler provenance mechanism

### Sigstore Rekor

- Overview: https://docs.sigstore.dev/logging/overview/
- Security model: https://docs.sigstore.dev/about/security/
- Relevance: append-only software-signature transparency log backed by a cryptographically verifiable Merkle tree and independently monitorable consistency.
- IDKMesh use: model for a P0/P1 provenance layer based on signatures + append-only transparency before general-purpose blockchain consensus.

## Working interpretation

The evidence supports the following current hierarchy:

1. graph/distributed algorithms, robust statistics, scheduling, cryptographic provenance, and scientific benchmarking are immediate foundations;
2. statistical-physics and multiscale methods provide concrete experimental models;
3. blockchain is credible for shared provenance/settlement in multi-party trust environments, but simpler transparency logs should be tested first;
4. quantum-inspired optimization can be explored through solver-neutral formulations such as QUBO;
5. actual quantum hardware is a later optional integration and does not change the classical nature of the core mesh.