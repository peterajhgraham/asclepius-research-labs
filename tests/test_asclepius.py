"""
Tests for the Asclepius structured biological data layer.

Covers:
- asclepius.schema    (Experiment, Sample, CellState, ProcessingPipeline)
- asclepius.models    (BiologicalStateGraph)
- asclepius.ingestion (load_metadata_csv, load_expression_csv, ingest)
- asclepius.versioning (VersionRegistry)
"""

import csv
import os
import tempfile
from datetime import date

import pytest

from asclepius.schema import CellState, Experiment, ProcessingPipeline, Sample
from asclepius.models import BiologicalStateGraph
from asclepius.ingestion import (
    ValidationError,
    ingest,
    load_expression_csv,
    load_metadata_csv,
)
from asclepius.versioning import VersionRegistry, _bump_patch


# ─────────────────────────────────────────────────────────────────────────────
# schema.py
# ─────────────────────────────────────────────────────────────────────────────

class TestSchema:
    def test_experiment_fields(self):
        exp = Experiment(
            id="EXP_001",
            organism="NCBITaxon:9606",
            assay_type="EFO:0009899",
            date=date(2024, 1, 1),
        )
        assert exp.id == "EXP_001"
        assert exp.pipeline_version == "1.0.0"

    def test_sample_defaults(self):
        s = Sample(id="S1", experiment_id="EXP_001")
        assert s.perturbation_type == ""
        assert s.dose is None

    def test_cell_state_defaults(self):
        c = CellState(id="CELL_001", sample_id="S1")
        assert c.processing_version == "1.0.0"
        assert c.annotation_label == ""

    def test_pipeline_defaults(self):
        p = ProcessingPipeline(
            id="pipe_1",
            reference_genome="GRCh38",
            normalization_method="log1p_CP10K",
        )
        assert p.batch_correction_method == ""
        assert p.software_version == "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# models.py
# ─────────────────────────────────────────────────────────────────────────────

class TestBiologicalStateGraph:
    def _make_graph(self):
        exp = Experiment(
            id="EXP_001",
            organism="NCBITaxon:9606",
            assay_type="EFO:0009899",
            date=date(2024, 1, 1),
        )
        pipe = ProcessingPipeline(
            id="pipe_1",
            reference_genome="GRCh38",
            normalization_method="log1p_CP10K",
        )
        return BiologicalStateGraph(experiment=exp, pipeline=pipe)

    def test_add_sample(self):
        graph = self._make_graph()
        sample = Sample(id="S1", experiment_id="EXP_001")
        graph.add_sample(sample)
        assert len(graph.samples) == 1

    def test_add_sample_wrong_experiment_raises(self):
        graph = self._make_graph()
        with pytest.raises(ValueError, match="experiment_id"):
            graph.add_sample(Sample(id="S1", experiment_id="WRONG"))

    def test_add_cell_state(self):
        graph = self._make_graph()
        graph.add_sample(Sample(id="S1", experiment_id="EXP_001"))
        graph.add_cell_state(CellState(id="C1", sample_id="S1"))
        assert len(graph.cell_states) == 1

    def test_add_cell_state_unknown_sample_raises(self):
        graph = self._make_graph()
        with pytest.raises(ValueError, match="sample_id"):
            graph.add_cell_state(CellState(id="C1", sample_id="UNKNOWN"))

    def test_summary_keys(self):
        graph = self._make_graph()
        s = graph.summary()
        assert "experiment_id" in s
        assert "n_samples" in s
        assert "n_cell_states" in s

    def test_cell_states_for_sample(self):
        graph = self._make_graph()
        graph.add_sample(Sample(id="S1", experiment_id="EXP_001"))
        graph.add_sample(Sample(id="S2", experiment_id="EXP_001"))
        graph.add_cell_state(CellState(id="C1", sample_id="S1"))
        graph.add_cell_state(CellState(id="C2", sample_id="S2"))
        assert len(graph.cell_states_for_sample("S1")) == 1


# ─────────────────────────────────────────────────────────────────────────────
# ingestion.py
# ─────────────────────────────────────────────────────────────────────────────

