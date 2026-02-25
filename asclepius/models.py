"""
Biological state graph models for Asclepius Research Labs.

These models represent the core relational structure of a biological
experiment as a versioned, queryable state graph.

Entities:
- Experiment  → top-level container for a biological experiment
- Sample      → a sample within an experiment with perturbation metadata
- CellState   → the observed state of a single cell
- ProcessingPipeline → a versioned preprocessing pipeline
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from asclepius.schema import CellState, Experiment, ProcessingPipeline, Sample


@dataclass
class BiologicalStateGraph:
    """
    A complete, versioned representation of a biological experiment
    as a relational state graph.

    Attributes
    ----------
    experiment : Experiment
        Top-level experiment metadata.
    pipeline : ProcessingPipeline
        The preprocessing pipeline used.
    samples : list of Sample
        All samples collected in this experiment.
    cell_states : list of CellState
        All observed cell states, keyed to samples.
    """

    experiment: Experiment
    pipeline: ProcessingPipeline
    samples: List[Sample] = field(default_factory=list)
    cell_states: List[CellState] = field(default_factory=list)

    # --- convenience accessors -------------------------------------------------

    def samples_for_experiment(self) -> List[Sample]:
        """Return all samples belonging to this graph's experiment."""
        return [s for s in self.samples if s.experiment_id == self.experiment.id]

    def cell_states_for_sample(self, sample_id: str) -> List[CellState]:
        """Return all cell states belonging to *sample_id*."""
        return [c for c in self.cell_states if c.sample_id == sample_id]

    def add_sample(self, sample: Sample) -> None:
        """Append a sample; raises ValueError if sample.experiment_id is wrong."""
        if sample.experiment_id != self.experiment.id:
            raise ValueError(
                f"Sample experiment_id '{sample.experiment_id}' does not match "
                f"graph experiment id '{self.experiment.id}'."
            )
        self.samples.append(sample)

    def add_cell_state(self, cell_state: CellState) -> None:
        """Append a cell state; raises ValueError if sample_id not found."""
        known_ids = {s.id for s in self.samples}
        if cell_state.sample_id not in known_ids:
            raise ValueError(
                f"CellState sample_id '{cell_state.sample_id}' not found in graph."
            )
        self.cell_states.append(cell_state)

    # --- summary ----------------------------------------------------------------

    def summary(self) -> Dict[str, object]:
        """Return a plain-dict summary suitable for logging or display."""
        return {
            "experiment_id": self.experiment.id,
            "organism": self.experiment.organism,
            "assay_type": self.experiment.assay_type,
            "pipeline_version": self.pipeline.software_version,
            "n_samples": len(self.samples),
            "n_cell_states": len(self.cell_states),
        }
