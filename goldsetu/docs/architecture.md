# GOLDSETU architecture

## 1. Goals and boundaries

GOLDSETU is an Android-first, offline-capable jewellery management system for Indian shops, with two independent clients:

- **Business**: staff workflows for catalogue, stock, rates, POS, accounting, reports, and pledge custody.
- **Customer**: authenticated access to that customer's shop-linked invoices, receipts, balances, pledge statements, catalogue, and service requests.

The platform is a modular monolith at launch. The target is strong module and data boundaries without the deployment and consistency burden of early microservices.

## 2. System view

```text
┌──────────────────────────┐       ┌──────────────────────────┐
│ Business Android app     │       │ Customer Android app     │
│ Next.js + Capacitor      │       │ Next.js + Capacitor      │
│ SQLite + durable outbox  │       │ authenticated API/cache  │
└────────────┬─────────────┘       └─────────────┬────────────┘
             │ HTTPS REST / optional events       │ HTTPS REST
             └────────────────┬──────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │ FastAPI v1 modular monolith   │
              │ auth, tenancy, domain services│
              │ audit, sync, provider adapters│
              └──────────────┬────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │ MongoDB Atlas       │
                  │ canonical shared data│
                  └─────────────────────┘
```

External payment, OTP, push, AI, market-rate, maps, and printer services are optional adapters. Secrets stay on the server or in Android Keystore where device-local secrets are necessary. The mobile apps do not contain provider secret keys.

## 3. App and package boundaries

- `apps/business` and `apps/customer` are separate Next.js apps and separate Capacitor Android applications. They have independent app IDs, names, icons, release signing, permissions, navigation, and app-specific state.
- `packages/ui` contains accessible shared primitives, not business authorization.
- `packages/domain` contains deterministic money, weight, pricing, and state-transition rules that can run locally and on the server where practical. The API remains the authority for shared records.
- `packages/validation` contains request/form schemas; the backend independently validates all requests with Pydantic.
- `packages/api-client` owns typed REST calls, auth/session handling, error mapping, and sync protocol types.
- `packages/i18n` supplies English, Hindi, and Marathi strings, locale formatting, and translation completeness checks.

Redux Toolkit holds transient cross-screen state. SQLite/MongoDB Atlas remain the durable stores; Redux is not a source of truth.

## 4. Data ownership and tenant security

Every business record is scoped to a shop and, where relevant, a branch. Server queries derive authorized shop/branch scope from the authenticated identity, not from an untrusted client-supplied tenant ID. Compound tenant-aware unique indexes and service-level checks both enforce ownership; MongoDB has no relational foreign-key constraints, so references and lifecycle integrity require validated domain services and reconciliation checks. Customer records are only returned after the account is linked to a verified customer identity and the relevant shop.

Users, roles, permissions, sessions, branch memberships, audit events, and approval decisions are server-managed. Sensitive operations (rate changes, posted invoice reversals, refunds, loan balance corrections, collateral release, user/role changes) require explicit permission and record the actor, time, reason, and affected records.

## 5. Local persistence and migrations

The Business app uses a Capacitor SQLite plugin as the Android operational database. The initial cost-conscious candidate is `@capacitor-community/sqlite`; its maintainers document Android/native SQLite and database migration support. Capawesome documents a Drizzle adapter for its own SQLite plugin, but the plugin requires an Insiders license. Before lockfile adoption, compare lifecycle/support, licensing cost, encryption requirements, Android transaction behavior, and migration tooling. A single adapter boundary isolates plugin details. Repositories expose domain-oriented reads and transaction-scoped writes; services enforce business rules. SQL migrations are versioned, ordered, and tested on a fresh database and upgrade path. Local audit events and the durable sync outbox commit in the same SQLite transaction as the associated local change.

Drizzle ORM is conditional on verified compatibility with the selected Capacitor SQLite driver, transaction behavior, type mapping, and migrations. The Capawesome SQLite plugin documents a Drizzle adapter but requires a paid Insiders license; the community plugin is the initial free candidate and does not document a Drizzle adapter. If the selected driver/adapter is not acceptable or any native checks fail, repositories use parameterized SQL through the adapter. Confirm the plugin/license choice before Android SQLite implementation. Web preview storage is a development adapter only and is not treated as Android production storage.

The Customer app caches only data needed for an explicitly supported experience. Sensitive account content is not placed in broad, long-lived caches; logout clears customer-scoped cache and credentials according to the security design.

## 6. Sync and conflict rules

The business client maintains an outbox entry per operation with a globally unique operation ID, idempotency key, entity ID, base version, creation time, actor/device, and payload schema version. Retries use bounded exponential backoff with jitter. The server stores operation outcomes so retries return the original result rather than duplicating effects. Pull sync uses server cursors/versions and tombstones where appropriate.

| Data/operation | Offline behavior | Server behavior on sync |
|---|---|---|
| Catalogue/customer edits | Queue with base version | Apply if version matches; otherwise return field-level conflict for review |
| Rates | Read cached rate with source/time; authorized local change is visibly pending | Append history; conflicting effective-rate edits require authorized resolution |
| Inventory movement | Record local movement and mark pending | Validate current stock and item identity; conflict is surfaced for reconciliation |
| Invoice | Draft locally; if business policy permits a completed offline bill, retain immutable device operation ID and mark server sync pending | Deduplicate, validate item/version/numbering rules, return canonical status; collision requires explicit reconciliation |
| Payment | Record as locally observed/entered with pending verification unless independently reconciled | Provider callback/reconciliation or authorized receipt confirmation determines canonical success |
| Pledge/loan | Cached read is allowed by permission; new or balance-affecting operations remain pending and clearly labelled | Validate authorization, contract terms, and state transition; never silently overwrite a balance |
| Posted accounting | No edit/delete; queue permitted append-only transaction or reversal | Validate balanced entries and preserve audit trail |

