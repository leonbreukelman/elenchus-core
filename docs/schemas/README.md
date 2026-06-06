# Project Model v1 Schema Snapshot

This directory contains a version-pinned local snapshot of Build Arena's authoritative Project Model v1 JSON Schema for Elenchus Core fixture validation and schema-drift detection.

- Source repository: `/home/leonb/projects/build-arena`
- Source path: `docs/schemas/project-model-v1.schema.json`
- Copied into Elenchus Core: `docs/schemas/project-model-v1.schema.json`
- Source date from Build Arena contract spec: 2026-06-05
- Snapshot sha256: `6d82e8635839bbc110014c844c842ba03913a7be0c0aea411d25a147a30aa38b`

Build Arena remains the owner of the `project-model/v1` contract. Elenchus Core does not redefine the contract; it validates tests against this snapshot and consumes only the advisory surfaces required by issue #5.

To refresh after a Build Arena contract change:

1. Copy the authoritative schema from Build Arena:
   `cp /home/leonb/projects/build-arena/docs/schemas/project-model-v1.schema.json docs/schemas/project-model-v1.schema.json`
2. Recompute sha256:
   `sha256sum docs/schemas/project-model-v1.schema.json`
3. Update the hash in this note.
4. Run `uv run pytest tests/test_project_model_v1.py -q` and then the full repo gates.
