"""
Suitability scoring engine (works on single plots and on whole raster grids).

Two complementary methods
  1. FAO limiting factor : the land is only as suitable as its worst factor.
     Analogy: a chain is as strong as its weakest link. One N factor makes the land N.
  2. AHP weighted linear combination (WLC): factor scores are averaged with weights
     from expert pairwise comparison. Analogy: a school report card, where some
     subjects count more than others; good grades can partly offset a weaker one.
  In WLC, a weak factor caps the result one class above it, and a factor in class N
  acts as a hard constraint (the report card cannot hide a failing grade).

Factor scores (fuzzy membership in [0, 1]) are piecewise linear across class bands:
  inside S1 band -> 1.0, at the S2 edge -> 0.66, at the S3 edge -> 0.33, beyond S3 -> 0 (N).
"""
from __future__ import annotations

import numpy as np

from .domain import (ClassBreaks, CropProfile, FactorResult, Method, Plot, SuitabilityAssessment,
                     SuitabilityClass)

METHOD_VERSION = "0.1.0"
_EPS = 1e-9
_CLASS_OF_RANK = {3: SuitabilityClass.S1, 2: SuitabilityClass.S2, 1: SuitabilityClass.S3, 0: SuitabilityClass.N}
# Aggregated WLC score thresholds -> class
WLC_THRESHOLDS = ((0.80, 3), (0.60, 2), (0.40, 1))


# ------------------------------------------------------------------ factor level
def _upper_side(v: np.ndarray, e1: float, e2: float, e3: float) -> tuple[np.ndarray, np.ndarray]:
    """Score and class rank when values above e1 become progressively worse."""
    score = np.ones_like(v, dtype=float)
    rank = np.full(v.shape, 3, dtype=np.int8)
    if np.isinf(e1):
        return score, rank
    m2 = (v > e1) & (v <= e2)
    score[m2] = 1.0 - 0.34 * (v[m2] - e1) / max(e2 - e1, _EPS) if np.isfinite(e2) else 1.0
    rank[m2] = 2
    m3 = (v > e2) & (v <= e3)
    score[m3] = 0.66 - 0.33 * (v[m3] - e2) / max(e3 - e2, _EPS) if np.isfinite(e3) else 0.66
    rank[m3] = 1
    mn = v > e3
    score[mn] = 0.0
    rank[mn] = 0
    return score, rank


def score_factor(values, breaks: ClassBreaks) -> tuple[np.ndarray, np.ndarray]:
    """
    Vectorised factor scoring.

    Returns (score in [0,1], class rank 3=S1 .. 0=N), same shape as `values`.
    NaN inputs return NaN score and rank -1 so missing data is never silently 'suitable'.
    """
    v = np.asarray(values, dtype=float)
    nan = np.isnan(v)
    vv = np.where(nan, 0.0, v)
    s_hi, r_hi = _upper_side(vv, breaks.s1_high, breaks.s2_high, breaks.s3_high)
    # the lower side is the upper side of the mirrored axis
    s_lo, r_lo = _upper_side(-vv, -breaks.s1_low, -breaks.s2_low, -breaks.s3_low)
    score = np.minimum(s_hi, s_lo)
    rank = np.minimum(r_hi, r_lo).astype(np.int8)
    score[nan] = np.nan
    rank[nan] = -1
    return score, rank


# ------------------------------------------------------------------ AHP
# Saaty's random consistency index for n = 1..10
_RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def ahp_weights(pairwise: np.ndarray) -> tuple[np.ndarray, float]:
    """
    Weights from an AHP pairwise comparison matrix (principal eigenvector) and the
    consistency ratio CR. CR < 0.10 is the usual acceptance rule.
    """
    a = np.asarray(pairwise, dtype=float)
    n = a.shape[0]
    if a.shape != (n, n):
        raise ValueError(f"Pairwise matrix must be square, got {a.shape}")
    if np.any(a <= 0):
        raise ValueError("Pairwise judgements must be positive (1/9 .. 9)")
    if not np.allclose(a * a.T, 1.0, atol=1e-6):
        raise ValueError("Pairwise matrix must be reciprocal: a[i,j] * a[j,i] == 1")
    eigvals, eigvecs = np.linalg.eig(a)
    k = int(np.argmax(eigvals.real))
    w = np.abs(eigvecs[:, k].real)
    w = w / w.sum()
    lam_max = float(eigvals[k].real)
    ci = (lam_max - n) / (n - 1) if n > 2 else 0.0
    ri = _RI.get(n, 1.49)
    cr = ci / ri if ri > 0 else 0.0
    return w, cr


