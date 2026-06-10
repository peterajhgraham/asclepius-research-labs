"""Node and edge type vocabulary for the immune signaling graph.

Vendored into the backend (`app.kg`) so the deployable service is
self-contained and does not depend on the repo-root ``graph``/``causal``
packages, which are not present when the backend is deployed with
``asclepius/backend`` as its root directory.
"""

NODE_TYPES = [
    "Gene",
    "Protein",
    "Cytokine",
    "Receptor",
    "TranscriptionFactor",
    "CellType",
    "Pathway",
]

EDGE_TYPES = [
    "activates",
    "inhibits",
    "binds",
    "expressed_in",
    "downstream_of",
    "part_of_pathway",
]

# Metadata fields stored on every edge
EDGE_METADATA_FIELDS = [
    "source_publication",
    "confidence_score",
    "cell_type_context",
]

# Valid disease contexts for future expansion
DISEASE_CONTEXTS = [
    "autoimmune",
    "oncology",
    "vaccine",
    "infectious_disease",
]