def _write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestIngestion:
    def test_load_metadata_csv(self, tmp_path):
        p = tmp_path / "meta.csv"
        _write_csv(
            p,
            [{"cell_id": "C1", "experiment_id": "E1", "assay_type": "10x", "organism": "human"}],
            ["cell_id", "experiment_id", "assay_type", "organism"],
        )
        cells = load_metadata_csv(p)
        assert len(cells) == 1
        assert cells[0].cell_id == "C1"
        assert cells[0].experiment_id == "E1"

    def test_load_metadata_csv_normalizes_columns(self, tmp_path):
        p = tmp_path / "meta.csv"
        _write_csv(
            p,
            [{"Cell ID": "C1", "Experiment ID": "E1", "Assay Type": "10x", "Organism": "human"}],
            ["Cell ID", "Experiment ID", "Assay Type", "Organism"],
        )
        cells = load_metadata_csv(p)
        assert cells[0].cell_id == "C1"

    def test_load_metadata_csv_missing_field_raises(self, tmp_path):
        p = tmp_path / "meta.csv"
        _write_csv(
            p,
            [{"cell_id": "C1", "experiment_id": "E1"}],
            ["cell_id", "experiment_id"],
        )
        with pytest.raises(ValidationError):
            load_metadata_csv(p)

    def test_load_expression_csv(self, tmp_path):
        p = tmp_path / "expr.csv"
        _write_csv(
            p,
            [{"cell_id": "C1", "GENE_A": "10", "GENE_B": "5"}],
            ["cell_id", "GENE_A", "GENE_B"],
        )
        matrix = load_expression_csv(p)
        assert matrix.cell_ids == ["C1"]
        assert len(matrix.gene_ids) == 2
        assert matrix.counts[0][0] == 10.0

    def test_ingest_with_expression(self, tmp_path):
        meta = tmp_path / "meta.csv"
        expr = tmp_path / "expr.csv"
        _write_csv(
            meta,
            [{"cell_id": "C1", "experiment_id": "E1", "assay_type": "10x", "organism": "human"}],
            ["cell_id", "experiment_id", "assay_type", "organism"],
        )
        _write_csv(
            expr,
            [{"cell_id": "C1", "GENE_A": "3"}],
            ["cell_id", "GENE_A"],
        )
        result = ingest(meta, expr)
        assert len(result.cells) == 1
        assert result.matrix is not None
        assert result.warnings == []

    def test_ingest_warns_on_cell_mismatch(self, tmp_path):
        meta = tmp_path / "meta.csv"
        expr = tmp_path / "expr.csv"
        _write_csv(
            meta,
            [{"cell_id": "C1", "experiment_id": "E1", "assay_type": "10x", "organism": "human"}],
            ["cell_id", "experiment_id", "assay_type", "organism"],
        )
        _write_csv(
            expr,
            [{"cell_id": "C2", "GENE_A": "3"}],  # C2 not in metadata
            ["cell_id", "GENE_A"],
        )
        result = ingest(meta, expr)
        assert len(result.warnings) == 2  # one for each direction


# ─────────────────────────────────────────────────────────────────────────────
# versioning.py
# ─────────────────────────────────────────────────────────────────────────────

class TestVersioning:
    def test_bump_patch(self):
        assert _bump_patch("1.0.0") == "1.0.1"
        assert _bump_patch("2.3.9") == "2.3.10"

    def test_bump_patch_invalid(self):
        with pytest.raises(ValueError):
            _bump_patch("v1.0")

    def test_register(self):
        reg = VersionRegistry()
        v = reg.register("DS1", {"norm": "log1p"})
        assert v.processing_version == "1.0.0"
        assert v.branch == "main"

    def test_commit_bumps_version(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        v2 = reg.commit(v1, {"norm": "scran"})
        assert v2.processing_version == "1.0.1"
        assert v2.derived_from_version == "1.0.0"

    def test_commit_different_params_changes_hash(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        v2 = reg.commit(v1, {"norm": "scran"})
        assert v1.content_hash != v2.content_hash

    def test_branch_creates_new_branch(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        v_branch = reg.branch(v1, "experiment-A")
        assert v_branch.branch == "experiment-A"
        assert v_branch.processing_version == "1.1.0"

    def test_latest(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        v2 = reg.commit(v1, {"norm": "scran"})
        assert reg.latest("DS1").processing_version == "1.0.1"

    def test_history(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        v2 = reg.commit(v1, {"norm": "scran"})
        v3 = reg.commit(v2, {"norm": "scran", "batch": "Harmony"})
        history = reg.history(v3)
        assert [h.processing_version for h in history] == ["1.0.0", "1.0.1", "1.0.2"]

    def test_duplicate_version_raises(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        with pytest.raises(ValueError):
            reg._save(v1)  # same key → should raise

    def test_all_versions(self):
        reg = VersionRegistry()
        v1 = reg.register("DS1", {"norm": "log1p"})
        reg.commit(v1, {"norm": "scran"})
        assert len(reg.all_versions("DS1")) == 2
