"""
Tests for the single-cell dataset observation, preprocessing provenance,
and unified schema modules.
"""

import pytest

from asclepius.singlecell.datasets import (
    DatasetCatalogue,
    DEFAULT_CATALOGUE,
    PBMC3K,
    TABULA_MURIS,
    CELLXGENE_LUNG,
    MetadataColumn,
    PublicDataset,
)
from asclepius.singlecell.preprocessing import (
    InconsistencyCategory,
    InconsistencyDetector,
    MetadataField,
    MetadataInconsistency,
    PreprocessingPipeline,
    PreprocessingStep,
    StepCategory,
    PBMC3K_PIPELINE,
    TABULA_MURIS_PIPELINE,
    CELLXGENE_LUNG_PIPELINE,
)
from asclepius.singlecell.schema import (
    DataLayer,
    GeneIdFormat,
    NormalisationStrategy,
    SchemaValidator,
    Sex,
    SuspensionType,
    UnifiedCell,
    UnifiedDataset,
    UnifiedGene,
    ValidationError,
)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #


def make_valid_cell(cell_id: str = "CELL_001") -> UnifiedCell:
    return UnifiedCell(
        cell_id=cell_id,
        dataset_id="pbmc3k",
        donor_id="D001",
        sample_id="S001",
        organism_ontology_term_id="NCBITaxon:9606",
        tissue_ontology_term_id="UBERON:0013756",
        cell_type_ontology_term_id="CL:0000084",
        disease_ontology_term_id="PATO:0000461",
        assay_ontology_term_id="EFO:0009899",
        sex=Sex.FEMALE,
        suspension_type=SuspensionType.CELL,
        n_counts=3500,
        n_genes=1200,
        pct_counts_mito=2.5,
        batch_id="B001",
        preprocessing_pipeline_id="pbmc3k_pipeline",
        doublet_score=0.05,
    )


def make_valid_dataset() -> UnifiedDataset:
    ds = UnifiedDataset(
        dataset_id="test_ds",
        title="Test Dataset",
        source_accession="GSE000000",
        layers=[
            DataLayer(
                name="counts",
                normalisation=NormalisationStrategy.RAW,
                ensembl_version="Ensembl_110",
                genome_assembly="GRCh38",
            )
        ],
    )
    ds.add_cell(make_valid_cell())
    ds.add_gene(
        UnifiedGene(
            feature_id="ENSG00000243485",
            feature_name="MIR1302-2HG",
            gene_id_format=GeneIdFormat.ENSEMBL_HUMAN,
            organism_ontology_term_id="NCBITaxon:9606",
            ensembl_version="Ensembl_110",
        )
    )
    return ds


# ------------------------------------------------------------------ #
# PublicDataset / DatasetCatalogue tests                              #
# ------------------------------------------------------------------ #


class TestPublicDataset:
    def test_pbmc3k_has_expected_obs_columns(self):
        assert "cell_type" in PBMC3K.obs_column_names()
        assert "n_genes" in PBMC3K.obs_column_names()
        assert "percent_mito" in PBMC3K.obs_column_names()

    def test_tabula_muris_has_cell_ontology_id(self):
        assert "cell_ontology_id" in TABULA_MURIS.obs_column_names()

    def test_cellxgene_lung_enforces_ontology_fields(self):
        names = CELLXGENE_LUNG.obs_column_names()
        assert "cell_type_ontology_term_id" in names
        assert "tissue_ontology_term_id" in names
        assert "disease_ontology_term_id" in names
        assert "organism_ontology_term_id" in names

    def test_gene_id_formats_differ(self):
        assert PBMC3K.gene_id_format == "ensembl_id"
        assert TABULA_MURIS.gene_id_format == "gene_symbol"
        assert CELLXGENE_LUNG.gene_id_format == "ensembl_id"

    def test_obs_encoding_map(self):
        enc = PBMC3K.obs_encoding_map()
        assert enc["cell_type"] == "free_text"
        assert enc["percent_mito"] == "float_percentage"

    def test_var_column_names(self):
        assert "gene_ids" in PBMC3K.var_column_names()
        assert "feature_id" in CELLXGENE_LUNG.var_column_names()

    def test_notes_present(self):
        assert len(PBMC3K.notes) > 0
        assert len(TABULA_MURIS.notes) > 0
        assert len(CELLXGENE_LUNG.notes) > 0


