"""Rule-based risk scoring engine for DMI target risk reports.

Heuristic scoring — no ML model training required for MVP.
"""

from __future__ import annotations


def compute_mechanistic_risk(
    pathway_position: str,
    redundancy_level: str,
    contradictory_evidence: bool,
) -> int:
    """Compute mechanistic risk score (0-100).

    Higher score = higher risk.

    Rules:
    - +20 if downstream target (harder to modulate upstream effects)
    - +10 if midstream
    - +0 if upstream
    - +25 if high redundancy (parallel pathways compensate)
    - +12 if medium redundancy
    - +0 if low redundancy
    - +15 if contradictory literature exists
    """
    score = 0

    if pathway_position == "downstream":
        score += 20
    elif pathway_position == "midstream":
        score += 10

    if redundancy_level == "high":
        score += 25
    elif redundancy_level == "medium":
        score += 12

    if contradictory_evidence:
        score += 15

    return min(max(score, 0), 100)


def compute_translational_risk(
    phase2_failures: int,
    biomarker_alignment: str,
    historical_failure_count: int,
) -> int:
    """Compute translational risk score (0-100).

    Higher score = higher risk.

    Rules:
    - +20 if multiple phase 2 failures (>=2)
    - +10 if single phase 2 failure
    - +15 if biomarker alignment is weak
    - +5 if biomarker alignment is moderate
    - +0 if biomarker alignment is strong
    - +10 if 3+ historical failures at any stage
    - +5 if 1-2 historical failures
    """
    score = 0

    if phase2_failures >= 2:
        score += 20
    elif phase2_failures == 1:
        score += 10

    if biomarker_alignment == "weak":
        score += 15
    elif biomarker_alignment == "moderate":
        score += 5

    if historical_failure_count >= 3:
        score += 10
    elif historical_failure_count >= 1:
        score += 5

    return min(max(score, 0), 100)


def compute_overall_risk(
    mechanistic_risk: int,
    translational_risk: int,
) -> int:
    """Compute overall risk as weighted average.

    60% mechanistic, 40% translational — biology drives risk.
    """
    score = int(0.6 * mechanistic_risk + 0.4 * translational_risk)
    return min(max(score, 0), 100)
