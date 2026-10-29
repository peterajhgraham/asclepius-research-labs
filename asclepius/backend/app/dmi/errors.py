"""Errors that mean a report could not be produced, as opposed to an empty result."""

from __future__ import annotations


class ReportUnavailableError(RuntimeError):
    """An upstream dependency (PubMed, the LLM) failed, so there is no honest report to return.

    Routes turn this into a 503 with the message as `detail`, so the UI can show
    what went wrong instead of a blank or "no literature found" report.
    """


class LiteratureUnavailableError(ReportUnavailableError):
    """PubMed could not be reached (as opposed to a search that found nothing)."""


class ExtractionUnavailableError(ReportUnavailableError):
    """The LLM extraction step is not configured or failed."""