class TestDatasetCatalogue:
    def test_default_catalogue_contains_three_datasets(self):
        assert len(DEFAULT_CATALOGUE.datasets) == 3

    def test_get_returns_correct_dataset(self):
        ds = DEFAULT_CATALOGUE.get("pbmc3k")
        assert ds is not None
        assert ds.dataset_id == "pbmc3k"

    def test_get_unknown_returns_none(self):
        assert DEFAULT_CATALOGUE.get("does_not_exist") is None

    def test_dataset_ids(self):
        ids = DEFAULT_CATALOGUE.dataset_ids()
        assert "pbmc3k" in ids
        assert "tabula_muris" in ids
        assert "cellxgene_lung" in ids

    def test_gene_id_formats(self):
        formats = DEFAULT_CATALOGUE.gene_id_formats()
        assert formats["tabula_muris"] == "gene_symbol"
        assert formats["cellxgene_lung"] == "ensembl_id"

    def test_organism_encodings_differ(self):
        enc = DEFAULT_CATALOGUE.organism_encodings()
        # All three use different strings — that's the whole point
        assert len(set(enc.values())) == 3

    def test_obs_column_union(self):
        union = DEFAULT_CATALOGUE.obs_column_union()
        # 'cell_type' exists in PBMC 3k and CELLxGENE Lung
        assert "pbmc3k" in union["cell_type"]
        assert "cellxgene_lung" in union["cell_type"]
        # 'cell_ontology_id' only in Tabula Muris
        assert union["cell_ontology_id"] == ["tabula_muris"]

    def test_custom_catalogue_add(self):
        cat = DatasetCatalogue()
        cat.add(PBMC3K)
        assert len(cat.datasets) == 1
        assert cat.get("pbmc3k") is not None


# ------------------------------------------------------------------ #
# PreprocessingStep / PreprocessingPipeline tests                     #
# ------------------------------------------------------------------ #


class TestPreprocessingStep:
    def test_round_trip(self):
        step = PreprocessingStep(
            name="Quality filter",
            category=StepCategory.QUALITY_FILTER,
            tool="Scanpy",
            tool_version="1.9.3",
            parameters={"min_genes": 200, "max_pct_mito": 5.0},
        )
        restored = PreprocessingStep.from_dict(step.to_dict())
        assert restored.name == step.name
        assert restored.category == StepCategory.QUALITY_FILTER
        assert restored.parameters["min_genes"] == 200

    def test_step_category_values(self):
        assert StepCategory.ALIGNMENT.value == "alignment"
        assert StepCategory.NORMALISATION.value == "normalisation"
        assert StepCategory.BATCH_INTEGRATION.value == "batch_integration"


