"""
Implement a simple versioning system for biological datasets.

Requirements:
- Each dataset has a processing_version string
- If preprocessing changes, version must increment
- Track lineage:
    - derived_from_dataset_id
- Allow branching

Goal:
Simulate Git-like behavior for biological data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Version string helpers
# ---------------------------------------------------------------------------

def _bump_patch(version: str) -> str:
    """Increment the patch segment of a semver string (e.g. '1.2.3' → '1.2.4')."""
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Expected semver 'MAJOR.MINOR.PATCH', got '{version}'.")
    parts[2] = str(int(parts[2]) + 1)
    return ".".join(parts)


def _content_hash(data: dict) -> str:
    """Return a short SHA-256 hex digest of *data* serialised as sorted JSON."""
    serialised = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(serialised).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------

@dataclass
class DatasetVersion:
    """
    A single version snapshot of a processed dataset.

    Attributes
    ----------
    dataset_id : str
        Stable identifier for the logical dataset (does not change across versions).
    processing_version : str
        Semver string that is bumped whenever preprocessing changes.
    content_hash : str
        Short SHA-256 digest of the pipeline parameters that produced this version.
    derived_from_dataset_id : str or None
        The dataset_id this version was derived from (lineage pointer).
    derived_from_version : str or None
        The specific version of the parent dataset.
    branch : str
        Branch label (default ``"main"``).  Use branches to explore alternative
        preprocessing strategies without overwriting the canonical lineage.
    created_at : str
        ISO-8601 UTC timestamp recorded at creation time.
    pipeline_params : dict
        Free-form dictionary of pipeline parameters used to produce this version.
        Changing any value here will produce a different *content_hash*.
    notes : str
        Human-readable description of what changed in this version.
    """

    dataset_id: str
    processing_version: str
    content_hash: str
    derived_from_dataset_id: Optional[str] = None
    derived_from_version: Optional[str] = None
    branch: str = "main"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    pipeline_params: Dict[str, object] = field(default_factory=dict)
    notes: str = ""


# ---------------------------------------------------------------------------
# Version registry
# ---------------------------------------------------------------------------

class VersionRegistry:
    """
    In-memory registry of all dataset versions.

    This class provides Git-inspired operations:

    * ``register``  – record the very first version of a dataset.
    * ``commit``    – create a new version derived from an existing one,
                      bumping the patch version and recomputing the content hash.
    * ``branch``    – fork a version under a new branch label.
    * ``history``   – return the full lineage chain for a given version.
    * ``latest``    – retrieve the most recent version on a branch.
    """

    def __init__(self) -> None:
        # Keyed by (dataset_id, branch, processing_version)
        self._store: Dict[tuple, DatasetVersion] = {}
        # Ordered insertion log for history traversal
        self._log: List[DatasetVersion] = []

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def register(
        self,
        dataset_id: str,
        pipeline_params: Dict[str, object],
        branch: str = "main",
        notes: str = "",
    ) -> DatasetVersion:
        """
        Record the initial version (1.0.0) of a brand-new dataset.

        Parameters
        ----------
        dataset_id : str
        pipeline_params : dict
            Pipeline parameters used to produce this dataset.
        branch : str
        notes : str

        Returns
        -------
        DatasetVersion
        """
        version = DatasetVersion(
            dataset_id=dataset_id,
            processing_version="1.0.0",
            content_hash=_content_hash(pipeline_params),
            branch=branch,
            pipeline_params=pipeline_params,
            notes=notes,
        )
        self._save(version)
        return version

    def commit(
        self,
        parent: DatasetVersion,
        new_pipeline_params: Dict[str, object],
        notes: str = "",
    ) -> DatasetVersion:
        """
        Create a new version derived from *parent*, bumping the patch version.

        Parameters
        ----------
        parent : DatasetVersion
        new_pipeline_params : dict
            Updated pipeline parameters.  Any change produces a new content hash.
        notes : str

        Returns
        -------
        DatasetVersion
        """
        new_version = DatasetVersion(
            dataset_id=parent.dataset_id,
            processing_version=_bump_patch(parent.processing_version),
            content_hash=_content_hash(new_pipeline_params),
            derived_from_dataset_id=parent.dataset_id,
            derived_from_version=parent.processing_version,
            branch=parent.branch,
            pipeline_params=new_pipeline_params,
            notes=notes,
        )
        self._save(new_version)
        return new_version

    def branch(
        self,
        parent: DatasetVersion,
        branch_name: str,
        notes: str = "",
    ) -> DatasetVersion:
        """
        Fork *parent* under *branch_name*, resetting patch to 0 of a new minor.

        The new version string is ``MAJOR.(MINOR+1).0`` so that branch versions
        sort after the parent but do not collide with further commits on *main*.

        Parameters
        ----------
        parent : DatasetVersion
        branch_name : str
        notes : str

        Returns
        -------
        DatasetVersion
        """
        major, minor, _ = parent.processing_version.split(".")
        new_ver = f"{major}.{int(minor) + 1}.0"
        new_version = DatasetVersion(
            dataset_id=parent.dataset_id,
            processing_version=new_ver,
            content_hash=_content_hash(parent.pipeline_params),
            derived_from_dataset_id=parent.dataset_id,
            derived_from_version=parent.processing_version,
            branch=branch_name,
            pipeline_params=dict(parent.pipeline_params),
            notes=notes or f"Branched from {parent.branch}@{parent.processing_version}",
        )
        self._save(new_version)
        return new_version

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def latest(self, dataset_id: str, branch: str = "main") -> Optional[DatasetVersion]:
        """Return the most recently registered version on *branch*."""
        candidates = [
            v for v in self._log
            if v.dataset_id == dataset_id and v.branch == branch
        ]
        return candidates[-1] if candidates else None

    def history(self, version: DatasetVersion) -> List[DatasetVersion]:
        """
        Return the full lineage chain for *version*, oldest first.

        Traverses ``derived_from_version`` pointers back to the root.
        """
        chain: List[DatasetVersion] = [version]
        current = version
        while current.derived_from_version is not None:
            key = (
                current.derived_from_dataset_id,
                current.branch,
                current.derived_from_version,
            )
            parent = self._store.get(key)
            if parent is None:
                # Try any branch (lineage may cross branches)
                parent = next(
                    (
                        v for v in self._log
                        if v.dataset_id == current.derived_from_dataset_id
                        and v.processing_version == current.derived_from_version
                    ),
                    None,
                )
            if parent is None:
                break
            chain.append(parent)
            current = parent
        chain.reverse()
        return chain

    def all_versions(self, dataset_id: str) -> List[DatasetVersion]:
        """Return all registered versions for *dataset_id*, in insertion order."""
        return [v for v in self._log if v.dataset_id == dataset_id]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _save(self, version: DatasetVersion) -> None:
        key = (version.dataset_id, version.branch, version.processing_version)
        if key in self._store:
            raise ValueError(
                f"Version {version.processing_version} on branch '{version.branch}' "
                f"already exists for dataset '{version.dataset_id}'."
            )
        self._store[key] = version
        self._log.append(version)
