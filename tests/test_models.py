"""
Tests for RNA-seq, perturbation, batch, and ontology data models.
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


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #


def make_sample(sample_id: str = "S001", batch_id: str = "B001") -> Sample:
    return Sample(
        sample_id=sample_id,
        organism="Homo sapiens",
        tissue="liver",
        library_strategy=LibraryStrategy.POLY_A,
        strandedness=StrandednessProtocol.REVERSE,
        batch_id=batch_id,
    )


def make_experiment(experiment_id: str = "EXP_001") -> RNASeqExperiment:
    return RNASeqExperiment(
        experiment_id=experiment_id,
        name="Test Experiment",
        description="A test RNA-seq experiment",
        created_at=datetime(2024, 1, 15, 12, 0, 0),
    )


# ------------------------------------------------------------------ #
# Sample tests                                                        #
# ------------------------------------------------------------------ #


class TestSample:
    def test_round_trip(self):
        s = make_sample()
        assert Sample.from_dict(s.to_dict()) == s

    def test_optional_fields_default_none(self):
        s = make_sample()
        assert s.cell_line is None
        assert s.disease_ontology_term is None

    def test_perturbation_ids_default_empty(self):
        s = make_sample()
        assert s.perturbation_ids == []


# ------------------------------------------------------------------ #
# RNASeqExperiment tests                                              #
# ------------------------------------------------------------------ #


class TestRNASeqExperiment:
    def test_add_sample(self):
        exp = make_experiment()
        s = make_sample()
        exp.add_sample(s)
        assert len(exp.samples) == 1

    def test_add_duplicate_sample_raises(self):
        exp = make_experiment()
        exp.add_sample(make_sample("S001"))
        with pytest.raises(ValueError, match="already exists"):
            exp.add_sample(make_sample("S001"))

    def test_content_hash_is_stable(self):
        exp = make_experiment()
        exp.add_sample(make_sample())
        h1 = exp.content_hash()
        h2 = exp.content_hash()
        assert h1 == h2

    def test_content_hash_changes_with_sample(self):
        exp = make_experiment()
        h_before = exp.content_hash()
        exp.add_sample(make_sample())
        h_after = exp.content_hash()
        assert h_before != h_after

    def test_round_trip(self):
        exp = make_experiment()
        exp.add_sample(make_sample())
        restored = RNASeqExperiment.from_dict(exp.to_dict())
        assert restored.experiment_id == exp.experiment_id
        assert len(restored.samples) == 1
        assert restored.samples[0].sample_id == "S001"


# ------------------------------------------------------------------ #
# Perturbation tests                                                  #
# ------------------------------------------------------------------ #


class TestPerturbation:
    def test_control_flag(self):
        control = Perturbation(
            perturbation_id="P_DMSO",
            name="DMSO",
            perturbation_type=PerturbationType.CONTROL,
        )
        assert control.is_control()

    def test_compound_not_control(self):
        drug = Perturbation(
            perturbation_id="P_IMA",
            name="Imatinib",
            perturbation_type=PerturbationType.SMALL_MOLECULE,
            compound_name="Imatinib",
            dose_value=1.0,
            dose_unit="uM",
        )
        assert not drug.is_control()

    def test_round_trip(self):
        p = Perturbation(
            perturbation_id="P_KO",
            name="BRCA1 KO",
            perturbation_type=PerturbationType.CRISPR_KO,
            target_gene_symbol="BRCA1",
        )
        assert Perturbation.from_dict(p.to_dict()) == p


# ------------------------------------------------------------------ #
# Batch tests                                                         #
# ------------------------------------------------------------------ #


class TestBatch:
    def test_round_trip(self):
        b = Batch(
            batch_id="B001",
            experiment_id="EXP_001",
            sequencing_date=date(2024, 3, 10),
            sequencing_platform="Illumina NovaSeq 6000",
            operator="Alice",
        )
        restored = Batch.from_dict(b.to_dict())
        assert restored.batch_id == b.batch_id
        assert restored.sequencing_date == date(2024, 3, 10)
        assert restored.operator == "Alice"

    def test_optional_fields_default_none(self):
        b = Batch(
            batch_id="B002",
            experiment_id="EXP_001",
            sequencing_date=date(2024, 4, 1),
            sequencing_platform="Illumina NextSeq 550",
        )
        assert b.flow_cell_id is None
        assert b.library_kit_lot is None


# ------------------------------------------------------------------ #
# OntologyTerm tests                                                  #
# ------------------------------------------------------------------ #


class TestOntologyTerm:
    def test_valid_term(self):
        term = OntologyTerm(
            term_id="GO:0008150",
            namespace=OntologyNamespace.GO,
            label="biological_process",
        )
        assert term.is_valid()
        assert term.curie == "GO:0008150"
        assert term.resolve() == "GO:0008150"

    def test_deprecated_term_without_replacement(self):
        term = OntologyTerm(
            term_id="GO:0000000",
            namespace=OntologyNamespace.GO,
            label="obsolete term",
            is_deprecated=True,
        )
        assert not term.is_valid()
        assert term.resolve() is None

    def test_deprecated_term_with_replacement(self):
        term = OntologyTerm(
            term_id="GO:0000001",
            namespace=OntologyNamespace.GO,
            label="old label",
            is_deprecated=True,
            deprecated_in_favor_of="GO:0000002",
        )
        assert term.resolve() == "GO:0000002"

    def test_round_trip(self):
        term = OntologyTerm(
            term_id="DOID:9352",
            namespace=OntologyNamespace.DOID,
            label="type 2 diabetes mellitus",
            synonyms=["T2D", "NIDDM"],
        )
        restored = OntologyTerm.from_dict(term.to_dict())
        assert restored.term_id == term.term_id
        assert restored.synonyms == ["T2D", "NIDDM"]