class TestPreprocessingPipeline:
    def test_pbmc3k_pipeline_has_alignment_step(self):
        steps = PBMC3K_PIPELINE.steps_by_category(StepCategory.ALIGNMENT)
        assert len(steps) == 1
        assert "Cell Ranger" in steps[0].tool

    def test_cellxgene_pipeline_has_doublet_detection(self):
        steps = CELLXGENE_LUNG_PIPELINE.steps_by_category(StepCategory.DOUBLET_DETECTION)
        assert len(steps) == 1
        assert steps[0].tool == "scrublet"

    def test_cellxgene_pipeline_has_batch_integration(self):
        steps = CELLXGENE_LUNG_PIPELINE.steps_by_category(StepCategory.BATCH_INTEGRATION)
        assert len(steps) == 1
        assert "scVI" in steps[0].tool

    def test_pbmc3k_pipeline_uses_louvain(self):
        steps = PBMC3K_PIPELINE.steps_by_category(StepCategory.CLUSTERING)
        assert steps[0].parameters["algorithm"] == "louvain"

    def test_cellxgene_pipeline_uses_leiden(self):
        steps = CELLXGENE_LUNG_PIPELINE.steps_by_category(StepCategory.CLUSTERING)
        assert steps[0].parameters["algorithm"] == "leiden"

    def test_normalisation_methods_differ(self):
        pbmc_norm = PBMC3K_PIPELINE.steps_by_category(StepCategory.NORMALISATION)
        lung_norm = CELLXGENE_LUNG_PIPELINE.steps_by_category(StepCategory.NORMALISATION)
        assert pbmc_norm[0].tool != lung_norm[0].tool

    def test_summary_returns_list_of_strings(self):
        summary = PBMC3K_PIPELINE.summary()
        assert isinstance(summary, list)
        assert all(isinstance(s, str) for s in summary)
        assert len(summary) == len(PBMC3K_PIPELINE.steps)

    def test_add_step(self):
        pipeline = PreprocessingPipeline(dataset_id="test")
        step = PreprocessingStep(
            name="test step",
            category=StepCategory.SCALING,
            tool="custom",
            tool_version="0.1",
        )
        pipeline.add_step(step)
        assert len(pipeline.steps) == 1


# ------------------------------------------------------------------ #
# MetadataInconsistency / InconsistencyDetector tests                 #
# ------------------------------------------------------------------ #


class TestInconsistencyDetector:
    @pytest.fixture
    def detector(self) -> InconsistencyDetector:
        return InconsistencyDetector()

    def test_detect_returns_inconsistencies(self, detector):
        result = detector.detect()
        assert len(result) > 0

    def test_gene_id_inconsistency_present(self, detector):
        gene_id_issues = detector.detect_by_category(InconsistencyCategory.GENE_ID_FORMAT)
        assert len(gene_id_issues) == 1
        issue = gene_id_issues[0]
        assert "tabula_muris" in issue.affected_datasets
        assert "pbmc3k" in issue.affected_datasets

    def test_organism_encoding_inconsistency_present(self, detector):
        issues = detector.detect_by_category(InconsistencyCategory.ORGANISM_ENCODING)
        assert len(issues) == 1
        # Should document all three different encodings
        field_encodings = {f.encoding for f in issues[0].affected_fields}
        assert len(field_encodings) == 3

    def test_cell_type_inconsistency_present(self, detector):
        issues = detector.detect_by_category(InconsistencyCategory.CELL_TYPE_ENCODING)
        assert len(issues) == 1
        # PBMC 3k uses free_text; CELLxGENE uses CL ontology
        encodings = {f.encoding for f in issues[0].affected_fields}
        assert "free_text" in encodings
        assert "CL_ontology_id" in encodings

    def test_normalisation_inconsistency_present(self, detector):
        issues = detector.detect_by_category(InconsistencyCategory.NORMALISATION_METHOD)
        assert len(issues) == 1

    def test_missing_field_inconsistency_present(self, detector):
        issues = detector.detect_by_category(InconsistencyCategory.MISSING_FIELD)
        assert len(issues) >= 1

    def test_all_inconsistencies_have_recommendation(self, detector):
        for inc in detector.detect():
            assert inc.recommendation, "Every inconsistency must have a recommendation"

    def test_all_inconsistencies_have_impact(self, detector):
        for inc in detector.detect():
            assert inc.impact, "Every inconsistency must document its impact"

    def test_summary_report_is_string(self, detector):
        report = detector.summary_report()
        assert isinstance(report, str)
        assert "Inconsistency" in report

    def test_to_dict_serialisable(self, detector):
        for inc in detector.detect():
            d = inc.to_dict()
            assert "category" in d
            assert "affected_datasets" in d
            assert "affected_fields" in d
            assert "recommendation" in d

    def test_custom_catalogue_filters_datasets(self):
        # A catalogue with only one dataset should still surface relevant issues
        cat = DatasetCatalogue(datasets=[PBMC3K])
        detector = InconsistencyDetector(catalogue=cat)
        result = detector.detect()
        # All known inconsistencies affect pbmc3k so all should still appear
        assert len(result) > 0


