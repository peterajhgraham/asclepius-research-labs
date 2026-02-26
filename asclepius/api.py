"""
FastAPI application for the Asclepius biological data registry.

Endpoints (v0)
--------------
GET  /health
GET  /experiments
POST /experiments
GET  /experiments/{experiment_id}
GET  /experiments/{experiment_id}/samples
GET  /experiments/{experiment_id}/datasets
POST /datasets/{dataset_id}/lineage
GET  /samples?cell_type=&condition=&assay_type=&organism=
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from asclepius.database import get_db, init_db
from asclepius.db_models import Dataset, Experiment, Sample
from asclepius.query import get_lineage, query_samples


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Asclepius Research Labs",
    description="Versioned biological dataset registry – v0 API",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    organism: Optional[str] = None
    assay_type: Optional[str] = None


class ExperimentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    organism: Optional[str]
    assay_type: Optional[str]
    created_at: Optional[datetime]


class SampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    cell_type: Optional[str]
    condition: Optional[str]
    replicate: Optional[str]
    batch_id: Optional[str]


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    experiment_id: uuid.UUID
    pipeline_id: uuid.UUID
    parent_dataset_id: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: Optional[datetime]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}


@app.get("/experiments", response_model=list[ExperimentRead], tags=["experiments"])
def list_experiments(db: Session = Depends(get_db)):
    return db.query(Experiment).all()


@app.post("/experiments", response_model=ExperimentRead, status_code=201, tags=["experiments"])
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    exp = Experiment(**payload.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@app.get("/experiments/{experiment_id}", response_model=ExperimentRead, tags=["experiments"])
def get_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@app.get(
    "/experiments/{experiment_id}/samples",
    response_model=list[SampleRead],
    tags=["samples"],
)
def get_experiment_samples(experiment_id: uuid.UUID, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp.samples


@app.get(
    "/experiments/{experiment_id}/datasets",
    response_model=list[DatasetRead],
    tags=["datasets"],
)
def get_experiment_datasets(experiment_id: uuid.UUID, db: Session = Depends(get_db)):
    exp = db.get(Experiment, experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp.datasets


@app.get("/datasets/{dataset_id}/lineage", tags=["datasets"])
def dataset_lineage(dataset_id: uuid.UUID, db: Session = Depends(get_db)):
    chain = get_lineage(db, dataset_id)
    if not chain:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"dataset_id": str(dataset_id), "lineage": [str(d) for d in chain]}


@app.get("/samples", response_model=list[SampleRead], tags=["samples"])
def search_samples(
    cell_type: Optional[str] = None,
    condition: Optional[str] = None,
    assay_type: Optional[str] = None,
    organism: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return query_samples(
        db,
        cell_type=cell_type,
        condition=condition,
        assay_type=assay_type,
        organism=organism,
    )
