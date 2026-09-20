# Review — *Reviewer Count Is Not Evidence Count: Measured Error Dependence in an Executable Verification Panel*

**Reviewer:** senior-reviewer pass (mska-scientific-paper-reviewer)
**Date:** 2026-09-09

---

## 1. Scope and evidence coverage

- **Manuscript:** `/home/mohsen/scratch/repos/idkmesh/paper/main.pdf`, 11 pages, built 2026-09-09 from `main.tex` (38 KB) + `refs.bib` (17 entries).
- **Review depth:** deep audit (standard review plus quantitative recomputation from the raw artifacts and a citation pass).
- **Paper type and domain:** empirical software-engineering measurement study, with a simulation component. Domain modules applied: *empirical/ML* and, for §7.2, *anomaly detection & predictive modeling* (baseline parity, confounding).
- **Target venue:** arXiv preprint (cs.SE / cs.MA), stated intent to resubmit to ICSE/FSE. A submission verdict is therefore appropriate; this is **not** a developmental draft.
- **Access:** manuscript text — **complete**. Figures/tables — **complete** (all three figures and all nine tables inspected at page-level rendering; Figures 2 and 3 re-read individually for legibility). Supplement — n/a. References — **complete**; all 16 verified against primary sources.
- **Additional evidence used:** the underlying artifacts (`E017-partial-oracle-votes.jsonl.gz`, `benchmarks/e016-verification-corpus/tasks.jsonl`, `E015-verification-phase-diagram.jsonl`) and the analysis code (`sim/e016_analyze.py`, `sim/e020_quorum_frontier.py`) were read and re-executed. This is a stronger evidence base than a normal reviewer has, and several findings below depend on it.

**Conflict of interest — disclosed.** This manuscript was drafted by the same assistant session that is now reviewing it. The review was therefore run adversarially against the artifacts rather than against the prose, and every headline number was recomputed from raw votes rather than read from the paper. Readers should still discount for the structural conflict.

---

## 2. Executive assessment

**Provisional recommendation: Weak Reject** (major revision required before submission).
**Recommendation confidence: Medium-High.**

Three findings drive this. First, the paper's headline quantity — "25 nominal verifiers are worth `n_eff = 1.00`" — **is not a measurement but a clamp**: `effective_n()` returns `1.0` unconditionally whenever the measured panel error is at or above single-verifier error, and it returns the same `1.0` for a physically absurd input error of `0.9` (**F1**). Second, and consequently, the metric-validation claim in §3.3 that the `ρ = 1` column "collapses to exactly 1.00 at every panel size, neither having been fitted" is **false as written** — that endpoint is produced by the clamp, by construction (**F2**). Third, the paper reports **no uncertainty anywhere**: the headline compares `0.2083` against `0.2044` on 72 items, where the panel error's 95% Wilson interval is `[0.1305, 0.3157]`, and a paired exact McNemar test of the panel against its own best member gives `p = 0.1797` — the central contrast is not statistically distinguishable from nothing (**F3**).

None of this is fatal to the research. The instrument (§3.2), the shape result (§5), and the blind-spot result (§6) are genuinely good, survive scrutiny, and are the paper's real contribution. The honest restatement of the headline is in fact **stronger** than the current one: the panel is not "worth one verifier", it is *worse than a single average verifier and worse still than its best member*. What must go is the false precision of `1.00` and the unearned claim that the metric was validated at both endpoints.

**What would change the recommendation:** replacing the clamped `n_eff` headline with the direct error comparison plus intervals; adding the trivial-baseline and best-member comparisons the paper itself demands of others (**F4**, **F5**); making §4.3's rule conditional (**F6**); and citing and reconciling the concurrent work (**F8**). These are revisions of framing and statistics, not new experiments.

---

## 3. Contribution–evidence map

