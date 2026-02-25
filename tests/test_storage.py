"""
Tests for the SQLite-backed storage layer.
"""

from datetime import date, datetime

import pytest

from asclepius.models.batch import Batch
from asclepius.models.ontology import OntologyNamespace, OntologyTerm
from asclepius.models.perturbation import Perturbation, PerturbationType
from asclepius.models.rnaseq import (
    LibraryStrategy,
    RNASeqExperiment,
    Sample,
    StrandednessProtocol,
)
from asclepius.storage.database import Database


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #


@pytest.fixture
def db() -> Database:
    """Return a fresh in-memory database for each test."""
    return Database(":memory:")


@pytest.fixture
def experiment() -> RNASeqExperiment:
    exp = RNASeqExperiment(
        experiment_id="EXP_001",
        name="Drug Screen",
        description="A perturbation screen",
        created_at=datetime(2024, 6, 1, 9, 0, 0),
    )
    exp.add_sample(
        Sample(
            sample_id="S001",
            organism="Homo sapiens",
            tissue="PBMC",
            library_strategy=LibraryStrategy.POLY_A,
            strandedness=StrandednessProtocol.REVERSE,
            batch_id="B001",
        )
    )
    return exp


@pytest.fixture
def batch() -> Batch:
    return Batch(
        batch_id="B001",
        experiment_id="EXP_001",
        sequencing_date=date(2024, 6, 1),
        sequencing_platform="Illumina NovaSeq 6000",
    )


@pytest.fixture
def perturbation() -> Perturbation:
    return Perturbation(
        perturbation_id="P001",
        name="Imatinib 1 uM",
        perturbation_type=PerturbationType.SMALL_MOLECULE,
        compound_name="Imatinib",
        dose_value=1.0,
        dose_unit="uM",
        duration_hours=24.0,
    )


@pytest.fixture
def ontology_term() -> OntologyTerm:
    return OntologyTerm(
        term_id="GO:0006915",
        namespace=OntologyNamespace.GO,
        label="apoptotic process",
    )


# ------------------------------------------------------------------ #
# Experiment storage tests                                            #
# ------------------------------------------------------------------ #


class TestExperimentStorage:
    def test_save_and_retrieve(self, db, experiment):
        db.save_experiment(experiment)
        retrieved = db.get_experiment("EXP_001")
        assert retrieved is not None
        assert retrieved.experiment_id == "EXP_001"
        assert len(retrieved.samples) == 1

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_experiment("DOES_NOT_EXIST") is None

    def test_list_experiments(self, db, experiment):
        db.save_experiment(experiment)
        exps = db.list_experiments()
        assert len(exps) == 1
        assert exps[0].experiment_id == "EXP_001"

    def test_overwrite_experiment(self, db, experiment):
        db.save_experiment(experiment)
        experiment.name = "Updated Name"
        db.save_experiment(experiment)
        retrieved = db.get_experiment("EXP_001")
        assert retrieved.name == "Updated Name"


# ------------------------------------------------------------------ #
# Version history tests                                               #
# ------------------------------------------------------------------ #


class TestVersionHistory:
    def test_single_save_creates_one_history_entry(self, db, experiment):
        db.save_experiment(experiment)
        history = db.get_version_history("EXP_001")
        assert len(history) == 1
        assert "content_hash" in history[0]
        assert "recorded_at" in history[0]

    def test_multiple_saves_append_history(self, db, experiment):
        db.save_experiment(experiment)
        # Add a second sample to change the hash
        experiment.add_sample(
            Sample(
                sample_id="S002",
                organism="Homo sapiens",
                tissue="liver",
                library_strategy=LibraryStrategy.POLY_A,
                strandedness=StrandednessProtocol.REVERSE,
                batch_id="B001",
            )
        )
        db.save_experiment(experiment)
        history = db.get_version_history("EXP_001")
        assert len(history) == 2
        assert history[0]["content_hash"] != history[1]["content_hash"]

    def test_empty_history_for_unknown_experiment(self, db):
        assert db.get_version_history("UNKNOWN") == []


# ------------------------------------------------------------------ #
# Batch storage tests                                                 #
# ------------------------------------------------------------------ #


class TestBatchStorage:
    def test_save_and_retrieve(self, db, batch):
        db.save_batch(batch)
        retrieved = db.get_batch("B001")
        assert retrieved is not None
        assert retrieved.experiment_id == "EXP_001"

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_batch("MISSING") is None

    def test_list_batches_filtered_by_experiment(self, db):
        b1 = Batch(
            batch_id="B001",
            experiment_id="EXP_001",
            sequencing_date=date(2024, 1, 1),
            sequencing_platform="Illumina",
        )
        b2 = Batch(
            batch_id="B002",
            experiment_id="EXP_002",
            sequencing_date=date(2024, 2, 1),
            sequencing_platform="Illumina",
        )
        db.save_batch(b1)
        db.save_batch(b2)
        result = db.list_batches(experiment_id="EXP_001")
        assert len(result) == 1
        assert result[0].batch_id == "B001"


# ------------------------------------------------------------------ #
# Perturbation storage tests                                          #
# ------------------------------------------------------------------ #


class TestPerturbationStorage:
    def test_save_and_retrieve(self, db, perturbation):
        db.save_perturbation(perturbation)
        retrieved = db.get_perturbation("P001")
        assert retrieved is not None
        assert retrieved.compound_name == "Imatinib"

    def test_list_perturbations(self, db, perturbation):
        db.save_perturbation(perturbation)
        result = db.list_perturbations()
        assert len(result) == 1

    def test_get_nonexistent_returns_none(self, db):
        assert db.get_perturbation("MISSING") is None


# ------------------------------------------------------------------ #
# Ontology term storage tests                                         #
# ------------------------------------------------------------------ #


class TestOntologyTermStorage:
    def test_save_and_retrieve(self, db, ontology_term):
        db.save_ontology_term(ontology_term)
        retrieved = db.get_ontology_term("GO:0006915")
        assert retrieved is not None
        assert retrieved.label == "apoptotic process"

    def test_filter_by_namespace(self, db):
        go_term = OntologyTerm(
            term_id="GO:0006915",
            namespace=OntologyNamespace.GO,
            label="apoptotic process",
        )
        doid_term = OntologyTerm(
            term_id="DOID:9352",
            namespace=OntologyNamespace.DOID,
            label="type 2 diabetes mellitus",
        )
        db.save_ontology_term(go_term)
        db.save_ontology_term(doid_term)

        go_terms = db.list_ontology_terms(namespace=OntologyNamespace.GO)
        assert len(go_terms) == 1
        assert go_terms[0].term_id == "GO:0006915"

    def test_exclude_deprecated(self, db):
        active = OntologyTerm(
            term_id="GO:0008150",
            namespace=OntologyNamespace.GO,
            label="biological_process",
        )
        deprecated = OntologyTerm(
            term_id="GO:0000000",
            namespace=OntologyNamespace.GO,
            label="obsolete",
            is_deprecated=True,
        )
        db.save_ontology_term(active)
        db.save_ontology_term(deprecated)

        result = db.list_ontology_terms(include_deprecated=False)
        assert all(not t.is_deprecated for t in result)
        assert len(result) == 1
