# Phase 1 acceptance criteria

Phase 1 is complete when the design and starter structure make subsequent implementation reviewable without claiming working features.

## Architecture and structure

- [x] Two separate Android apps are defined with independent identities/configuration and shared packages.
- [x] Next.js/TypeScript, React, Tailwind, Redux Toolkit, Zod, Capacitor, SQLite, FastAPI, MongoDB Atlas, migrations, and pnpm are assigned to clear layers.
- [x] SQLite-to-sync boundaries, tenant isolation, server authority, and offline payment semantics are documented.
- [x] SQLite/ORM candidates and the licensed Drizzle-compatible option are identified as a Phase 2 dependency decision.
- [x] Conflict behavior is defined for rates, inventory, invoices, payments, pledge balances, and posted accounting.
- [x] Money, weight, inventory, invoice immutability, audit, AI, security, GST, and lending constraints are recorded.
- [x] Repository tree and dependency families are documented.
- [x] Unresolved decisions and production gates are explicit.

## Project checkpoint

- [x] Root README explains purpose, target layout, architecture, dependency plan, local development direction, and phase status.
- [x] Architecture, acceptance criteria, and implementation plan documents exist.
- [x] Starter directories for both apps, packages, API, docs, and scripts exist.
- [x] Existing workspace content is left untouched by this Phase 1 work.
- [x] No feature, test result, or APK build is represented as complete without implementation/evidence.

## Phase exit

- [x] User approved moving into Phase 2.

This checklist only confirms Phase 1 planning artifacts and repository skeleton. It does not satisfy the final product acceptance criteria or imply any tested implementation.




