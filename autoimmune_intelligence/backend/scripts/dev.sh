#!/bin/bash
venv/bin/uvicorn app.main:app --port 8000 --reload --reload-dir app
