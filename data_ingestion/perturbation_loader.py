# perturbation_loader.py
# Load CRISPR screen and cytokine perturbation datasets.

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_crispr_screen(
    filepath: str,
    source_col: str = "gene",
    score_col: str = "lfc",
    fdr_col: Optional[str] = "fdr",
    fdr_threshold: float = 0.05,
    dataset_name: Optional[str] = None,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Load a CRISPR genetic screen result file and return perturbation edges.

    Expects a CSV/TSV with at minimum columns for the perturbed gene and a
    log-fold-change (or similar enrichment) score.  Each perturbed gene is
    linked to a virtual ``"CRISPR_SCREEN"`` target node so that results can
    be stored as edges in the graph.

    Parameters
    ----------
    filepath:
        Path to the screen result file (CSV or TSV).
    source_col:
        Name of the column containing perturbed gene symbols.
    score_col:
        Name of the column containing effect scores (e.g. LFC or Z-score).
    fdr_col:
        Optional column name for FDR/adjusted p-value.  Rows exceeding
        *fdr_threshold* are discarded.
    fdr_threshold:
        Maximum allowable FDR.  Used only when *fdr_col* is provided.
    dataset_name:
        Label to embed in edge metadata as ``"source_publication"``.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
        ``edge_type`` is ``"activates"`` for positive LFC and ``"inhibits"``
        for negative LFC.
    """
    path = Path(filepath)
    delimiter = "\t" if path.suffix.lower() in (".tsv", ".txt") else ","
    edges: List[Tuple[str, str, str, Dict[str, Any]]] = []

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        for row in reader:
            gene = row.get(source_col, "").strip()
            score_str = row.get(score_col, "").strip()

            if not gene or not score_str:
                continue

            try:
                score = float(score_str)
            except ValueError:
                continue

            if fdr_col and fdr_col in row:
                try:
                    fdr_val = float(row[fdr_col])
                except ValueError:
                    fdr_val = 1.0
                if fdr_val > fdr_threshold:
                    continue

            edge_type = "activates" if score >= 0 else "inhibits"
            metadata: Dict[str, Any] = {
                "confidence_score": min(1.0, abs(score) / 5.0),
                "perturbation_score": score,
                "perturbation_type": "CRISPR",
            }
            if dataset_name:
                metadata["source_publication"] = dataset_name

            screen_node = dataset_name or "CRISPR_SCREEN"
            edges.append((gene, screen_node, edge_type, metadata))

    return edges


def load_cytokine_perturbations(
    filepath: str,
    cytokine_col: str = "cytokine",
    target_col: str = "target_gene",
    direction_col: str = "direction",
    confidence_col: Optional[str] = "confidence",
    dataset_name: Optional[str] = None,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Load cytokine perturbation data and return interaction edges.

    Accepts CSV/TSV files with columns for the stimulating cytokine,
    the target gene/protein, and the direction of regulation.

    Parameters
    ----------
    filepath:
        Path to the perturbation data file.
    cytokine_col:
        Column name for the stimulating cytokine.
    target_col:
        Column name for the regulated gene/protein.
    direction_col:
        Column name encoding direction: ``"up"``/``"activates"`` or
        ``"down"``/``"inhibits"``.
    confidence_col:
        Optional column name for a numeric confidence score in [0, 1].
    dataset_name:
        Label for provenance metadata.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
    """
    path = Path(filepath)
    delimiter = "\t" if path.suffix.lower() in (".tsv", ".txt") else ","
    edges: List[Tuple[str, str, str, Dict[str, Any]]] = []

    _direction_map = {
        "up": "activates",
        "activates": "activates",
        "activation": "activates",
        "down": "inhibits",
        "inhibits": "inhibits",
        "inhibition": "inhibits",
    }

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        for row in reader:
            cytokine = row.get(cytokine_col, "").strip()
            target = row.get(target_col, "").strip()
            direction = row.get(direction_col, "").strip().lower()

            if not cytokine or not target:
                continue

            edge_type = _direction_map.get(direction, "activates")
            metadata: Dict[str, Any] = {
                "perturbation_type": "cytokine",
            }

            if confidence_col and confidence_col in row:
                try:
                    metadata["confidence_score"] = float(row[confidence_col])
                except ValueError:
                    metadata["confidence_score"] = 0.5
            else:
                metadata["confidence_score"] = 0.5

            if dataset_name:
                metadata["source_publication"] = dataset_name

            edges.append((cytokine, target, edge_type, metadata))

    return edges


def load_perturbation_json(
    filepath: str,
) -> List[Tuple[str, str, str, Dict[str, Any]]]:
    """Load perturbation data from a JSON file.

    Expected JSON schema::

        [
            {
                "source": "IL6",
                "target": "STAT3",
                "edge_type": "activates",
                "confidence_score": 0.9,
                "perturbation_type": "cytokine"
            },
            ...
        ]

    Parameters
    ----------
    filepath:
        Path to the JSON file.

    Returns
    -------
    list of (source, target, edge_type, metadata) tuples
    """
    with open(filepath, encoding="utf-8") as fh:
        records = json.load(fh)

    edges: List[Tuple[str, str, str, Dict[str, Any]]] = []
    for rec in records:
        source = rec.get("source", "")
        target = rec.get("target", "")
        edge_type = rec.get("edge_type", "activates")
        metadata = {
            k: v
            for k, v in rec.items()
            if k not in ("source", "target", "edge_type")
        }
        if source and target:
            edges.append((source, target, edge_type, metadata))

    return edges