# ------------------------------------------------------------------ grid level
def assess_grid(layers: dict[str, np.ndarray], profile: CropProfile, method: Method = Method.AHP_WLC):
    """
    Assess a whole raster stack for one crop.

    layers  : factor_code -> 2D array (all same shape, already co-registered)
    returns : dict with 'score', 'rank' (3..0, -1 = missing data), 'limiting' (index into
              'factor_codes' of the lowest-scoring factor per cell) and 'factor_codes'.
    """
    codes = [r.factor.code for r in profile.requirements]
    missing = [c for c in codes if c not in layers]
    if missing:
        raise KeyError(f"Missing layers for {profile.crop}: {missing}")
    shapes = {layers[c].shape for c in codes}
    if len(shapes) != 1:
        raise ValueError(f"Layers are not co-registered, shapes differ: {shapes}")

    scores, ranks = [], []
    for req in profile.requirements:
        s, r = score_factor(layers[req.factor.code], req.breaks)
        scores.append(s)
        ranks.append(r)
    S = np.stack(scores)          # (F, H, W)
    R = np.stack(ranks)
    w = np.array([r.weight for r in profile.requirements], dtype=float)
    w = w / w.sum()

    any_missing = np.isnan(S).any(axis=0)
    worst_rank = R.min(axis=0)
    limiting = np.nanargmin(np.where(np.isnan(S), np.inf, S), axis=0)

    if method == Method.FAO_LIMITING:
        score = np.nanmin(S, axis=0)
        rank = worst_rank.copy()
    elif method == Method.AHP_WLC:
        score = np.tensordot(w, np.nan_to_num(S), axes=1)
        rank = np.zeros(score.shape, dtype=np.int8)
        for thr, rk in reversed(WLC_THRESHOLDS):
            rank[score >= thr] = rk
        # compensation cap: averaging may not hide a weak factor by more than one class
        # (a factor in S3 caps the land at S2; a factor in N makes the land N)
        rank = np.minimum(rank, np.where(worst_rank == 0, 0, worst_rank + 1)).astype(np.int8)
        score = np.where(worst_rank == 0, np.minimum(score, 0.39), score)
    else:
        raise ValueError(f"Method {method} is not a rule-based method; use the deep-learning model")

    score = np.where(any_missing, np.nan, score)
    rank = np.where(any_missing, -1, rank).astype(np.int8)
    return {"score": score, "rank": rank, "limiting": limiting, "factor_codes": codes}


# ------------------------------------------------------------------ plot level
def assess_plot(plot: Plot, profile: CropProfile, method: Method = Method.AHP_WLC,
                n_monte_carlo: int = 0, seed: int = 0) -> SuitabilityAssessment:
    """
    Assess one plot. If n_monte_carlo > 0, observation std values are used to sample
    inputs and the std of the resulting score is reported as uncertainty.
    """
    codes = [r.factor.code for r in profile.requirements]
    missing = [c for c in codes if c not in plot.observations]
    if missing:
        raise KeyError(f"Plot {plot.plot_id} lacks observations for {missing}")

    layers = {c: np.array([[plot.observations[c].value]]) for c in codes}
    out = assess_grid(layers, profile, method)

    factor_results = []
    for req in profile.requirements:
        s, r = score_factor([plot.observations[req.factor.code].value], req.breaks)
        factor_results.append(FactorResult(req.factor.code, plot.observations[req.factor.code].value,
                                           _CLASS_OF_RANK[int(r[0])], float(s[0])))
    worst = min(fr.score for fr in factor_results)
    limiting = tuple(fr.factor_code for fr in factor_results if fr.score < 1.0 and fr.score <= worst + 1e-9)

    uncertainty = None
    if n_monte_carlo > 0:
        rng = np.random.default_rng(seed)
        samples = {}
        for c in codes:
            obs = plot.observations[c]
            sd = obs.std or 0.0
            samples[c] = (obs.value + rng.normal(0.0, sd, n_monte_carlo)).reshape(1, -1)
        mc = assess_grid(samples, profile, method)
        uncertainty = float(np.nanstd(mc["score"]))

    return SuitabilityAssessment(
        target_id=plot.plot_id, crop=profile.crop, season=profile.season,
        klass=_CLASS_OF_RANK[int(out["rank"][0, 0])], score=float(out["score"][0, 0]),
        limiting_factors=limiting, factor_results=tuple(factor_results),
        method=method, method_version=METHOD_VERSION, uncertainty=uncertainty,
    )
