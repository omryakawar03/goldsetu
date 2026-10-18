# GOLDSETU implementation plan

Phases run in the user-specified order. The user approved work across all phases, so implementation proceeds without intermediate approval stops. A phase is marked complete only when its exit evidence exists and relevant checks pass.

| Phase | Scope | Exit evidence |
|---|---|---|
| 1. Requirements and architecture | Architecture, project structure, dependencies, acceptance criteria | Planning docs and starter structure reviewed; approval to proceed |
| 2. Data/domain foundation | MongoDB document contracts, tenant-aware indexes, versioned migrations, domain entities, decimal/weight rules, SQLite schema foundation | Migration upgrade checks and critical domain tests |
| 3. Identity and tenancy | Shops, branches, users, sessions, roles/permissions, audit, authorization | Auth, RBAC, tenant isolation, and audit tests |
| 4. Rates and inventory | Rate history, catalogue, stock movements, barcodes, purchase/adjustment flows | Pricing, scan, unique-item, and stock tests |
| 5. POS and payments | Drafts, invoices, numbering policy, tax snapshots, receipts, printer/PDF/share adapters, returns | Invoice/stock atomicity, idempotency, payment status and print verification |
| 6. Pledges and customer accounts | Pledge items/custody, appraisal, disbursements, interest, repayment, statements | Interest/repayment/closure/custody tests and compliance gate review |
| 7. Accounting and reports | Configurable tax, chart of accounts, journal, ledgers, financial/tax reports, exports | Balanced-entry and reconciled report tests |
| 8. Customer app | Auth/linkage, catalogue, own invoices/balances/pledges, payments entry points, loyalty/service | Customer privacy, record ownership, and UX tests |
| 9. AI and automation | Permission-aware query assistant, provider adapters, notifications/jobs | Grounding, permission, privacy, idempotent delivery checks |
| 10. Offline sync and recovery | Durable outbox, retries, cursors, conflicts, backup/restore | Duplicate operation, conflict, restore, and integrity tests |
| 11. Security, QA, performance | Threat review, security tests, load/performance work, dependency scanning | Critical test suite, scan results, remediation list |
| 12. Android and release docs | Native permissions/plugins, independent APK builds/signing, installation/release docs | Both APK builds and device/printer verification with actual results |
| 13. Hinglish and sales materials | Hinglish guides and product brochure with placeholders | Content review; no invented claims |

## Current implementation snapshot (2026-10-14)

- Phase 1: architecture and acceptance documentation prepared.
- Phase 2: MongoDB document/index foundation and Decimal-safe money helpers implemented; 15 synthetic domain/security tests pass. MongoDB integration is not yet exercised.
- Phase 3: auth, role checks, tenant membership, invitation and branch/catalogue/rate/customer/stock routes have an initial implementation. API-level tests, live Atlas checks, and concurrency/security verification remain open.
- Phase 4: manual rate history, product creation/listing, unique-item intake/barcode lookup, and transaction-safe stock adjustments with a quantity balance exist. Purchase/transfer/returns, labels, and API concurrency/integration checks remain open.
- Phase 5: invoice draft creation and cash/pending-payment record skeleton exist. Drafts are not final invoices: tax/pricing configuration, posting, returns/reversals, provider verification, receipts, and print/PDF remain open.
- Phase 6: pledge opening record only. Interest accrual, repayments, renewal, closure, custody verification/release, and compliance review remain open; do not use for lending.
- Phase 7–12: accounting/reporting, customer app, AI/notifications, offline SQLite synchronization, full security/QA, and Android APK delivery remain open.
- Phase 13: end-to-end guide and responsive Hinglish brochure with separate Business/Customer sample screen visuals are present; the visuals are synthetic mockups, not screenshots of a shipped app or evidence of implemented screens.

## Acceptance criteria for the eventual product

The final product is accepted only after evidence is available for all applicable items below:

1. Business and Customer APKs build and install separately with distinct app identities.
2. Authorized shop staff create and manage products; barcode scans resolve correct available items.
3. Billing performs decimal-safe pricing/tax calculations, uses unique-item safeguards, and updates stock transactionally.
4. Supported PDF/print flows are verified on named Android/printer configurations; unsupported printer combinations are documented.
5. Effective-dated tax configuration and review process are documented; tax behavior receives qualified guidance before production use.
6. Sales, returns, expenses, journal entries, and reports reconcile under documented formulas; posted history is corrected through reversals.
7. Pledge accounts preserve disclosed terms, principal, interest, charges, payment history, custody, and release authorization.
8. Customer authentication and server authorization restrict records to the verified customer and linked shop.
9. Online payment success is based on signed server-side provider confirmation/reconciliation; pending and failed states stay distinct.
10. Shared staff accounts, branch assignments, roles, revocation, and sensitive approvals work server-side.
11. Offline operations persist; duplicate sync retries do not duplicate financial/inventory effects; conflicts are surfaced.
12. Notifications are tested through configured providers, with delivery logs, consent/preferences, and retry behavior.
13. AI responses use authorized deterministic data and do not execute restricted writes.
14. Backup and restore are exercised and integrity is checked.
15. Critical business-rule, security, API, component, integration, and end-to-end tests pass with recorded output.
16. Setup, deployment, owner/customer guides, backup/recovery, security/compliance, release docs, and Hinglish brochure are complete.

## Production gates

- Qualified Indian tax guidance for applicable GST/HSN/SAC, exchange, return, discount, invoice, and tax reporting behavior.
- Qualified review of lending permissions, interest disclosure, customer verification, retention, and collateral custody/release before pledge lending is enabled.
- Merchant account and gateway verification before online collection is enabled.
- Privacy/data-sharing review and appropriate consent before sending data to external AI, OTP, push, or messaging providers.
- Device/printer matrix and Android QA before claiming generic print compatibility.