# ------------------------------------------------------------------ #
# UnifiedCell / UnifiedGene / UnifiedDataset tests                   #
# ------------------------------------------------------------------ #


class TestUnifiedCell:
    def test_round_trip(self):
        cell = make_valid_cell()
        restored = UnifiedCell.from_dict(cell.to_dict())
        assert restored.cell_id == cell.cell_id
        assert restored.sex == Sex.FEMALE
        assert restored.suspension_type == SuspensionType.CELL
        assert restored.organism_ontology_term_id == "NCBITaxon:9606"

    def test_to_dict_contains_all_required_fields(self):
        cell = make_valid_cell()
        d = cell.to_dict()
        required = {
            "cell_id", "dataset_id", "donor_id", "sample_id",
            "organism_ontology_term_id", "tissue_ontology_term_id",
            "cell_type_ontology_term_id", "disease_ontology_term_id",
            "assay_ontology_term_id", "sex", "suspension_type",
            "n_counts", "n_genes", "pct_counts_mito",
            "batch_id", "preprocessing_pipeline_id",
        }
        assert required.issubset(d.keys())

    def test_sex_encodes_as_pato_curie(self):
        cell = make_valid_cell()
        assert cell.to_dict()["sex"].startswith("PATO:")


class TestUnifiedGene:
    def test_round_trip(self):
        gene = UnifiedGene(
            feature_id="ENSG00000243485",
            feature_name="MIR1302-2HG",
            gene_id_format=GeneIdFormat.ENSEMBL_HUMAN,
            organism_ontology_term_id="NCBITaxon:9606",
            ensembl_version="Ensembl_110",
            is_highly_variable=True,
        )
        restored = UnifiedGene.from_dict(gene.to_dict())
        assert restored.feature_id == "ENSG00000243485"
        assert restored.gene_id_format == GeneIdFormat.ENSEMBL_HUMAN
        assert restored.is_highly_variable is True


class TestUnifiedDataset:
    def test_add_cell_increments_count(self):
        ds = make_valid_dataset()
        initial = ds.n_cells()
        ds.add_cell(make_valid_cell("CELL_002"))
        assert ds.n_cells() == initial + 1

    def test_add_gene_increments_count(self):
        ds = make_valid_dataset()
        initial = ds.n_genes()
        ds.add_gene(
            UnifiedGene(
                feature_id="ENSG00000223972",
                feature_name="DDX11L1",
                gene_id_format=GeneIdFormat.ENSEMBL_HUMAN,
                organism_ontology_term_id="NCBITaxon:9606",
                ensembl_version="Ensembl_110",
            )
        )
        assert ds.n_genes() == initial + 1

    def test_layer_names(self):
        ds = make_valid_dataset()
        assert "counts" in ds.layer_names()

    def test_to_dict_structure(self):
        ds = make_valid_dataset()
        d = ds.to_dict()
        assert "dataset_id" in d
        assert "layers" in d
        assert "cells" in d
        assert "genes" in d


# ------------------------------------------------------------------ #
# DataLayer tests                                                     #
# ------------------------------------------------------------------ #


class TestDataLayer:
    def test_round_trip(self):
        layer = DataLayer(
            name="log1p_cp10k",
            normalisation=NormalisationStrategy.LOG1P_CP10K,
            ensembl_version="Ensembl_110",
            genome_assembly="GRCh38",
        )
        restored = DataLayer.from_dict(layer.to_dict())
        assert restored.name == "log1p_cp10k"
        assert restored.normalisation == NormalisationStrategy.LOG1P_CP10K


