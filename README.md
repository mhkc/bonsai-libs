# bonsai-api-client

Shared API client library for Bonsai services (audit log, notification, etc.).

Purpose:
- Provide a single, versioned API client that can be consumed by PRP, Bonsai API, and worker services.
- Allow independent releases, CI, and tests.

Quick start

Install from a package repository (example):

```bash
pip install bonsai-api-client
```

Or use a git dependency in `pyproject.toml`:

```toml
[project]
dependencies = [
  "bonsai-api-client @ git+https://github.com/yourorg/bonsai-libs.git@v0.1.0",
]
```

Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
```

Schemas

This repository also contains a `bonsai_schemas` package with canonical
Pydantic models that can be imported by the API and clients to keep DTOs
in sync. See `bonsai_schemas` for initial audit and notification models.
# bonsai-libs

Shared Python libraries for the **Bonsai** ecosystem.

This package centralizes reusable components used across:
- **Bonsai** (core services and microservices)
- **PRP** (Pipeline Result Processor)
- CLI tools and data ingestion utilities

> One place for shared models, a API client and other assets.

## Install

```bash
pip install bonsai-libs
