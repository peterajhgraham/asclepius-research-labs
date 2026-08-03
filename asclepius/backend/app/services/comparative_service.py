"""Comparative analysis service for autoimmune diseases.

Compares two diseases across multiple dimensions: pathways, cytokines,
cell types, genetics, and therapeutics.  Returns structured differential
analysis useful for translational researchers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.data.ingestion import STORE, DiseaseRecord

logger = logging.getLogger(__name__)


def _find_disease(name: str) -> Optional[DiseaseRecord]:
    """Fuzzy-match a disease name against the loaded dataset."""
    name_lower = name.lower().strip()
    # Exact match first
    for dis in STORE.diseases:
        if dis.disease_name.lower() == name_lower:
            return dis
    # Substring match
    for dis in STORE.diseases:
        if name_lower in dis.disease_name.lower() or dis.disease_name.lower() in name_lower:
            return dis
    # Token overlap
    query_tokens = set(name_lower.split())
    best_match: Optional[DiseaseRecord] = None
    best_score = 0.0
    for dis in STORE.diseases:
        dis_tokens = set(dis.disease_name.lower().split())
        overlap = len(query_tokens & dis_tokens)
        score = overlap / max(len(query_tokens), 1)
        if score > best_score and score > 0.3:
            best_score = score
            best_match = dis
    return best_match


def _disease_to_profile(dis: DiseaseRecord) -> Dict[str, Any]:
    """Convert a disease record into a structured analysis profile."""
    # Collect cytokines from related cytokine edges
    cytokines: List[str] = []
    cytokine_edges: List[Dict[str, Any]] = []
    dis_name_lower = dis.disease_name.lower()
    for edge in STORE.cytokine_edges:
        edge_diseases = [d.lower() for d in edge.diseases]
        if any(dis_name_lower in d or d in dis_name_lower for d in edge_diseases):
            if edge.source not in cytokines:
                cytokines.append(edge.source)
            if edge.target not in cytokines:
                cytokines.append(edge.target)
            cytokine_edges.append({
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "description": edge.description,
            })

    # Collect pathways
    pathways: List[Dict[str, Any]] = []
    for pw in STORE.pathways:
        relevance = [d.lower() for d in pw.disease_relevance]
        if any(dis_name_lower in d or d in dis_name_lower for d in relevance):
            pathways.append({
                "pathway_name": pw.pathway_name,
                "pathway_id": pw.pathway_id,
                "description": pw.description[:200],
                "key_nodes": [n.get("gene", "") for n in pw.key_nodes[:6]],
                "therapeutic_targets": pw.therapeutic_targets[:3],
            })

    # Collect therapeutics
    therapeutics: List[Dict[str, Any]] = []
    for rx in STORE.therapeutics:
        for ind in rx.approved_indications:
            ind_disease = ind.get("disease", "").lower()
            if dis_name_lower in ind_disease or ind_disease in dis_name_lower:
                therapeutics.append({
                    "drug_name": rx.drug_name,
                    "brand_name": rx.brand_name,
                    "drug_class": rx.drug_class,
                    "target": rx.target,
                    "mechanism": rx.mechanism[:150],
                })
                break

    return {
        "disease_name": dis.disease_name,
        "disease_id": dis.disease_id,
        "description": dis.description,
        "prevalence": dis.prevalence,
        "pathogenic_mechanisms": dis.pathogenic_mechanisms,
        "key_cell_types": dis.key_cell_types,
        "associated_genes": [
            {"gene": g["gene"], "score": g.get("score", 0)}
            for g in dis.associated_genes[:10]
        ],
        "hla_associations": dis.hla_associations,
        "autoantibodies": dis.autoantibodies,
        "cytokines": cytokines[:15],
        "cytokine_network": cytokine_edges[:10],
        "pathways": pathways,
        "therapeutics": therapeutics,
        "approved_therapies": dis.approved_therapies,
    }


def _compute_overlaps(
    profile_a: Dict[str, Any],
    profile_b: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute shared and unique elements between two disease profiles."""
    genes_a = {g["gene"] for g in profile_a["associated_genes"]}
    genes_b = {g["gene"] for g in profile_b["associated_genes"]}

    cells_a = set(profile_a["key_cell_types"])
    cells_b = set(profile_b["key_cell_types"])

    cytokines_a = set(profile_a["cytokines"])
    cytokines_b = set(profile_b["cytokines"])

    pathways_a = {p["pathway_name"] for p in profile_a["pathways"]}
    pathways_b = {p["pathway_name"] for p in profile_b["pathways"]}

    drugs_a = {t["drug_name"] for t in profile_a["therapeutics"]}
    drugs_b = {t["drug_name"] for t in profile_b["therapeutics"]}

    mechanisms_a = set(profile_a["pathogenic_mechanisms"])
    mechanisms_b = set(profile_b["pathogenic_mechanisms"])

    return {
        "shared_genes": sorted(genes_a & genes_b),
        "unique_genes_a": sorted(genes_a - genes_b),
        "unique_genes_b": sorted(genes_b - genes_a),
        "shared_cell_types": sorted(cells_a & cells_b),
        "unique_cell_types_a": sorted(cells_a - cells_b),
        "unique_cell_types_b": sorted(cells_b - cells_a),
        "shared_cytokines": sorted(cytokines_a & cytokines_b),
        "unique_cytokines_a": sorted(cytokines_a - cytokines_b),
        "unique_cytokines_b": sorted(cytokines_b - cytokines_a),
        "shared_pathways": sorted(pathways_a & pathways_b),
        "unique_pathways_a": sorted(pathways_a - pathways_b),
        "unique_pathways_b": sorted(pathways_b - pathways_a),
        "shared_therapeutics": sorted(drugs_a & drugs_b),
        "unique_therapeutics_a": sorted(drugs_a - drugs_b),
        "unique_therapeutics_b": sorted(drugs_b - drugs_a),
        "shared_mechanisms": sorted(mechanisms_a & mechanisms_b),
        "unique_mechanisms_a": sorted(mechanisms_a - mechanisms_b),
        "unique_mechanisms_b": sorted(mechanisms_b - mechanisms_a),
    }