| Contribution / strong claim | Location | Evidence offered | Status | Reviewer note |
|---|---|---|---|---|
| Instrument with execution-decided ground truth; 25/25 verifiers discriminate | §3.2, p.3–4 | Youden's *J*, Bonferroni-corrected | **Supported** | The strongest part of the paper. Screen is the right one. |
| LLM panel could not be measured; 0/20 discriminate | §3.1, p.3 | Mean *J* = +0.0487, permutation *p* = 0.13 | **Supported** | Valuable negative result, honestly framed. |
| Declared independence label under-predicts dependence (0.892 within vs 0.526 across) | §4.1, p.4 | 300 pairwise correlations | **Supported** | Recomputed; correct. |
| "25 verifiers are worth one" (`n_eff = 1.00`) | §4.2, p.4 | Table | **Contradicted** | `1.00` is a clamp (F1). True relation: panel *worse* than mean and best member. |
| Metric anchored, not fitted; both endpoints fall out of measurement | §3.3, p.4 | ρ=0 and ρ=1 columns | **Partially supported** | ρ=0 endpoint genuine; ρ=1 endpoint is the clamp (F2). |
| Design-effect heuristic overstates independence in 441/441 cells | §4.3, p.5 | Simulation grid | **Partially supported** | True *conditional on* the item-difficulty model; stated unconditionally (F6). Contradicted empirically by Kohli 2026 (F8). |
| Shared shock has the wrong *shape*; cannot produce partial failure | §5.2, p.6 | Fig. 2; 11 obs / 11.1 / 0.01 | **Supported** | Recomputed exactly. Best result in the paper. |
| Irreducible blind-spot floor λ = 0.0556 | §6, p.7 | Quorum frontier; 4/72 | **Supported**, thinly | Rests on 4 items; no interval given (F3). |
| Group balancing never wins under shared difficulty | §7.1, p.8 | Simulation table | **Supported** | Simulation-only; correctly labelled. |
| "Correlation, not accuracy, is the exploitable surface" (0 vs 58) | §7.2, p.8–9 | Two-panel contrast | **Partially supported** | Two variables differ, not one (F7). |

---

## 4. Specific strengths

1. **The instrument is the right answer to a real problem.** Using partial test oracles with execution-decided ground truth sidesteps the judgement-call ground truth that limits most LLM-judge work. Every error is a genuine missed defect. This is a genuine methodological contribution and should be the paper's front-line claim.
2. **§3.1 is exemplary scientific hygiene.** Reporting the failed LLM experiment, diagnosing *why* accuracy hid it on an unbalanced corpus, and deriving the Youden-*J* screen as a precondition is exactly the kind of negative result the field under-publishes. Keep it prominent.
3. **The shape result (§5.2) is the paper's best science.** The partial-failure diagnostic — 11 observed, 11.1 under per-item difficulty, 0.01 under shared shock, *at matched parameter count* — is a clean, well-controlled discriminating test between two models. Figure 2's magnified lower panel shows it honestly.
4. **The correlation/blind-spot distinction (§6) is conceptually sharp** and operationally actionable: decorrelating fixes one, only a different *kind* of verifier fixes the other. No prior work located in the citation pass makes this separation.
5. **Reproducibility is unusually good.** Figures are generated by importing the same analysis modules the experiment records use, so figure–text drift is structurally prevented. All artifacts committed; all commands given.
6. **Threats to validity (§8) is candid**, particularly the admission that the panel's diversity is constructed. Most papers would bury this.

---

## 5. Prioritized findings

