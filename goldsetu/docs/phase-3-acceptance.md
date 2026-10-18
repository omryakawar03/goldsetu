# Phase 3 — Identity and tenancy status

## Implemented in this checkpoint

- Password hashing with per-password random salts using scrypt; opaque random session tokens are stored as SHA-256 digests.
- Login throttling records keyed by normalized email and client IP, expiring automatically.
- Shop owner registration creates the user, shop, first branch, owner membership, session, and audit event in a MongoDB transaction.
- Login, session identity checks, single/all-session logout, and `/auth/me` permissions.
- Role/permission map with default deny for unknown role values.
- Branch listing/creation, staff invitations with one-time token digest and expiry, invitation acceptance, product catalogue endpoints, rates, customer creation, stock adjustments, invoice drafts, cash/pending payment records, and pledge opening record.
- Versioned index migrations are run with `goldsetu-migrate`, not automatically by API workers.
- Pledge-record endpoint is disabled by default with `GOLDSETU_ENABLE_PLEDGE_RECORDS=false`.

## Verification

- `python -m unittest discover -s tests -v`: 15 tests passed using synthetic data.
- Python AST syntax parse: all 18 API/test Python files parsed.
- The API's FastAPI and MongoDB dependencies were not installed in the available test runtime, so route imports, HTTP behavior, Atlas connectivity, transactions, and live indexes have not been verified.

## Limitations before this phase can be accepted as production-ready

- Add integration tests against a disposable replica-set MongoDB deployment, covering tenant/branch isolation, duplicate requests, invite races, session revocation, index migrations, transaction rollback, and concurrent stock/payment changes.
- Add registered customer authentication and verified shop-customer linkage; customer endpoints do not exist.
- Add account recovery, verified email/phone workflows, stronger abuse controls, session/device management, and operational monitoring.
- Ensure all role-to-route grants receive direct tests; review privilege separation and audit atomicity.

This phase is an implementation checkpoint, not a production security certification.