def compare_diseases(
    disease_a_name: str,
    disease_b_name: str,
) -> Optional[Dict[str, Any]]:
    """Compare two autoimmune diseases across all dimensions.

    Returns None if either disease is not found in the dataset.
    """
    dis_a = _find_disease(disease_a_name)
    dis_b = _find_disease(disease_b_name)

    if not dis_a:
        logger.warning("Disease not found: %s", disease_a_name)
        return None
    if not dis_b:
        logger.warning("Disease not found: %s", disease_b_name)
        return None

    if dis_a.disease_id == dis_b.disease_id or dis_a.disease_name == dis_b.disease_name:
        logger.warning(
            "Self-comparison detected: both inputs resolved to %s", dis_a.disease_name
        )
        return None

    profile_a = _disease_to_profile(dis_a)
    profile_b = _disease_to_profile(dis_b)
    overlaps = _compute_overlaps(profile_a, profile_b)

    # Compute a similarity score
    total_shared = (
        len(overlaps["shared_genes"])
        + len(overlaps["shared_cell_types"])
        + len(overlaps["shared_cytokines"])
        + len(overlaps["shared_pathways"])
        + len(overlaps["shared_mechanisms"])
    )
    total_all = (
        len(set(profile_a.get("cytokines", [])) | set(profile_b.get("cytokines", [])))
        + len({g["gene"] for g in profile_a["associated_genes"]} | {g["gene"] for g in profile_b["associated_genes"]})
        + len(set(profile_a["key_cell_types"]) | set(profile_b["key_cell_types"]))
        + len({p["pathway_name"] for p in profile_a["pathways"]} | {p["pathway_name"] for p in profile_b["pathways"]})
        + len(set(profile_a["pathogenic_mechanisms"]) | set(profile_b["pathogenic_mechanisms"]))
    )
    similarity_score = total_shared / max(total_all, 1)

    return {
        "disease_a": profile_a,
        "disease_b": profile_b,
        "overlaps": overlaps,
        "similarity_score": round(similarity_score, 3),
        "summary": _generate_comparison_summary(profile_a, profile_b, overlaps, similarity_score),
    }


def _generate_comparison_summary(
    a: Dict[str, Any],
    b: Dict[str, Any],
    overlaps: Dict[str, Any],
    similarity: float,
) -> str:
    """Generate a narrative comparison summary."""
    lines = [
        f"**{a['disease_name']}** vs **{b['disease_name']}** — "
        f"Overall mechanistic similarity: {similarity:.0%}",
        "",
    ]

    if overlaps["shared_pathways"]:
        lines.append(
            f"**Shared pathways:** {', '.join(overlaps['shared_pathways'])}. "
            f"These represent potential cross-disease therapeutic targets."
        )
    if overlaps["shared_cytokines"]:
        lines.append(
            f"**Shared cytokines:** {', '.join(overlaps['shared_cytokines'][:8])}."
        )
    if overlaps["shared_genes"]:
        lines.append(
            f"**Shared genetic risk loci:** {', '.join(overlaps['shared_genes'][:6])}."
        )
    if overlaps["shared_cell_types"]:
        lines.append(
            f"**Shared immune cell involvement:** {', '.join(overlaps['shared_cell_types'])}."
        )
    if overlaps["shared_therapeutics"]:
        lines.append(
            f"**Cross-approved therapeutics:** {', '.join(overlaps['shared_therapeutics'])}."
        )

    lines.append("")

    if overlaps["unique_mechanisms_a"]:
        lines.append(
            f"**Mechanisms unique to {a['disease_name']}:** "
            f"{', '.join(overlaps['unique_mechanisms_a'][:4])}."
        )
    if overlaps["unique_mechanisms_b"]:
        lines.append(
            f"**Mechanisms unique to {b['disease_name']}:** "
            f"{', '.join(overlaps['unique_mechanisms_b'][:4])}."
        )

    return "\n".join(lines)


def list_available_diseases() -> List[str]:
    """Return all disease names available for comparison."""
    return [dis.disease_name for dis in STORE.diseases]
