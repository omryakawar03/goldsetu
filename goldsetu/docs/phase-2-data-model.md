# GOLDSETU Phase 2 — MongoDB data model

## Decision update

The persistence choice is now MongoDB Atlas, as requested. The FastAPI service uses PyMongo's asynchronous API (`AsyncMongoClient`); Motor is not selected because MongoDB has announced its deprecation timeline. MongoDB documents are modeled with Pydantic. Money is stored as integer paise, while weights and metal rates use Decimal128 semantics, never binary float.

MongoDB Atlas Free is the development/demo target. It is not the production financial-data target: official limits currently include 512 MB storage (indexes count), throughput limits of 100 operations/second, no Atlas-managed backups, no private endpoints, and auto-pause after 30 days with no connections. Before real shop/loan data, move to an appropriate paid tier and prove backup/restore and operational monitoring. Atlas transaction support must still be exercised against the selected cluster and exact workflows.

## Mongo document model

The collection catalogue and index strategy live in `apps/api/app/db/indexes.py`. Every tenant-owned document has `shop_id`, relevant records include `branch_id`, and every repository query must apply the authenticated scope. Unique indexes include tenant/branch in their key so one shop's SKU, invoice number, or barcode cannot block another shop's value. Immutable financial/audit collections use insert/reversal patterns rather than delete/update flows.

Cross-document atomic operations (invoice posting with inventory and ledger changes, payment reconciliation, pledge repayment) must use MongoDB transactions and retry only on transient transaction labels. If any target deployment cannot meet this transaction requirement, those commands stay disabled; do not silently fall back to partial writes. Unique-item sale protection also has a unique item-state transition guarded by item ID and expected version.

## Phase 2 artifacts

- `app/domain/models.py`: validated document/domain shapes and enums.
- `app/domain/money.py`: paise-safe and Decimal-only arithmetic.
- `app/db/indexes.py`: collection catalogue and required unique/query indexes.
- `app/db/migrations.py`: versioned, idempotent index/schema migration runner.
- `tests/`: synthetic validation and calculation tests.

## Migration policy

Migrations are append-only and carry a monotonically increasing version. Run them as a single deployment job, not from every API worker. Index creation is idempotent. Destructive field removal is never an in-place migration while old app/API versions may still write it; use expand/backfill/verify/contract. Financial history is never rewritten to fit a new schema without an audited correction.

## Current limitation

Phase 2 defines the schema foundation and deterministic primitives. A live Atlas connection and migration run were not exercised in this checkpoint; no customer data or production workflows are created. The one-shot migration CLI is implemented, and Atlas credentials/project access must be configured by the operator in a local environment file. No credentials belong in the repository or Android app.


