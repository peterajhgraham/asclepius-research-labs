"""Disease dossier / paper context memory service.

Provides persistent in-memory storage for user research sessions:
- Save and retrieve queries with structured results
- Build disease-specific dossiers that accumulate insights
- Attach notes to queries and dossiers
- Export dossiers as structured JSON

In production this would be backed by a database; for now we use
an in-memory store that persists across the server lifetime.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DossierEntry:
    """A single entry in a disease dossier (one query + result + notes)."""

    def __init__(
        self,
        query: str,
        response: Dict[str, Any],
        notes: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.query = query
        self.response = response
        self.notes = notes
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "notes": self.notes,
            "created_at": self.created_at,
        }


class Dossier:
    """A disease dossier that accumulates structured research insights."""

    def __init__(
        self,
        name: str,
        description: str = "",
    ) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.entries: List[DossierEntry] = []
        self.tags: List[str] = []
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def add_entry(
        self,
        query: str,
        response: Dict[str, Any],
        notes: str = "",
    ) -> DossierEntry:
        entry = DossierEntry(query=query, response=response, notes=notes)
        self.entries.append(entry)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return entry

    def update_entry_notes(self, entry_id: str, notes: str) -> bool:
        for entry in self.entries:
            if entry.id == entry_id:
                entry.notes = notes
                self.updated_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def remove_entry(self, entry_id: str) -> bool:
        for i, entry in enumerate(self.entries):
            if entry.id == entry_id:
                self.entries.pop(i)
                self.updated_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def get_accumulated_insights(self) -> Dict[str, Any]:
        """Aggregate structured reasoning across all entries."""
        all_cells: List[str] = []
        all_cytokines: List[str] = []
        all_pathways: List[str] = []
        all_targets: List[str] = []
        all_genes: List[str] = []
        all_hypotheses: List[str] = []
        all_sources: List[str] = []
        queries: List[str] = []

        for entry in self.entries:
            queries.append(entry.query)
            resp = entry.response
            reasoning = resp.get("reasoning", {})
            all_cells.extend(reasoning.get("key_cells", []))
            all_cytokines.extend(reasoning.get("key_cytokines", []))
            all_pathways.extend(reasoning.get("pathways", []))
            all_targets.extend(reasoning.get("therapeutic_targets", []))
            all_genes.extend(reasoning.get("genes", []))
            all_hypotheses.extend(reasoning.get("open_questions", []))
            all_sources.extend(resp.get("sources", []))

        return {
            "total_queries": len(self.entries),
            "queries": queries,
            "key_cells": _dedupe(all_cells),
            "key_cytokines": _dedupe(all_cytokines),
            "pathways": _dedupe(all_pathways),
            "therapeutic_targets": _dedupe(all_targets),
            "genes": _dedupe(all_genes),
            "hypotheses": _dedupe(all_hypotheses),
            "sources": _dedupe(all_sources),
            "notes": [
                {"entry_id": e.id, "query": e.query, "notes": e.notes}
                for e in self.entries if e.notes
            ],
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "entry_count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "entry_count": len(self.entries),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DossierStore:
    """In-memory store for disease dossiers."""

    def __init__(self) -> None:
        self._dossiers: Dict[str, Dossier] = {}

    def create_dossier(
        self,
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dossier:
        dossier = Dossier(name=name, description=description)
        if tags:
            dossier.tags = tags
        self._dossiers[dossier.id] = dossier
        logger.info("Created dossier: %s (%s)", name, dossier.id)
        return dossier

    def get_dossier(self, dossier_id: str) -> Optional[Dossier]:
        return self._dossiers.get(dossier_id)

    def list_dossiers(self) -> List[Dict[str, Any]]:
        return [d.to_summary() for d in self._dossiers.values()]

    def delete_dossier(self, dossier_id: str) -> bool:
        if dossier_id in self._dossiers:
            del self._dossiers[dossier_id]
            return True
        return False

    def add_to_dossier(
        self,
        dossier_id: str,
        query: str,
        response: Dict[str, Any],
        notes: str = "",
    ) -> Optional[Dict[str, Any]]:
        dossier = self._dossiers.get(dossier_id)
        if not dossier:
            return None
        entry = dossier.add_entry(query=query, response=response, notes=notes)
        return entry.to_dict()

    def get_insights(self, dossier_id: str) -> Optional[Dict[str, Any]]:
        dossier = self._dossiers.get(dossier_id)
        if not dossier:
            return None
        return dossier.get_accumulated_insights()


def _dedupe(items: List[str]) -> List[str]:
    """Deduplicate while preserving order."""
    seen: set = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# Singleton store
dossier_store = DossierStore()
