"""
Project-wide configuration constants for Asclepius neurology platform.

All external API endpoints, default file paths, and tunable parameters are
centralised here so that callers never hard-code URLs or magic strings.

Usage
-----
>>> from utils.config import Config
>>> print(Config.GNOMAD_API_URL)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Config:
    """Immutable project configuration.

    All attributes are class-level defaults.  Override by instantiating with
    explicit values when running in non-default environments.
    """

    # ------------------------------------------------------------------
    # Project layout
    # ------------------------------------------------------------------
    #: Root of the repository (two levels up from this file).
    PROJECT_ROOT: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )

    @property
    def data_raw_dir(self) -> Path:
        """Absolute path to the raw data directory."""
        return self.PROJECT_ROOT / "data" / "raw"

    @property
    def data_processed_dir(self) -> Path:
        """Absolute path to the processed data directory."""
        return self.PROJECT_ROOT / "data" / "processed"

    # ------------------------------------------------------------------
    # ClinVar
    # ------------------------------------------------------------------
    #: NCBI FTP URL for the ClinVar variant summary file.
    CLINVAR_FTP_URL: str = (
        "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
    )
    #: Default genome assembly filter when loading ClinVar data.
    CLINVAR_ASSEMBLY: str = "GRCh38"

    # ------------------------------------------------------------------
    # gnomAD
    # ------------------------------------------------------------------
    #: gnomAD public GraphQL API endpoint.
    GNOMAD_API_URL: str = "https://gnomad.broadinstitute.org/api"
    #: Default gnomAD dataset identifier.
    GNOMAD_DATASET: str = "gnomad_r4"

    # ------------------------------------------------------------------
    # KEGG
    # ------------------------------------------------------------------
    #: KEGG REST API base URL.
    KEGG_BASE_URL: str = "https://rest.kegg.jp"
    #: Default KEGG organism code.
    KEGG_ORGANISM: str = "hsa"

    # ------------------------------------------------------------------
    # Reactome
    # ------------------------------------------------------------------
    #: Reactome Content Service base URL.
    REACTOME_BASE_URL: str = "https://reactome.org/ContentService"
    #: NCBI taxonomy ID for *Homo sapiens*.
    REACTOME_SPECIES_TAXON: str = "9606"

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    #: Clinical significance values considered pathogenic for scoring.
    PATHOGENIC_SIGNIFICANCES: List[str] = field(
        default_factory=lambda: [
            "Pathogenic",
            "Likely pathogenic",
            "Pathogenic/Likely pathogenic",
        ]
    )
    #: Weight applied to high-confidence loss-of-function (LoF) variants.
    LOF_WEIGHT: float = 2.0
    #: Weight applied to pathogenic variants without LoF annotation.
    PATHOGENIC_WEIGHT: float = 1.0
    #: Default weight for variants of uncertain significance.
    VUS_WEIGHT: float = 0.1

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    #: Default timeout (seconds) for external API requests.
    HTTP_TIMEOUT: int = 30


# Module-level singleton for convenience import
_default_config = Config()
