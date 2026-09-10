from __future__ import annotations

import random


PANEL_DEPENDENCE_SHAPES = {"shared_shock", "item_difficulty"}


def sample_panel_correctness(
    panel_size: int,
    accuracy: float,
    correlation: float,
    shape: str,
    rng: random.Random,
) -> list[bool]:
    """Sample one candidate's verifier-correctness vector.

    This is the sampling counterpart to the two closed-form models in
    ``sim/e018_dependence_models.py``.  ``accuracy`` is the common probability
    that one verifier makes the correct binary decision on the candidate and
    ``correlation`` is the common pairwise correctness/error correlation.

    The two shapes deliberately share canonical endpoint implementations:

    * ``correlation == 0`` -> independent Bernoulli correctness draws;
    * ``correlation == 1`` -> one Bernoulli correctness draw shared by all.

    Consequently both the sampled vector *and RNG state* agree exactly at the
    endpoints for a common seed.  Between them:

    * ``shared_shock`` mixes an all-shared draw with independent draws;
    * ``item_difficulty`` draws a beta-binomial latent error probability using
      the same parameterisation as E018.

    R1 calls this helper only for a real dependent panel.  Its default
    ``panel_dependence_correlation == 0`` path continues through the historical
    verifier code so every committed single-verifier replay keeps its RNG call
    order byte-for-byte.
    """

    if isinstance(panel_size, bool) or not isinstance(panel_size, int) or panel_size < 1:
        raise ValueError("panel_size must be a positive integer")
    if not 0.0 <= accuracy <= 1.0:
        raise ValueError("accuracy must be in [0, 1]")
    if not 0.0 <= correlation <= 1.0:
        raise ValueError("correlation must be in [0, 1]")
    if shape not in PANEL_DEPENDENCE_SHAPES:
        raise ValueError(
            f"shape must be one of {sorted(PANEL_DEPENDENCE_SHAPES)}"
        )

    if accuracy <= 0.0:
        return [False] * panel_size
    if accuracy >= 1.0:
        return [True] * panel_size

    # Canonical endpoint implementations are intentionally shared by both
    # shapes.  Besides matching the same distribution, this lets tests assert
    # exact output and RNG-state equality at rho=0 and rho=1.
    if correlation <= 0.0:
        return [rng.random() < accuracy for _ in range(panel_size)]
    if correlation >= 1.0:
        correct = rng.random() < accuracy
        return [correct] * panel_size

    if shape == "shared_shock":
        if rng.random() < correlation:
            correct = rng.random() < accuracy
            return [correct] * panel_size
        return [rng.random() < accuracy for _ in range(panel_size)]

    # Item-difficulty / beta-binomial model.  Let mu be the marginal error
    # probability.  With scale=(1-rho)/rho, Beta(mu*scale,
    # (1-mu)*scale) has mean mu and intraclass Bernoulli correlation rho.
    mu = 1.0 - accuracy
    scale = (1.0 - correlation) / correlation
    difficulty = rng.betavariate(mu * scale, (1.0 - mu) * scale)
    return [rng.random() >= difficulty for _ in range(panel_size)]
