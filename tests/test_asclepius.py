"""
Tests for the Asclepius structured biological data layer.

Covers:
- asclepius.schema    (Experiment, Sample, CellState, ProcessingPipeline)
- asclepius.models    (BiologicalStateGraph)
- asclepius.ingestion (load_metadata_csv, load_expression_csv, ingest)
- asclepius.versioning (VersionRegistry)
- asclepius.database  (init_db, SessionLocal)
- asclepius.db_models (ORM models)
- asclepius.ontology  (normalize_term, add_term)
- asclepius.query     (query_samples, get_lineage, query_datasets)
- asclepius.cli       (ingest-scrna, list-experiments, lineage commands)
- asclepius.api       (FastAPI endpoints)
- asclepius.export    (export_expression_matrix)
"""

import csv
import json
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
    load_10x_mtx,
    load_10x_h5,
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

    def test_load_10x_mtx(self, tmp_path):
        import gzip
        import scipy.io
        import scipy.sparse

        mtx_dir = tmp_path / "mtx"
        mtx_dir.mkdir()

        barcodes = ["AAACATAC-1", "AAACCGTG-1"]
        features = [("ENSG001", "GeneA", "Gene Expression"), ("ENSG002", "GeneB", "Gene Expression")]

        with gzip.open(mtx_dir / "barcodes.tsv.gz", "wt") as fh:
            fh.write("\n".join(barcodes) + "\n")
        with gzip.open(mtx_dir / "features.tsv.gz", "wt") as fh:
            for f in features:
                fh.write("\t".join(f) + "\n")

        # genes × cells sparse matrix: 2 genes × 2 cells
        data = scipy.sparse.coo_matrix([[3, 0], [1, 7]], dtype=float)
        with gzip.open(mtx_dir / "matrix.mtx.gz", "wb") as fh:
            scipy.io.mmwrite(fh, data)

        matrix = load_10x_mtx(mtx_dir)
        assert matrix.cell_ids == barcodes
        assert matrix.gene_ids == ["ENSG001", "ENSG002"]
        assert len(matrix.counts) == 2      # 2 cells
        assert len(matrix.counts[0]) == 2  # 2 genes
        assert matrix.counts[0][0] == 3.0  # cell 0, gene 0
        assert matrix.counts[1][1] == 7.0  # cell 1, gene 1

    def test_load_10x_mtx_plain_files(self, tmp_path):
        import scipy.io
        import scipy.sparse

        mtx_dir = tmp_path / "mtx_plain"
        mtx_dir.mkdir()

        barcodes = ["CELL1-1"]
        with open(mtx_dir / "barcodes.tsv", "w") as fh:
            fh.write("CELL1-1\n")
        with open(mtx_dir / "features.tsv", "w") as fh:
            fh.write("ENSG001\tGeneA\tGene Expression\n")

        data = scipy.sparse.coo_matrix([[5]], dtype=float)
        scipy.io.mmwrite(str(mtx_dir / "matrix.mtx"), data)

        matrix = load_10x_mtx(mtx_dir)
        assert matrix.cell_ids == ["CELL1-1"]
        assert matrix.gene_ids == ["ENSG001"]
        assert matrix.counts[0][0] == 5.0

    def test_load_10x_h5(self, tmp_path):
        import h5py
        import numpy as np
        import scipy.sparse

        h5_path = tmp_path / "matrix.h5"

        barcodes = [b"AAACATAC-1", b"AAACCGTG-1"]
        gene_ids = [b"ENSG001", b"ENSG002"]

        # genes × cells CSC matrix
        dense = np.array([[3, 0], [1, 7]], dtype=np.int32)
        mat = scipy.sparse.csc_matrix(dense)

        with h5py.File(h5_path, "w") as f:
            grp = f.create_group("matrix")
            grp.create_dataset("barcodes", data=barcodes)
            grp.create_dataset("data", data=mat.data.astype(np.int32))
            grp.create_dataset("indices", data=mat.indices)
            grp.create_dataset("indptr", data=mat.indptr)
            grp.create_dataset("shape", data=np.array(mat.shape, dtype=np.int32))
            feat = grp.create_group("features")
            feat.create_dataset("id", data=gene_ids)

        matrix = load_10x_h5(h5_path)
        assert len(matrix.cell_ids) == 2
        assert len(matrix.gene_ids) == 2
        assert matrix.counts[0][0] == 3.0  # cell 0, gene 0
        assert matrix.counts[1][1] == 7.0  # cell 1, gene 1
        assert matrix.source_path == str(h5_path)


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


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixture: in-memory SQLite session for all DB tests
# ─────────────────────────────────────────────────────────────────────────────

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session():
    """Yield a fresh in-memory SQLite session for each test."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    from asclepius.database import Base
    import asclepius.db_models  # noqa: F401 – registers models
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ─────────────────────────────────────────────────────────────────────────────
# database.py
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabase:
    def test_init_db_creates_tables(self, db_session):
        from sqlalchemy import inspect
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        assert "experiments" in tables
        assert "samples" in tables
        assert "files" in tables
        assert "pipelines" in tables
        assert "datasets" in tables
        assert "ontology_terms" in tables


# ─────────────────────────────────────────────────────────────────────────────
# db_models.py
# ─────────────────────────────────────────────────────────────────────────────

class TestDbModels:
    def _make_experiment(self, db_session, name="Test Exp"):
        from asclepius.db_models import Experiment
        exp = Experiment(name=name, organism="NCBITaxon:9606", assay_type="scRNA-seq")
        db_session.add(exp)
        db_session.flush()
        return exp

    def _make_pipeline(self, db_session, commit_hash="abc123"):
        from asclepius.db_models import Pipeline
        pipe = Pipeline(name="test-pipeline", git_commit_hash=commit_hash)
        db_session.add(pipe)
        db_session.flush()
        return pipe

    def test_create_experiment(self, db_session):
        exp = self._make_experiment(db_session)
        assert exp.id is not None
        assert exp.name == "Test Exp"

    def test_create_sample(self, db_session):
        from asclepius.db_models import Sample
        exp = self._make_experiment(db_session)
        sample = Sample(
            experiment_id=exp.id,
            cell_type="T cell",
            condition="treated",
            replicate="rep1",
            batch_id="batch_A",
        )
        db_session.add(sample)
        db_session.flush()
        assert sample.id is not None
        assert sample.experiment_id == exp.id

    def test_create_pipeline(self, db_session):
        pipe = self._make_pipeline(db_session)
        assert pipe.id is not None
        assert pipe.git_commit_hash == "abc123"

    def test_create_dataset_with_parent(self, db_session):
        from asclepius.db_models import Dataset
        exp = self._make_experiment(db_session)
        pipe = self._make_pipeline(db_session)

        ds1 = Dataset(experiment_id=exp.id, pipeline_id=pipe.id, notes="v1")
        db_session.add(ds1)
        db_session.flush()

        ds2 = Dataset(
            experiment_id=exp.id,
            pipeline_id=pipe.id,
            parent_dataset_id=ds1.id,
            notes="v2",
        )
        db_session.add(ds2)
        db_session.flush()

        assert ds2.parent.id == ds1.id
        assert ds1.children[0].id == ds2.id

    def test_create_ontology_term(self, db_session):
        from asclepius.db_models import OntologyTerm
        term = OntologyTerm(
            raw_term="T cell",
            normalized_term="CL:0000084",
            namespace="cell_type",
        )
        db_session.add(term)
        db_session.flush()
        assert term.id is not None

    def test_create_file(self, db_session):
        from asclepius.db_models import File, Sample
        exp = self._make_experiment(db_session)
        sample = Sample(experiment_id=exp.id, cell_type="B cell")
        db_session.add(sample)
        db_session.flush()
        f = File(
            sample_id=sample.id,
            file_type="expression_csv",
            file_path="/data/expr.csv",
            checksum="deadbeef",
            pipeline_version="abc123",
        )
        db_session.add(f)
        db_session.flush()
        assert f.id is not None


# ─────────────────────────────────────────────────────────────────────────────
# ontology.py
# ─────────────────────────────────────────────────────────────────────────────

class TestOntology:
    def test_normalize_unknown_term_passthrough(self, db_session):
        from asclepius.ontology import normalize_term
        result = normalize_term(db_session, "unknown cell", "cell_type")
        assert result == "unknown cell"

    def test_add_and_normalize_term(self, db_session):
        from asclepius.ontology import add_term, normalize_term
        add_term(db_session, "T cell", "CL:0000084", namespace="cell_type", commit=False)
        result = normalize_term(db_session, "T cell", namespace="cell_type")
        assert result == "CL:0000084"

    def test_update_existing_term(self, db_session):
        from asclepius.ontology import add_term, normalize_term
        add_term(db_session, "human", "NCBITaxon:9606", namespace="organism", commit=False)
        add_term(db_session, "human", "NCBITaxon:9606_updated", namespace="organism", commit=False)
        result = normalize_term(db_session, "human", namespace="organism")
        assert result == "NCBITaxon:9606_updated"

    def test_normalize_case_insensitive(self, db_session):
        from asclepius.ontology import add_term, normalize_term
        add_term(db_session, "T Cell", "CL:0000084", namespace="cell_type", commit=False)
        result = normalize_term(db_session, "t cell", namespace="cell_type")
        assert result == "CL:0000084"

    def test_normalize_without_namespace(self, db_session):
        from asclepius.ontology import add_term, normalize_term
        add_term(db_session, "mouse", "NCBITaxon:10090", commit=False)
        result = normalize_term(db_session, "mouse")
        assert result == "NCBITaxon:10090"


# ─────────────────────────────────────────────────────────────────────────────
# query.py
# ─────────────────────────────────────────────────────────────────────────────

def _populate_db(db_session):
    """Insert two experiments with two samples each and a dataset tree."""
    from asclepius.db_models import Dataset, Experiment, Pipeline, Sample

    exp1 = Experiment(name="Exp1", organism="NCBITaxon:9606", assay_type="scRNA-seq")
    exp2 = Experiment(name="Exp2", organism="NCBITaxon:10090", assay_type="ATAC-seq")
    db_session.add_all([exp1, exp2])
    db_session.flush()

    s1 = Sample(experiment_id=exp1.id, cell_type="T cell", condition="treated", replicate="rep1", batch_id="B1")
    s2 = Sample(experiment_id=exp1.id, cell_type="B cell", condition="control", replicate="rep1", batch_id="B1")
    s3 = Sample(experiment_id=exp2.id, cell_type="T cell", condition="treated", replicate="rep2", batch_id="B2")
    db_session.add_all([s1, s2, s3])

    pipe = Pipeline(name="pipe", git_commit_hash="abc")
    db_session.add(pipe)
    db_session.flush()

    ds1 = Dataset(experiment_id=exp1.id, pipeline_id=pipe.id, notes="root")
    db_session.add(ds1)
    db_session.flush()

    ds2 = Dataset(experiment_id=exp1.id, pipeline_id=pipe.id, parent_dataset_id=ds1.id, notes="child")
    db_session.add(ds2)
    db_session.flush()

    return exp1, exp2, s1, s2, s3, pipe, ds1, ds2


class TestQuery:
    def test_query_samples_no_filter(self, db_session):
        from asclepius.query import query_samples
        _populate_db(db_session)
        results = query_samples(db_session)
        assert len(results) == 3

    def test_query_samples_by_cell_type(self, db_session):
        from asclepius.query import query_samples
        _populate_db(db_session)
        results = query_samples(db_session, cell_type="T cell")
        assert len(results) == 2
        assert all(s.cell_type == "T cell" for s in results)

    def test_query_samples_by_condition(self, db_session):
        from asclepius.query import query_samples
        _populate_db(db_session)
        results = query_samples(db_session, condition="control")
        assert len(results) == 1

    def test_query_samples_by_assay_type(self, db_session):
        from asclepius.query import query_samples
        _populate_db(db_session)
        results = query_samples(db_session, assay_type="scRNA-seq")
        assert len(results) == 2

    def test_query_samples_by_organism(self, db_session):
        from asclepius.query import query_samples
        _populate_db(db_session)
        results = query_samples(db_session, organism="NCBITaxon:10090")
        assert len(results) == 1

    def test_query_samples_combined_filters(self, db_session):
        from asclepius.query import query_samples
        _populate_db(db_session)
        results = query_samples(db_session, cell_type="T cell", organism="NCBITaxon:9606")
        assert len(results) == 1

    def test_get_lineage_root(self, db_session):
        from asclepius.query import get_lineage
        _, _, _, _, _, _, ds1, _ = _populate_db(db_session)
        chain = get_lineage(db_session, ds1.id)
        assert len(chain) == 1
        assert chain[0] == ds1.id

    def test_get_lineage_child(self, db_session):
        from asclepius.query import get_lineage
        _, _, _, _, _, _, ds1, ds2 = _populate_db(db_session)
        chain = get_lineage(db_session, ds2.id)
        assert len(chain) == 2
        assert chain[0] == ds1.id
        assert chain[1] == ds2.id

    def test_get_lineage_not_found(self, db_session):
        from asclepius.query import get_lineage
        import uuid
        chain = get_lineage(db_session, uuid.uuid4())
        assert chain == []

    def test_query_datasets_by_experiment(self, db_session):
        from asclepius.query import query_datasets
        exp1, _, _, _, _, _, ds1, ds2 = _populate_db(db_session)
        results = query_datasets(db_session, experiment_id=exp1.id)
        assert len(results) == 2

    def test_query_datasets_by_pipeline(self, db_session):
        from asclepius.query import query_datasets
        _, _, _, _, _, pipe, ds1, ds2 = _populate_db(db_session)
        results = query_datasets(db_session, pipeline_id=pipe.id)
        assert len(results) == 2


# ─────────────────────────────────────────────────────────────────────────────
# cli.py
# ─────────────────────────────────────────────────────────────────────────────

class TestCli:
    def _make_counts_csv(self, path):
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["cell_id", "GENE_A", "GENE_B"])
            writer.writeheader()
            writer.writerow({"cell_id": "C1", "GENE_A": "10", "GENE_B": "5"})

    def _make_metadata_json(self, path, extra=None):
        meta = {
            "cell_type": "T cell",
            "condition": "treated",
            "replicate": "rep1",
            "batch_id": "batch_A",
        }
        if extra:
            meta.update(extra)
        with open(path, "w") as f:
            json.dump(meta, f)

    def test_ingest_scrna_success(self, tmp_path):
        from typer.testing import CliRunner
        from asclepius.cli import app
        from asclepius.db_models import Experiment
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from asclepius.database import Base
        import asclepius.db_models  # noqa: F401

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        exp = Experiment(name="CLI Test", organism="NCBITaxon:9606", assay_type="scRNA-seq")
        session.add(exp)
        session.commit()
        exp_id = str(exp.id)
        session.close()

        counts = tmp_path / "counts.csv"
        self._make_counts_csv(counts)
        metadata = tmp_path / "meta.json"
        self._make_metadata_json(metadata)

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ingest-scrna",
                "--counts", str(counts),
                "--metadata", str(metadata),
                "--experiment-id", exp_id,
                "--pipeline-hash", "deadbeef",
                "--db-url", db_url,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Dataset registered" in result.output

    def test_ingest_scrna_missing_metadata_field(self, tmp_path):
        from typer.testing import CliRunner
        from asclepius.cli import app
        from asclepius.db_models import Experiment
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from asclepius.database import Base
        import asclepius.db_models  # noqa: F401

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"

        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        exp = Experiment(name="CLI Test", organism="NCBITaxon:9606", assay_type="scRNA-seq")
        session.add(exp)
        session.commit()
        exp_id = str(exp.id)
        session.close()

        counts = tmp_path / "counts.csv"
        self._make_counts_csv(counts)
        metadata = tmp_path / "meta.json"
        with open(metadata, "w") as f:
            json.dump({"cell_type": "T cell"}, f)  # missing fields

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "ingest-scrna",
                "--counts", str(counts),
                "--metadata", str(metadata),
                "--experiment-id", str(exp_id),
                "--pipeline-hash", "abc",
                "--db-url", db_url,
            ],
        )
        assert result.exit_code != 0

    def test_list_experiments(self, tmp_path):
        from typer.testing import CliRunner
        from asclepius.cli import app
        from asclepius.db_models import Experiment
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from asclepius.database import Base
        import asclepius.db_models  # noqa: F401

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        exp = Experiment(name="My Experiment", organism="NCBITaxon:9606", assay_type="scRNA-seq")
        session.add(exp)
        session.commit()
        session.close()

        runner = CliRunner()
        result = runner.invoke(app, ["list-experiments", "--db-url", db_url])
        assert result.exit_code == 0
        assert "My Experiment" in result.output

    def test_lineage_command(self, tmp_path):
        from typer.testing import CliRunner
        from asclepius.cli import app
        from asclepius.db_models import Dataset, Experiment, Pipeline
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from asclepius.database import Base
        import asclepius.db_models  # noqa: F401

        db_path = tmp_path / "test.db"
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        exp = Experiment(name="Exp", organism="NCBITaxon:9606", assay_type="scRNA-seq")
        pipe = Pipeline(name="pipe", git_commit_hash="abc")
        session.add_all([exp, pipe])
        session.flush()
        ds = Dataset(experiment_id=exp.id, pipeline_id=pipe.id)
        session.add(ds)
        session.commit()
        ds_id = str(ds.id)
        session.close()

        runner = CliRunner()
        result = runner.invoke(app, ["lineage", "--dataset-id", ds_id, "--db-url", db_url])
        assert result.exit_code == 0
        assert ds_id in result.output


# ─────────────────────────────────────────────────────────────────────────────
# api.py
# ─────────────────────────────────────────────────────────────────────────────

class TestApi:
    @pytest.fixture()
    def client(self, tmp_path):
        """Create a TestClient backed by a fresh in-memory SQLite database."""
        db_path = tmp_path / "api_test.db"
        db_url = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = db_url

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from asclepius.database import Base, get_db
        import asclepius.db_models  # noqa: F401

        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def override_get_db():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        from fastapi.testclient import TestClient
        from asclepius.api import app as api_app
        api_app.dependency_overrides[get_db] = override_get_db
        client = TestClient(api_app)
        yield client
        api_app.dependency_overrides.clear()

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_list_experiments_empty(self, client):
        resp = client.get("/experiments")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_and_get_experiment(self, client):
        payload = {
            "name": "PBMC 3k",
            "organism": "NCBITaxon:9606",
            "assay_type": "scRNA-seq",
            "description": "10x PBMC 3k dataset",
        }
        resp = client.post("/experiments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "PBMC 3k"
        exp_id = data["id"]

        resp2 = client.get(f"/experiments/{exp_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == exp_id

    def test_get_experiment_not_found(self, client):
        import uuid
        resp = client.get(f"/experiments/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_experiments_after_creation(self, client):
        client.post("/experiments", json={"name": "Exp A", "organism": "human"})
        client.post("/experiments", json={"name": "Exp B", "organism": "mouse"})
        resp = client.get("/experiments")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_search_samples_empty(self, client):
        resp = client.get("/samples")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_dataset_lineage_not_found(self, client):
        import uuid
        resp = client.get(f"/datasets/{uuid.uuid4()}/lineage")
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# export.py
# ─────────────────────────────────────────────────────────────────────────────

class TestExport:
    def test_export_expression_matrix(self, db_session, tmp_path):
        from asclepius.db_models import Dataset, Experiment, File, Pipeline, Sample
        from asclepius.export import export_expression_matrix

        # Write an expression CSV
        expr_path = tmp_path / "expr.csv"
        _write_csv(
            expr_path,
            [{"cell_id": "C1", "GENE_A": "3", "GENE_B": "7"}],
            ["cell_id", "GENE_A", "GENE_B"],
        )

        exp = Experiment(name="ExportTest", organism="NCBITaxon:9606", assay_type="scRNA-seq")
        pipe = Pipeline(name="pipe", git_commit_hash="abc")
        db_session.add_all([exp, pipe])
        db_session.flush()

        sample = Sample(
            experiment_id=exp.id,
            cell_type="T cell",
            condition="treated",
            replicate="rep1",
            batch_id="B1",
        )
        db_session.add(sample)
        db_session.flush()

        file_rec = File(
            sample_id=sample.id,
            file_type="expression_csv",
            file_path=str(expr_path),
            checksum="abc",
            pipeline_version="abc",
        )
        db_session.add(file_rec)

        ds = Dataset(experiment_id=exp.id, pipeline_id=pipe.id)
        db_session.add(ds)
        db_session.flush()

        matrix, meta = export_expression_matrix(db_session, ds.id)
        assert matrix.cell_ids == ["C1"]
        assert len(matrix.gene_ids) == 2
        assert matrix.counts[0][0] == 3.0
        assert len(meta) == 1
        assert meta[0]["cell_id"] == "C1"
        assert meta[0]["cell_type"] == "T cell"

    def test_export_dataset_not_found(self, db_session):
        import uuid
        from asclepius.export import export_expression_matrix
        with pytest.raises(ValueError, match="not found"):
            export_expression_matrix(db_session, uuid.uuid4())

    def test_export_no_files(self, db_session):
        from asclepius.db_models import Dataset, Experiment, Pipeline
        from asclepius.export import export_expression_matrix

        exp = Experiment(name="NoFiles", organism="NCBITaxon:9606", assay_type="scRNA-seq")
        pipe = Pipeline(name="pipe", git_commit_hash="abc")
        db_session.add_all([exp, pipe])
        db_session.flush()

        ds = Dataset(experiment_id=exp.id, pipeline_id=pipe.id)
        db_session.add(ds)
        db_session.flush()

        with pytest.raises(ValueError, match="No expression CSV files"):
            export_expression_matrix(db_session, ds.id)

