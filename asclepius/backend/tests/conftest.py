"""Shared pytest configuration for the backend test suite.

The backend is self-contained: its graph + causal logic is vendored in the
``app.kg`` package, so tests import everything from under ``app`` and no
repo-root path manipulation is required. (pytest's rootdir insertion already
puts ``asclepius/backend`` on ``sys.path`` via ``pytest.ini``.)
"""

from __future__ import annotations
