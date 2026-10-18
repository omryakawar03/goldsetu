# Phase 2 acceptance

## Implemented

- [x] MongoDB Atlas replaces the PostgreSQL decision; PyMongo Async is the selected API driver.
- [x] Tenant-aware collections/index definitions cover shops, branches, users/memberships, customers, products, jewellery items, suppliers, stock movements, rates, invoices, payments, journal entries, pledge accounts, audit events, and sync operations.
- [x] Unique constraints cover tenant-specific SKU/item/invoice/idempotency identifiers; partial unique indexes cover optional barcode/provider reference values.
- [x] Atlas `.env.example`, async connection factory, versioned migration registry, and explicit one-shot CLI are present; migrations are never run during API worker startup.
- [x] Pydantic models validate invoice totals, payment verification state, weight consistency, balanced journal entries, and bounded pledge principal.
- [x] Money helpers store rupees as integer paise and calculate weight × paise-per-gram with Decimal only.
- [x] Atlas Free limits and the development-only production boundary are included in the user guide.
- [x] Hinglish brochure and end-to-end guide are prepared.

## Test results

- [x] 15 standard-library unittest cases passed on Python 3.12.14 with Pydantic 2.13.5; this includes the Phase 3 credential and permission unit checks.
- [x] All 18 Python API/test files pass a Python AST syntax parse.
- [ ] MongoDB driver/index creation test: not run because PyMongo is not installed in the available runtime and package installation could not write its temporary wheel directory.
- [ ] Live Atlas migration, backup/restore, and transaction test: not run because no Atlas credentials/cluster are configured.

Command run from `apps/api`:

```text
python -m unittest discover -s tests -v
Ran 15 tests ... OK
```

## Limitations and risks

- Atlas Free is limited to synthetic development/demo data; it lacks managed backups and has constrained storage/throughput.
- MongoDB has no relational foreign keys. Services and reconciliation checks must enforce reference integrity and tenant isolation.
- Route/API integration and cross-document transaction behavior are not verified against MongoDB.
- GST/lending/payment workflows remain production gates requiring qualified review and configured providers.
- Documentation and brochure describe planned product capabilities; they are not proof the corresponding app screens or services exist.

## Exit checkpoint

- [x] Phase 2 schema/domain foundation is ready for review.
- [x] User authorized work through all remaining phases; Phase 3 implementation has begun.