# ------------------------------------------------------------------ #
# SchemaValidator tests                                               #
# ------------------------------------------------------------------ #


class TestSchemaValidator:
    @pytest.fixture
    def validator(self) -> SchemaValidator:
        return SchemaValidator()

    def test_valid_cell_passes(self, validator):
        assert validator.is_valid_cell(make_valid_cell())

    def test_invalid_organism_curie_fails(self, validator):
        cell = make_valid_cell()
        cell.organism_ontology_term_id = "Homo sapiens"   # wrong format
        errors = validator.validate_cell(cell)
        assert any(e.field == "organism_ontology_term_id" for e in errors)

    def test_invalid_tissue_curie_fails(self, validator):
        cell = make_valid_cell()
        cell.tissue_ontology_term_id = "liver"            # free-text, not UBERON
        errors = validator.validate_cell(cell)
        assert any(e.field == "tissue_ontology_term_id" for e in errors)

    def test_invalid_cell_type_curie_fails(self, validator):
        cell = make_valid_cell()
        cell.cell_type_ontology_term_id = "T cell"        # free-text, not CL
        errors = validator.validate_cell(cell)
        assert any(e.field == "cell_type_ontology_term_id" for e in errors)

    def test_invalid_disease_curie_fails(self, validator):
        cell = make_valid_cell()
        cell.disease_ontology_term_id = "healthy"         # free-text
        errors = validator.validate_cell(cell)
        assert any(e.field == "disease_ontology_term_id" for e in errors)

    def test_invalid_assay_curie_fails(self, validator):
        cell = make_valid_cell()
        cell.assay_ontology_term_id = "10x v3"            # free-text
        errors = validator.validate_cell(cell)
        assert any(e.field == "assay_ontology_term_id" for e in errors)

    def test_negative_n_counts_fails(self, validator):
        cell = make_valid_cell()
        cell.n_counts = -1
        errors = validator.validate_cell(cell)
        assert any(e.field == "n_counts" for e in errors)

    def test_pct_mito_out_of_range_fails(self, validator):
        cell = make_valid_cell()
        cell.pct_counts_mito = 105.0
        errors = validator.validate_cell(cell)
        assert any(e.field == "pct_counts_mito" for e in errors)

    def test_doublet_score_out_of_range_fails(self, validator):
        cell = make_valid_cell()
        cell.doublet_score = 1.5
        errors = validator.validate_cell(cell)
        assert any(e.field == "doublet_score" for e in errors)

    def test_none_doublet_score_is_valid(self, validator):
        cell = make_valid_cell()
        cell.doublet_score = None
        assert validator.is_valid_cell(cell)

    def test_valid_dataset_passes(self, validator):
        ds = make_valid_dataset()
        assert validator.is_valid_dataset(ds)

    def test_dataset_missing_raw_layer_fails(self, validator):
        ds = make_valid_dataset()
        ds.layers = [
            DataLayer(
                name="log1p_cp10k",
                normalisation=NormalisationStrategy.LOG1P_CP10K,
                ensembl_version="Ensembl_110",
                genome_assembly="GRCh38",
            )
        ]
        errors = validator.validate_dataset(ds)
        assert any(e.field == "layers" for e in errors)

    def test_multiple_errors_reported(self, validator):
        cell = make_valid_cell()
        cell.organism_ontology_term_id = "human"
        cell.tissue_ontology_term_id = "liver"
        errors = validator.validate_cell(cell)
        assert len(errors) >= 2

    def test_validation_error_str_includes_cell_id(self, validator):
        cell = make_valid_cell("TEST_CELL")
        cell.n_counts = -5
        errors = validator.validate_cell(cell)
        assert any("TEST_CELL" in str(e) for e in errors)
