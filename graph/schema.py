# schema.py
# Define node and edge types for immune signaling graph

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
