"""Hypothesis generator service for autoimmune research.

Generates structured, testable research hypotheses based on disease
mechanisms, pathway analysis, cytokine networks, and identified
research gaps.  Each hypothesis includes experimental design
suggestions, biomarkers, and potential confounders.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.data.ingestion import STORE
from app.services.query_engine import search_all

logger = logging.getLogger(__name__)


def generate_hypotheses(
    topic: str,
    max_hypotheses: int = 5,
) -> Dict[str, Any]:
    """Generate testable research hypotheses for a given topic.

    Parameters
    ----------
    topic : str
        Research topic or question (e.g., "IL-17 in psoriasis",
        "JAK-STAT in lupus").
    max_hypotheses : int
        Maximum number of hypotheses to generate.

    Returns
    -------
    dict with keys:
        - topic: the input topic
        - hypotheses: list of structured hypothesis dicts
        - context: supporting evidence used to generate hypotheses
    """
    results = search_all(topic)
    hypotheses: List[Dict[str, Any]] = []

    # Strategy 1: Target-based hypotheses from disease-pathway gaps
    hypotheses.extend(_pathway_gap_hypotheses(results, topic))

    # Strategy 2: Cross-disease repurposing hypotheses
    hypotheses.extend(_repurposing_hypotheses(results, topic))

    # Strategy 3: Cytokine network hypotheses (feedback loops)
    hypotheses.extend(_cytokine_network_hypotheses(results, topic))

    # Strategy 4: Genetic-mechanistic hypotheses
    hypotheses.extend(_genetic_hypotheses(results, topic))

    # Strategy 5: Combination therapy hypotheses
    hypotheses.extend(_combination_hypotheses(results, topic))

    # Deduplicate and limit
    seen_titles: set = set()
    unique: List[Dict[str, Any]] = []
    for h in hypotheses:
        if h["hypothesis"] not in seen_titles:
            seen_titles.add(h["hypothesis"])
            unique.append(h)
    hypotheses = unique[:max_hypotheses]

    # Build context summary
    context = _build_context_summary(results)

    return {
        "topic": topic,
        "hypotheses": hypotheses,
        "context": context,
        "total_generated": len(hypotheses),
    }


# ------------------------------------------------------------------
# Hypothesis generation strategies
# ------------------------------------------------------------------

def _pathway_gap_hypotheses(results: Any, topic: str) -> List[Dict[str, Any]]:
    """Generate hypotheses from pathway-disease connections."""
    hypotheses: List[Dict[str, Any]] = []

    for pw in results.pathway_hits[:3]:
        pw_name = pw["pathway_name"]
        targets = pw.get("therapeutic_targets", [])

        if results.disease_hits:
            disease = results.disease_hits[0]
            disease_name = disease["disease_name"]

            # Known pathway with unexplored targets
            existing_drugs = {t.get("drug", "") for t in targets}
            all_nodes = [n.get("gene", "") for n in pw.get("key_nodes", [])]
            untargeted = [n for n in all_nodes if n and n not in existing_drugs]

            if untargeted:
                target_node = untargeted[0]
                hypotheses.append({
                    "hypothesis": (
                        f"Selective modulation of {target_node} within the "
                        f"{pw_name} pathway may attenuate pathogenic signaling "
                        f"in {disease_name}"
                    ),
                    "category": "Target Discovery",
                    "rationale": (
                        f"{target_node} is a key node in {pw_name} but lacks "
                        f"approved therapeutic agents. Given the pathway's established "
                        f"role in {disease_name}, {target_node} represents an "
                        f"unexplored intervention point."
                    ),
                    "experimental_design": {
                        "model": f"In vitro: primary {disease_name} patient PBMCs; "
                                 f"In vivo: relevant murine model",
                        "intervention": f"siRNA knockdown or small-molecule inhibition of {target_node}",
                        "readouts": [
                            f"Downstream signaling (phospho-flow for {pw_name} effectors)",
                            "Pro-inflammatory cytokine secretion (ELISA/Luminex)",
                            "T cell/B cell activation markers (flow cytometry)",
                        ],
                        "controls": [
                            "Scrambled siRNA / vehicle control",
                            f"Positive control: existing {pw_name} inhibitor",
                        ],
                        "timeline": "8-12 weeks for in vitro; 16-20 weeks for in vivo",
                    },
                    "biomarkers": [
                        f"Phosphorylated {target_node}",
                        "Serum cytokine levels (IL-6, TNF-α, IL-17)",
                        "Disease activity score",
                    ],
                    "confounders": [
                        "Off-target effects of inhibitor",
                        "Compensatory pathway activation",
                        "Patient heterogeneity in disease stage",
                    ],
                    "confidence": "Medium",
                    "supporting_evidence": pw.get("references", [])[:3],
                })

    return hypotheses


def _repurposing_hypotheses(results: Any, topic: str) -> List[Dict[str, Any]]:
    """Generate drug repurposing hypotheses across diseases."""
    hypotheses: List[Dict[str, Any]] = []

    if not results.disease_hits or not results.therapeutic_hits:
        return hypotheses

    disease = results.disease_hits[0]
    disease_name = disease["disease_name"]

    # Find therapeutics approved for OTHER diseases but targeting shared pathways
    disease_drugs = {
        rx["drug"] for rx in disease.get("approved_therapies", [])
    }

    for rx in results.therapeutic_hits[:5]:
        drug_name = rx["drug_name"]
        if drug_name in disease_drugs:
            continue  # Already approved for this disease

        # Check if the drug's target is relevant to this disease
        target = rx.get("target", "")
        target_lower = target.lower()
        mechanisms = [m.lower() for m in disease.get("pathogenic_mechanisms", [])]

        relevant = any(
            target_lower in mech or target_lower in " ".join(disease.get("key_cell_types", []))
            for mech in mechanisms
        )

        if relevant or target_lower in topic.lower():
            indications = [
                ind["disease"]
                for ind in rx.get("approved_indications", [])[:3]
            ]
            hypotheses.append({
                "hypothesis": (
                    f"{drug_name} ({rx.get('drug_class', '')}) may be efficacious "
                    f"in {disease_name} given its mechanism of action on {target}"
                ),
                "category": "Drug Repurposing",
                "rationale": (
                    f"{drug_name} targets {target} and is approved for "
                    f"{', '.join(indications)}. The shared mechanistic involvement "
                    f"of {target} in {disease_name} suggests potential therapeutic benefit."
                ),
                "experimental_design": {
                    "model": f"Phase IIa proof-of-concept trial in {disease_name} patients",
                    "intervention": f"{drug_name} at approved dosing vs placebo",
                    "readouts": [
                        "Primary: Disease activity index change at 12 weeks",
                        f"Secondary: Serum {target} pathway biomarkers",
                        "Safety: Adverse event monitoring",
                    ],
                    "controls": [
                        "Placebo arm",
                        "Standard-of-care comparator",
                    ],
                    "timeline": "24-36 weeks",
                },
                "biomarkers": [
                    f"Serum {target} levels",
                    "Clinical disease activity score",
                    "Patient-reported outcomes",
                ],
                "confounders": [
                    "Prior treatment history",
                    "Disease duration and severity",
                    "Concomitant medications",
                ],
                "confidence": "Medium-High" if len(indications) > 1 else "Medium",
                "supporting_evidence": [],
            })

    return hypotheses


def _cytokine_network_hypotheses(results: Any, topic: str) -> List[Dict[str, Any]]:
    """Generate hypotheses from cytokine network topology."""
    hypotheses: List[Dict[str, Any]] = []

    if len(results.cytokine_hits) < 3:
        return hypotheses

    # Look for potential feedback loops or cascade amplification
    sources = {}
    for edge in results.cytokine_hits[:15]:
        src = edge["source"]
        tgt = edge["target"]
        if src not in sources:
            sources[src] = []
        sources[src].append(tgt)

    # Find nodes that both activate and are activated by the network
    all_targets = {e["target"] for e in results.cytokine_hits[:15]}
    all_sources = {e["source"] for e in results.cytokine_hits[:15]}
    feedback_nodes = all_targets & all_sources

    disease_name = results.disease_hits[0]["disease_name"] if results.disease_hits else topic

    for node in list(feedback_nodes)[:2]:
        # Find what this node activates and what activates it
        activators = [
            e["source"] for e in results.cytokine_hits
            if e["target"] == node and e["edge_type"] == "activates"
        ][:3]
        downstream = [
            e["target"] for e in results.cytokine_hits
            if e["source"] == node and e["edge_type"] == "activates"
        ][:3]

        if activators and downstream:
            hypotheses.append({
                "hypothesis": (
                    f"{node} functions as an amplification hub in {disease_name}, "
                    f"where upstream signals from {', '.join(activators[:2])} are "
                    f"propagated to {', '.join(downstream[:2])}, creating a "
                    f"self-reinforcing inflammatory loop"
                ),
                "category": "Network Mechanism",
                "rationale": (
                    f"{node} sits at a network hub position, receiving signals from "
                    f"{len(activators)} upstream cytokines and propagating to "
                    f"{len(downstream)} downstream targets. Disrupting this hub "
                    f"may break the amplification cycle."
                ),
                "experimental_design": {
                    "model": f"Ex vivo {disease_name} tissue explants + "
                             "in vitro stimulation assays",
                    "intervention": f"Neutralizing antibody against {node}",
                    "readouts": [
                        f"Downstream cytokine levels ({', '.join(downstream[:3])})",
                        "Transcriptomic profiling (RNA-seq)",
                        "Immune cell phenotyping",
                    ],
                    "controls": [
                        "Isotype control antibody",
                        f"Known {node} inhibitor as positive control",
                    ],
                    "timeline": "4-8 weeks for in vitro; 12-16 weeks for ex vivo",
                },
                "biomarkers": [
                    f"Serum {node} levels",
                    f"Downstream: {', '.join(downstream[:2])} levels",
                    "Immune activation markers (CD69, HLA-DR)",
                ],
                "confounders": [
                    "Redundant signaling pathways",
                    "Cell-type-specific effects",
                    "Temporal dynamics of cytokine cascades",
                ],
                "confidence": "Medium",
                "supporting_evidence": [],
            })

    return hypotheses


def _genetic_hypotheses(results: Any, topic: str) -> List[Dict[str, Any]]:
    """Generate hypotheses linking genetic risk loci to mechanisms."""
    hypotheses: List[Dict[str, Any]] = []

    if not results.disease_hits:
        return hypotheses

    disease = results.disease_hits[0]
    disease_name = disease["disease_name"]
    genes = disease.get("associated_genes", [])

    for gene_rec in genes[:2]:
        gene = gene_rec.get("gene", "")
        score = gene_rec.get("score", 0)
        desc = gene_rec.get("description", "")

        if not gene or score < 0.5:
            continue

        # Check if this gene is in any pathway
        gene_pathways = []
        for pw in STORE.pathways:
            for node in pw.key_nodes:
                if node.get("gene", "").upper() == gene.upper():
                    gene_pathways.append(pw.pathway_name)
                    break

        hypotheses.append({
            "hypothesis": (
                f"Risk variants in {gene} may drive {disease_name} pathogenesis "
                f"through dysregulation of "
                f"{', '.join(gene_pathways[:2]) if gene_pathways else 'immune signaling'}, "
                f"creating a context-dependent effect in specific immune cell subsets"
            ),
            "category": "Genetic Mechanism",
            "rationale": (
                f"{gene} (GWAS score: {score}) is a top genetic risk locus for "
                f"{disease_name}. {desc} Understanding the functional consequences "
                f"of risk variants could reveal new therapeutic targets."
            ),
            "experimental_design": {
                "model": "Patient-derived iPSC immune cell differentiation + "
                         "CRISPR-edited risk variant lines",
                "intervention": f"CRISPR knock-in of {gene} risk vs protective variants",
                "readouts": [
                    f"{gene} expression and protein levels",
                    "Downstream signaling (pathway-specific phospho-flow)",
                    "Single-cell RNA-seq for cell-type-specific effects",
                    "Functional immune assays (proliferation, cytokine secretion)",
                ],
                "controls": [
                    "Isogenic control (wild-type)",
                    "Known functional variant as positive control",
                ],
                "timeline": "6-12 months (iPSC differentiation + functional assays)",
            },
            "biomarkers": [
                f"{gene} expression levels",
                "Variant-specific eQTL effects",
                "Cell-type composition changes",
            ],
            "confounders": [
                "Linkage disequilibrium with nearby variants",
                "Epistatic interactions",
                "iPSC-to-immune cell differentiation artifacts",
            ],
            "confidence": "High" if score > 0.8 else "Medium",
            "supporting_evidence": disease.get("references", [])[:3],
        })

    return hypotheses


def _combination_hypotheses(results: Any, topic: str) -> List[Dict[str, Any]]:
    """Generate combination therapy hypotheses."""
    hypotheses: List[Dict[str, Any]] = []

    if len(results.therapeutic_hits) < 2:
        return hypotheses

    disease_name = results.disease_hits[0]["disease_name"] if results.disease_hits else topic

    # Pair therapeutics targeting different pathways
    rx_a = results.therapeutic_hits[0]
    rx_b = results.therapeutic_hits[1]

    if rx_a["target"] != rx_b["target"]:
        hypotheses.append({
            "hypothesis": (
                f"Combination of {rx_a['drug_name']} ({rx_a['target']} inhibitor) "
                f"and {rx_b['drug_name']} ({rx_b['target']} inhibitor) may achieve "
                f"synergistic efficacy in {disease_name} by simultaneously "
                f"targeting parallel pathogenic pathways"
            ),
            "category": "Combination Therapy",
            "rationale": (
                f"{rx_a['drug_name']} targets {rx_a['target']} while {rx_b['drug_name']} "
                f"targets {rx_b['target']}. Monotherapy resistance in {disease_name} "
                f"often arises from compensatory pathway activation. Dual blockade "
                f"may overcome this limitation."
            ),
            "experimental_design": {
                "model": f"In vitro synergy assay + in vivo {disease_name} model",
                "intervention": (
                    f"2x2 factorial: {rx_a['drug_name']} alone, {rx_b['drug_name']} alone, "
                    f"combination, vehicle"
                ),
                "readouts": [
                    "Combination index (Chou-Talalay method)",
                    "Disease activity score",
                    "Inflammatory marker panel",
                    "Safety/tolerability profile",
                ],
                "controls": [
                    "Vehicle control",
                    f"{rx_a['drug_name']} monotherapy",
                    f"{rx_b['drug_name']} monotherapy",
                ],
                "timeline": "12-16 weeks in vitro; 24+ weeks in vivo",
            },
            "biomarkers": [
                f"Serum {rx_a['target']} and {rx_b['target']} levels",
                "Composite inflammatory index",
                "Patient-reported symptom scores",
            ],
            "confounders": [
                "Drug-drug interactions",
                "Additive toxicity",
                "Dose-finding complexity",
                "Prior treatment exposure",
            ],
            "confidence": "Medium",
            "supporting_evidence": [],
        })

    return hypotheses


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_context_summary(results: Any) -> Dict[str, Any]:
    """Summarize the evidence context used for hypothesis generation."""
    return {
        "diseases_matched": [d["disease_name"] for d in results.disease_hits[:3]],
        "pathways_matched": [p["pathway_name"] for p in results.pathway_hits[:3]],
        "therapeutics_matched": [r["drug_name"] for r in results.therapeutic_hits[:5]],
        "cytokine_edges_found": len(results.cytokine_hits),
        "kb_entries_matched": len(results.kb_hits),
    }