Conflict screens show both versions, actor/time, and allowed resolution actions. Automatic last-write-wins is not used for money, inventory quantities, rates, invoices, payments, or pledge balances. A server response is required before displaying cross-device synchronization as complete.

## 7. Financial and jewellery domain rules

- Use integer paise for INR values when practical and Decimal-compatible arithmetic for rates, tax, and intermediate calculations. Define rounding by line, tax component, and document total before implementing billing.
- Keep gross, stone, and net metal weights separate with an explicit precision and unit. Never infer live metal rates; each rate records purity, unit, source, effective timestamp, actor, and history.
- Invoices snapshot item, rate, making charge, wastage, discount, tax configuration, and customer-facing totals. Posted financial documents are immutable; correction is represented by reversal/credit/debit workflows.
- Inventory is represented by append-only movements. Individually tracked pieces have unique IDs/barcodes and a constrained sale state. Quantity stock uses transactional quantity checks.
- Double-entry accounting commands must balance debits and credits atomically. Sales revenue, COGS, gross profit, operating expense, and net profit have explicit formulas and report definitions.
- Pledge custody and lending are separate domain workflows with appraisal, item custody location, authorization, disclosed terms, principal/interest/fees separation, repayment history, physical verification, and release approval. Enabling production lending is contingent on qualified legal/compliance review and jurisdiction/business eligibility.
- GST is configurable by effective date, jurisdiction, HSN/SAC, and transaction type. No tax rate or legal treatment is treated as universally valid; implementation requires qualified tax guidance.

## 8. API and authentication

REST routes are versioned under `/api/v1`; FastAPI publishes OpenAPI. Request and response schemas are explicit. Mutating financial endpoints accept an idempotency key and return operation/transaction IDs and canonical status. Authentication uses short-lived access credentials and revocable sessions/refresh credentials with server-side rotation policy, throttling, password hashing, and reset flows. OTP is an external provider adapter. WebSocket/event updates are an optimization; periodic cursor-based sync remains available.

The server validates permissions for every sensitive read and write. The mobile UI may hide unavailable actions, but that is not authorization. Input validation, parameterized database operations, rate limits, audit events, and tenant isolation are tested at API boundaries.

## 9. External services and AI

Provider integrations have explicit interfaces and sandbox/test modes. Online payment success is established only from authenticated server-side provider confirmation or reconciliation, never from a client callback alone. Webhook signatures and duplicate events are handled idempotently. Provider secrets are environment-managed and excluded from source control.

AI receives only approved, permission-filtered summaries. Deterministic queries calculate all figures; the model explains the result and can navigate to records. It has no direct write tools for rates, invoices, refunds, loans, payments, or pledged-item release. PII sharing is disabled by default until the data policy and consent support it. Basic help and navigation remain available without an AI provider.

## 10. Delivery and operations

Local development does not require Docker: use an Atlas Free cluster for synthetic development/demo data, or run MongoDB locally; migrations and API/frontend use local toolchains. Container deployment is optional documentation. CI should lint/type-check, run domain/API tests, verify migrations, and build both Android artifacts in a configured Android environment. Backups require encryption, retention, restore drills, and tenant-aware export controls.

## 11. Architecture decisions and gates

1. **Modular monolith first**: one FastAPI deployment and MongoDB database with module boundaries; split services only when measured scaling or isolation requires it.
2. **SQLite is the offline operational store**: local writes are durable before sync; server remains canonical across devices.
3. **SQLite plugin and ORM choice**: compare the free `@capacitor-community/sqlite` plugin plus SQL repositories with the licensed Capawesome SQLite/Drizzle adapter. Select after Android transaction, encryption, migration, and cost checks; Drizzle is used only with a verified driver.
4. **MongoDB data integrity**: MongoDB has no relational foreign keys. Tenant-scoped compound unique indexes, repository-enforced references, validators, transactional commands, append-only financial history, and periodic integrity reconciliation are required. Atlas Free is for synthetic development/demo data only; production requires an appropriate paid tier, operational monitoring, and tested backups.
5. **Static mobile frontend assumption**: Next.js runs as a static Capacitor bundle on Android; server rendering is not part of device runtime. Validate routing, plugin lifecycle, and asset paths in a minimal Android spike before domain features.
6. **Provisional offline invoice policy needs product decision**: local invoice creation can be supported, but branch-wide final invoice numbering and stock reservation cannot be guaranteed offline across multiple devices. The design therefore distinguishes local draft/provisional status from server-canonical posting and requires an explicit reconciliation policy before Phase 5.
7. **Pledge/lending, GST, payment, and privacy gates**: obtain qualified review and configured providers before enabling affected production workflows.

## 12. Decisions to resolve before implementation reaches dependent phases

- Offline completed-bill semantics, numbering, and conflict resolution by branch.
- Whether customer app supports account access before verified shop linkage.
- Initial GST configuration ownership and tax-review process.
- Supported payment, OTP, push, AI, market-rate, and printer providers/devices.
- Pledge workflow's legal scope and authorized operating entity.
- Backup key ownership, retention periods, and account deletion/export policy.




