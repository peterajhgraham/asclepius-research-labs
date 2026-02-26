"""
Asclepius CLI.

Usage
-----
    asclepius ingest-scrna \\
        --counts matrix.csv \\
        --metadata metadata.json \\
        --experiment-id <UUID> \\
        --pipeline-hash <git-hash>

    asclepius list-experiments
    asclepius lineage --dataset-id <UUID>
"""

from __future__ import annotations

import json
import uuid as _uuid
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="asclepius",
    help="Asclepius Research Labs – biological data registry CLI.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Required metadata fields for the ingest-scrna command
# ---------------------------------------------------------------------------

_SCRNA_REQUIRED_FIELDS = ["cell_type", "condition", "replicate", "batch_id"]


def _validate_scrna_metadata(metadata_dict: dict) -> None:
    missing = [f for f in _SCRNA_REQUIRED_FIELDS if f not in metadata_dict]
    if missing:
        raise ValueError(f"Missing required metadata fields: {missing}")


def _make_session(db_url: Optional[str]):
    """Create a SQLAlchemy session for *db_url* (or DATABASE_URL env var)."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from asclepius.database import Base
    import asclepius.db_models  # noqa: F401 – registers models

    url = db_url or os.getenv("DATABASE_URL", "sqlite:///./asclepius.db")
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("ingest-scrna")
def ingest_scrna(
    counts: str = typer.Option(..., help="Path to expression count matrix CSV."),
    metadata: str = typer.Option(..., help="Path to sample metadata JSON file."),
    experiment_id: str = typer.Option(..., help="UUID of the target experiment."),
    pipeline_hash: str = typer.Option(..., help="Git commit hash of the pipeline."),
    pipeline_name: str = typer.Option("default-pipeline", help="Name of the pipeline."),
    parent_dataset_id: Optional[str] = typer.Option(
        None, help="UUID of the parent dataset for versioning (optional)."
    ),
    notes: str = typer.Option("", help="Human-readable notes for this dataset version."),
    db_url: Optional[str] = typer.Option(
        None,
        envvar="DATABASE_URL",
        help="Database URL (defaults to DATABASE_URL env var).",
    ),
) -> None:
    """
    Ingest a scRNA-seq dataset and register a versioned dataset entry.

    Steps:
      1. Validate the metadata JSON.
      2. Validate the counts CSV exists.
      3. Register or retrieve the pipeline.
      4. Create a versioned Dataset record linked to the experiment.
      5. Register the expression file against the sample.
    """
    from asclepius.db_models import Dataset, Experiment, File, Pipeline, Sample

    # 1. Validate metadata
    meta_path = Path(metadata)
    if not meta_path.exists():
        typer.echo(f"ERROR: metadata file not found: {meta_path}", err=True)
        raise typer.Exit(1)

    with meta_path.open() as fh:
        meta = json.load(fh)

    try:
        _validate_scrna_metadata(meta)
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(1)

    # 2. Validate counts CSV
    counts_path = Path(counts)
    if not counts_path.exists():
        typer.echo(f"ERROR: counts file not found: {counts_path}", err=True)
        raise typer.Exit(1)

    session = _make_session(db_url)
    try:
        # 3. Verify experiment exists
        exp_uuid = _uuid.UUID(experiment_id)
        experiment = session.get(Experiment, exp_uuid)
        if experiment is None:
            typer.echo(f"ERROR: experiment {experiment_id!r} not found.", err=True)
            raise typer.Exit(1)

        # 4. Get or create pipeline
        pipeline = (
            session.query(Pipeline)
            .filter(Pipeline.git_commit_hash == pipeline_hash)
            .first()
        )
        if pipeline is None:
            pipeline = Pipeline(
                name=pipeline_name,
                git_commit_hash=pipeline_hash,
                parameters={},
            )
            session.add(pipeline)
            session.flush()

        # 5. Create sample from metadata
        sample = Sample(
            experiment_id=exp_uuid,
            cell_type=meta.get("cell_type"),
            condition=meta.get("condition"),
            replicate=meta.get("replicate"),
            batch_id=meta.get("batch_id"),
            metadata_=meta,
        )
        session.add(sample)
        session.flush()

        # 6. Register the expression file
        file_rec = File(
            sample_id=sample.id,
            file_type="expression_csv",
            file_path=str(counts_path.resolve()),
            checksum=_sha256(counts_path),
            pipeline_version=pipeline_hash,
        )
        session.add(file_rec)
        session.flush()

        # 7. Create versioned dataset
        parent_uuid = _uuid.UUID(parent_dataset_id) if parent_dataset_id else None
        dataset = Dataset(
            experiment_id=exp_uuid,
            pipeline_id=pipeline.id,
            parent_dataset_id=parent_uuid,
            notes=notes,
        )
        session.add(dataset)
        session.commit()

        typer.echo(f"✓  Dataset registered: {dataset.id}")
        typer.echo(f"   Experiment : {experiment_id}")
        typer.echo(f"   Pipeline   : {pipeline_hash}")
        typer.echo(f"   Sample     : {sample.id}")
        if parent_dataset_id:
            typer.echo(f"   Parent     : {parent_dataset_id}")

    finally:
        session.close()


@app.command("list-experiments")
def list_experiments(
    db_url: Optional[str] = typer.Option(
        None, envvar="DATABASE_URL", help="Database URL."
    ),
) -> None:
    """List all experiments in the registry."""
    from asclepius.db_models import Experiment

    session = _make_session(db_url)
    try:
        experiments = session.query(Experiment).all()
        if not experiments:
            typer.echo("No experiments registered yet.")
            return
        for exp in experiments:
            typer.echo(
                f"{exp.id}  {exp.name:<30}  organism={exp.organism}  assay={exp.assay_type}"
            )
    finally:
        session.close()


@app.command("lineage")
def lineage(
    dataset_id: str = typer.Option(..., help="UUID of the dataset."),
    db_url: Optional[str] = typer.Option(
        None, envvar="DATABASE_URL", help="Database URL."
    ),
) -> None:
    """Print the version lineage chain for a dataset."""
    from asclepius.query import get_lineage

    session = _make_session(db_url)
    try:
        chain = get_lineage(session, _uuid.UUID(dataset_id))
        if not chain:
            typer.echo(f"Dataset {dataset_id!r} not found.")
            return
        typer.echo(f"Lineage for {dataset_id} ({len(chain)} version(s)):")
        for i, ds_id in enumerate(chain):
            prefix = "└─" if i == len(chain) - 1 else "├─"
            typer.echo(f"  {prefix} {ds_id}")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    app()
