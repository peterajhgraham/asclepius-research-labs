"""Shared pytest fixtures / path setup for the backend test suite.

The backend imports the repo-root ``causal/`` and ``graph/`` packages at
runtime (via ``app.services.graph_service``), so make sure the repo root is on
``sys.path`` for tests that import them directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

# .../asclepius/backend/tests/conftest.py -> repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