| ID | Severity | Conf. | Area | Location | Finding and evidence | Why it matters | Smallest concrete fix |
|---|---|---|---|---|---|---|---|
| **F1** | **Critical** | High | Correctness | §4.2 table, p.4; `sim/e016_analyze.py:90–91` | The headline row reads "**measured** effective size `n_eff` **1.00** (of 25 nominal)". `effective_n()` begins `if measured_err >= errs[0]: return 1.0`. Panel error `0.2083` ≥ single-verifier `0.2044`, so the clamp fires. Verified: `effective_n(0.2083, 0.7956) = 1.0`, and `effective_n(0.9, 0.7956) = 1.0` — the same answer for an absurd input. | The paper's title and central number rest on a floor value presented as a measurement. A reviewer who reads the code will treat this as misrepresentation. | Report the direct comparison instead: panel `0.2083` vs mean member `0.2044` vs best member `0.1389`, and state "`n_eff` is below the metric's floor of 1" rather than "= 1.00". This is a *stronger* claim. |
| **F2** | **Critical** | High | Correctness | §3.3, p.4 | "the `ρ = 1` column collapses to exactly 1.00 at every panel size, neither having been fitted; both fall out of the measurement." The ρ=1 endpoint is the F1 clamp: at ρ=1 simulated panel error (0.251978) ≥ single-verifier error (0.25), so 1.0 is returned by construction. 28 of 315 E015 cells at q=0.5 (8.9%) sit exactly on the clamp. | An explicitly claimed validation property of the paper's central metric is an artifact. This is the kind of finding that ends a review. | Delete the ρ=1 half of the validation claim. Keep the ρ=0 half — recovering 2.98→20.99 is genuine and unclamped. Disclose both the lower clamp and the `nmax=201` upper clamp in the metric definition. |
| **F3** | **Critical** | High | Statistics | Abstract, §4.2, §6 | No confidence interval, standard error, or significance test appears anywhere in the paper. Recomputed: panel error 15/72, 95% Wilson `[0.1305, 0.3157]`; best-member error 10/72, `[0.0772, 0.2371]`; panel-vs-best paired exact McNemar `p = 0.1797`. λ = 0.0556 rests on 4 items. | The headline difference (0.2083 vs 0.2044) is ~0.004 on 72 items — far inside noise. Concurrent work reports bootstrap CIs; this paper will be compared directly and unfavourably. | Add Wilson intervals to every proportion, a McNemar test for the panel-vs-member contrast, and a bootstrap CI for λ. Then state plainly which claims survive: the *ordering* is suggestive, the *magnitude* is not established. |
| **F4** | **Major** | High | Evaluation | §4.2, p.4 | The panel is compared only to the **mean** verifier (0.2044). The **best** verifier errs on 10/72 = **0.1389** — 33% relatively better than the panel. This comparison is absent from the paper. | It both understates the paper's own result and omits the comparison the closest concurrent work makes ("best single judge matches or outperforms the full panel"). Its absence looks like selection. | Add a best-member row to the §4.2 table and to the abstract, with the McNemar *p* from F3. |
| **F5** | **Major** | High | Evaluation | §6, Fig. 3, p.7 | §3.1 correctly insists a panel must be screened against a constant rule ("always reject" scores 0.639 accuracy). That screen is never applied to this paper's own quorum frontier. Recomputed: always-reject error = 26/72 = **0.3611**; the panel's frontier does **not** beat it until `need = 6` (errors at need 1–5: 0.4167, 0.3889, 0.3889, 0.3750, 0.3611). At need = 5 the panel exactly *ties* a rule that never reads the code. | The paper applies a standard to others that it does not apply to itself. A reviewer will find this quickly and it damages the §3.1 argument by association. | Draw the always-reject baseline as a horizontal line on Figure 3, state the `need = 6` crossing in §6, and note that majority (need = 13) and unanimity do clear it comfortably. |
| **F6** | **Major** | High | Reasoning | §4.3, p.5 | "The rule that follows is **unconditional**: do not size a verification panel with `N/(1+(N−1)ρ)`." The 441/441 figure is obtained by simulating under the per-item-difficulty model and comparing against a heuristic derived under different assumptions. That is a disagreement between two models, not an empirical falsification. The single real-panel data point (1.66 vs a *clamped* 1.00) is n = 1 panel and inherits F1. | The paper's most quotable prescriptive claim is circular as argued, and is stated at a confidence the evidence cannot carry. | Restate conditionally: "*under the item-difficulty shape*, the heuristic overstates independence in every cell; whether that shape holds is panel-specific and must be measured." Remove the word "unconditional". |
| **F7** | **Major** | High | Confounding | §7.2 table, p.8 | The text says the two panels differ "*only* in correlation and blind spot" — which is two variables — and then the section title and conclusion attribute the 0-vs-58 catastrophe gap to **correlation**. Correlation moves 0 → 0.4513 *and* blind spot moves 0 → 0.0556 simultaneously. | The headline "Correlation, not accuracy, is the exploitable surface" is not supported by a two-factor change; the blind spot is an equally valid explanation and §6 argues it is a *distinct mechanism*. | Either run the third cell (correlation on, blind spot off), or retitle to "*dependence structure*, not accuracy" and say explicitly that the design cannot separate the two components. |
| **F8** | **Major** | High | Novelty / prior work | §2, §4 | Concurrent work not cited: Kohli, *"Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels"*, arXiv 2605.29800, 28 May 2026. It reaches the same headline (9 judges → `n_eff` 2.18), makes the best-single-judge comparison (F4), reports an all-wrong excess (51/1000 = 5.1%, vs this paper's 4/72 = 5.6%), and claims "the first item-level measurement of effective independence in a judge evaluation setting". Critically, it **empirically validates the Kish heuristic** (`n_eff(k)` tracks `k/(1+(k−1)·0.391)`; eigenvalue estimate 2.16 ≈ Kish 2.18) and its permutation test **rejects shared item difficulty** as the explanation for its correlation (*p* < 10⁻⁴; only 6.8–13.5% of the gap). | Priority on the framing is lost, and two of this paper's claims are in direct tension with published evidence. Submitting without addressing it invites a desk-level novelty objection. | Cite it in §2; drop any first-measurement framing; use it to *support* the paper's own construct-validity threat (their result is evidence that item-difficulty dominance here is partly manufactured by the 5-region design); and position this work as the executable-ground-truth complement in a different regime. |
| **F9** | Moderate | Medium | Construct validity | §3.2, p.3 | Verifiers accept a candidate iff it matches a **reference implementation** on drawn inputs; ground-truth viability is the exit status of **hidden tests**. The relationship between the reference implementation and the hidden tests is never stated. If they share provenance, verifier errors and label errors are not independent. | Potential circularity in the ground truth — the one thing the paper sells as its advantage over judgement-based labels. | One paragraph in §3.2 stating how reference implementations and hidden tests were produced and whether they share code or authorship. |
| **F10** | Moderate | High | Generalization | throughout | Every *real* measurement in the paper comes from **one panel** on **one corpus** of 72 items from 24 problems. The "441/441" and "63,000 runs" figures give an impression of breadth that belongs to simulation under an assumed model, not to measurement. | §8 concedes this, but the abstract and §4.3 do not, and readers stop at the abstract. | Add "one panel, 72 items" to the abstract's scope sentence; label the 441/441 result as simulation in situ, not only in §8. |
| **F11** | Moderate | High | Figure accuracy | Fig. 1 caption, p.5 | "The curves are close together for most of the range." Measured spread across n = 3…21: 18.01 at ρ=0, 7.91 at ρ=0.125, 4.76 at ρ=0.25, falling below 2.00 only from ρ=0.5. | The caption overstates the effect the figure shows at low correlation, which is where panel-size decisions are actually made. | Rewrite: "the curves converge from ρ ≈ 0.5 upward; below that, panel size still matters substantially." |
| **F12** | Moderate | Medium | Metric transparency | §3.3, p.4 | The definition mentions linear interpolation between bracketing odd sizes but discloses neither the lower clamp (F1) nor the `nmax = 201` upper clamp, which returns `201.0` for very low error. | A metric with two silent saturation points cannot be reused by readers as specified. | State both clamps and their firing conditions in the definition; report how many cells hit each. |
| **F13** | Minor | High | Presentation | §4.2, §5.1 tables | Tables report bare point estimates with 4 decimal places and no dispersion, implying precision the 72-item sample cannot support. | False precision. | Fold in F3's intervals; reduce to 3 decimals where the interval is ±0.09. |
| **F14** | Minor | Medium | Framing | Title, §10 | "Reviewer Count Is Not Evidence Count" is a strong general claim; the evidence is one constructed panel of automated oracles, and the closest concurrent work reaches ~2 effective votes rather than ~1. | Title over-generalizes from n = 1 panel. | Consider narrowing, e.g. "…in an Executable Verification Panel" is already in the subtitle — let the subtitle do more work in the abstract's first sentence. |

### Questions for the author

- **Q1.** Were the reference implementations used by the partial oracles written independently of the hidden test suites that decide `viable`? (Bears on F9.)
- **Q2.** Does `sim/e017_verify.py --seeds 5` reproduce `E017-partial-oracle-votes.jsonl.gz` bit-for-bit, or only in distribution? §9 implies the former; the repository's own records note that frozen artifacts are not always bit-reproducible.
- **Q3.** Is there a principled reason the analysis uses `e020_quorum_frontier.py`'s moment fit while the E017 record uses a different fit (11.1 vs 11.2, 2.3 vs 2.1, 8.5 vs 8.6)? The paper is internally consistent, but it silently differs from the cited experiment record.

### Optional enhancements (not required)

- A second panel with a *different* diversity construction (e.g. mutation-based oracles) would convert F10 from a limitation into a finding, and would directly test whether item-difficulty dominance is manufactured.
- Reporting Fleiss' κ alongside mean pairwise ρ would let readers connect to the inter-rater literature already cited.

---

## 6. Section-level review

**Title / abstract.** See F14, F10. The abstract states five point estimates as findings with no dispersion (F3) and asserts the 441/441 result without marking it as simulation (F10).

**§1 Introduction.** Well-constructed; the Knight–Leveson framing is apt and honest ("Our contribution here is not the model"). No new findings.

**§2 Related work.** Accurate and correctly scoped, but stops at 2023 for the LLM-judge line and misses the directly competing 2026 work (F8). The Kuncheva characterization ("diversity measures correlate with ensemble gain far less reliably than intuition suggests") was checked against the source and is fair.

**§3 Instrument.** §3.1 is a strength. §3.2 needs F9. §3.3 contains F2 and F12.

**§4 Measurement.** §4.1 is sound. §4.2 contains F1, F3, F4. §4.3 contains F6 and F10.

**§5 Shape.** The strongest section. One note: the "417× too low" figure for the independent model is arithmetically right (0.2083/0.0005) but is a ratio of a small denominator and would read better as "essentially zero probability under independence".

**§6 Quorum frontier.** Contains F5. The mechanism discussion (shared shock → floor ρμ; beta-binomial → n^−β decay; reality → λ) is clear and correct, and is the paper's most original argument.

**§7 Consequences.** §7.1 is fine and correctly labelled as simulation. §7.2 contains F7. The "accept rate inverts the ranking" observation is genuinely useful and well flagged.

**§8 Threats.** Candid and unusually complete. Its weakness is that several concessions (constructed diversity, one panel, base-rate dependence) are *only* here, while the abstract and body assert without them (F10).

**§9 Reproduction.** Good. See Q2.

**§10 Conclusion.** Inherits F1, F6. "Do not apply N/(1+(N−1)ρ)" must be conditionalized.

**Figures.** Fig. 1 — caption overstates (F11); otherwise legible and correctly labelled. Fig. 2 — the two-panel construction with the magnified `13 ≤ k ≤ 24` region is the right design and the caption's definition of partial failure is correct. Fig. 3 — clear, but needs the trivial baseline (F5) and would benefit from a CI band (F3).

---

## 7. Quantitative and cross-section audit

| Item | Locations compared | Recalculation | Assessment | Fix |
|---|---|---|---|---|
| Panel majority error | Abstract, §4.2, §5.1, §6 | 15/72 = 0.20833 | **Consistent** everywhere | — |
| Single-verifier error | §4.2 | 1 − 0.7956 = 0.2044 (mean) | Correct, but it is the **mean**, not a member (F4) | Label it "mean member" |
| Best-member error | *absent* | 10/72 = 0.1389 | **Missing** (F4) | Add |
| `n_eff` = 1.00 | §4.2 | Clamp, not measurement | **Contradicted** (F1) | Replace |
| Design-effect heuristic 1.66 | §4.2 | 25/(1+24×0.5873) = 1.664 | Correct arithmetic | Keep; reframe per F6 |
| Partial / unanimous failures | §5.2 table, Fig. 2 | 11 / 11.11 / 0.014 and 4 / 2.26 / 8.54 | **Consistent** with the paper's 11.1 / 0.01 / 2.3 / 8.5 | — |
| λ = 0.0556 | Abstract, §6 | 4/72 = 0.05556 | Correct; no interval (F3) | Add CI |
| RMSE 0.0766 / 0.0251 / 0.0328 | Fig. 3 caption | Reproduced exactly | **Consistent** | — |
| 15→21 delta at ρ=0.5 | §4.3 | 3.92 → 3.98 = +0.053 | Paper says +0.05 — **correct** | — |
| ρ = 0.125 caps 21-panel at 10.6 | §4.3 | max over grid = 10.62 | **Correct** | — |
| "417× too low" | §5.1 | 0.2083/0.0005 = 416.6 | Correct | Consider rephrasing |
| always-reject baseline | *absent* | 26/72 = 0.3611; crossed at need = 6 | **Missing** (F5) | Add |
| Uncertainty on any proportion | *absent* | Wilson CIs computed above | **Missing** (F3) | Add |

No unit, denominator, or terminology drift was detected across sections; the notation (`n`, `p`, `ρ`, `q`, `need`, `λ`, `icc`) is used consistently. Absence of detected inconsistency is not proof of correctness.

---

## 8. Citation integrity

**Coverage: 16/16 checked** (100%). Selection rule: all entries, since the bibliography is small and every entry carries either a novelty contrast or a methodological borrowing. Sources: publisher records (IEEE/ACM/Springer/Oxford/Wiley), PubMed, and one award announcement.

| Claim and location | Cited source | Status | Note |
|---|---|---|---|
| Per-input difficulty model origin, §2 | Eckhardt & Lee 1985, TSE SE-11(12):1511–1517 | **Verified** | Volume/pages/year correct; characterization fair |
| Independence assumption failed empirically, §1–2 | Knight & Leveson 1986, TSE 12(1):96–109 | **Verified** | "27 versions… same specification" confirmed |
| Diverse-methodology extension, §2 | Littlewood & Miller 1989, TSE 15(12):1596–1614 | **Verified** | — |
| N-version programming origin, §1 | Avizienis & Chen 1977, COMPSAC, 149–155 | **Verified** | Author order confirmed (Avizienis first) |
| Design effect, §1, §2 | Kish 1965, *Survey Sampling* | **Verified** | Correct attribution; see F6 on its use |
| Beta-binomial for over-dispersed binary data, §2, §5.2 | Williams 1975, *Biometrics* 31:949–952 | **Verified** | — |
| Condorcet under correlated votes, §1–2 | Ladha 1992, AJPS 36(3):617–634 | **Verified** | — |
| Majority systems, §1–2 | Boland 1989, *JRSS D* 38(3):181–189 | **Verified** | Journal name corrected during this pass |
| Discrimination index, §3.1 | Youden 1950, *Cancer* 3(1):32–35 | **Verified** | — |
| Diversity–accuracy relationship, §2 | Kuncheva & Whitaker 2003, *Mach. Learn.* 51(2):181–207 | **Verified** | Paper's characterization matches the source's own conclusion |
| Rater concordance, §2 | Fleiss 1971, *Psych. Bull.* 76(5):378–382 | **Verified** | — |
| Code review coverage/participation, §2 | McIntosh et al. 2014, MSR, 192–201 | **Verified** | Subtitle added during this pass |
| Modern code review, §2 | Bacchelli & Bird 2013, ICSE, 712–721 | **Verified** | — |
| LLM-as-judge, §2 | Zheng et al. 2023, NeurIPS | **Verified** | — |
| Execution-based benchmarks, §2 | Chen et al. 2021, arXiv:2107.03374 | **Verified** | — |
| Artifacts, §9 | IDKMesh repository | **Verified** | Public, artifacts present |
| **Missing** | Kohli 2026, arXiv 2605.29800 | **Omitted** | See F8 — present in `refs.bib` but uncited in the text |

No fabricated, mis-attributed, or unverifiable citation was found. The bibliography's accuracy is a genuine strength.

---

## 9. Reproducibility and artifact readiness

Strong overall. All five commands in §9 were executed during this review and all completed successfully; the E017, E018, and E020 analyses reproduce the paper's numbers exactly, and `paper/make_figures.py` regenerates all four data files. The repository's full gate (1661 tests passed / 2 skipped, link check clean, observatory clean) passes with `paper/` present.

Gaps: (i) no environment/version pinning is stated (Python version, OS) — the analyses are pure standard library, which mitigates but does not remove this; (ii) the bit-reproducibility of the regenerated vote artifact is asserted but not demonstrated (Q2); (iii) the LLM experiment of §3.1 gives no model checkpoints, quantization, sampling parameters, or serving versions, so it is *reported* but not *reproducible* — acceptable for a negative result, but it should say so.

---

## 10. Prose quality and submission cleanup

Prose is clear, unusually concrete, and largely free of padding. Meaning-affecting items only:

| Location | Observable issue | Effect | Revision direction |
|---|---|---|---|
| §4.2, p.4 | "**measured** effective size" | Labels a clamp as a measurement | See F1 |
| §3.3, p.4 | "neither having been fitted" | Asserts validation that half-fails | See F2 |
| §4.3, p.5 | "The rule that follows is **unconditional**" | States a conditional result unconditionally | See F6 |
| §7.2, p.8 | "differing **only** in correlation and blind spot" | "only" contradicted by the same sentence naming two factors | See F7 |
| Fig. 1 caption | "curves are close together for most of the range" | Overstates convergence where it matters least | See F11 |
| §5.1 | "417× too low" | Ratio against a near-zero denominator reads as spurious precision | "essentially zero under independence" |

**Cleanup sweep:** no TODO/FIXME/placeholder markers, no duplicated passages, no broken cross-references (LaTeX log: 0 undefined references, 0 overfull boxes), no orphaned sections. Every figure and table is referenced in the text. No anonymization leaks — the paper is correctly non-anonymous for arXiv, but note that ICSE/FSE resubmission is **double-blind** and the author block, the `mskazemi.github.io` link, and the `github.com/MSKazemi/idkmesh` data-availability URL would all need masking.

---

## 11. Rejection-risk view

| Likely attack point | Evidence / location | Why it could drive rejection | How to defuse |
|---|---|---|---|
| "Your headline number is a clamp" | §4.2; `e016_analyze.py:90–91` | Reviewer reads the artifact and finds the central quantity is a floor value labelled a measurement. Near-certain rejection if found and unexplained. | F1 — restate as the direct error comparison, which is stronger |
| "No statistics on 72 items" | Abstract, §4.2 | A 0.004 difference presented as a headline with no CI, against concurrent work that reports bootstrap intervals | F3 |
| "Concurrent work did this in May" | §2 | Novelty framing collapses; reviewer may not read further | F8 — cite, differentiate on instrument and shape |
| "You didn't apply your own screen" | §3.1 vs §6 | Directly self-inconsistent; embarrassing because §3.1 is otherwise the paper's ethical high ground | F5 |
| "Your Kish result is circular / contradicted" | §4.3 | Conditional result stated unconditionally, and Kohli validates Kish empirically | F6 |
| "n = 1 panel, constructed diversity" | §8 | External validity; already conceded, so it wounds rather than kills — unless the abstract keeps over-claiming | F10 |

---

## 12. Ordered revision plan

**1 — Must fix before submission (correctness and central evidence).**
1. **F1.** Remove `n_eff = 1.00` as a measured headline. Replace with: panel 0.2083, mean member 0.2044, best member 0.1389, and the statement that `n_eff` is below the metric's floor. Retitle §4.2 accordingly ("the panel is worse than its members").
2. **F2.** Delete the ρ=1 half of the §3.3 validation claim; keep and keep claiming the ρ=0 half. Disclose both clamps (F12).
3. **F3.** Add Wilson intervals to every reported proportion, a McNemar test for the panel-vs-member contrast, and a bootstrap CI for λ. Say explicitly which claims survive the intervals and which are directional only.
4. **F6.** Conditionalize the design-effect rule; delete "unconditional".
5. **F8.** Cite Kohli 2026; remove first-measurement framing; add a short subsection reconciling the two panels' opposite findings on Kish and item difficulty.

**2 — Should fix (credibility and interpretation).**
6. **F4** best-member comparison; **F5** always-reject baseline on Figure 3 and in §6; **F7** de-confound or retitle §7.2; **F9** state reference-implementation/hidden-test provenance; **F10** move the scope caveats into the abstract.

**3 — Polish.**
7. **F11** Figure 1 caption; **F12** metric clamps in the definition; **F13** decimals; **F14** title scope; the "417×" rephrasing; double-blind masking if ICSE/FSE.

---

### Closing note

This is a well-built, honestly-reported piece of empirical work sitting behind a headline it cannot support. The instrument, the shape result, and the correlation/blind-spot distinction are real contributions that survive every check I ran; the `n_eff = 1.00` framing does not, and it is load-bearing for the title, the abstract, and §4. The good news is that the corrections all point the same way: the panel is *worse* than its members, not merely equal to one, and saying so with intervals is both more defensible and more striking than the current claim. Fix the clamp, add the statistics, cite the concurrent work, and apply to §6 the same screen §3.1 applies to everyone else — and this becomes a solid preprint whose remaining weakness is honest scope rather than misstated evidence.
