# GOLDSETU

GOLDSETU is being built as two Android apps for Indian jewellery businesses: **Business** for shop staff and **Customer** for verified customers. The repository now has MongoDB document/index definitions, Decimal-safe domain rules, initial FastAPI identity/tenant and basic business routes, an end-to-end guide, and a Hinglish brochure. The API workflows are not production-ready; no Next.js app or APK is built yet.

## Documents

- [Architecture](docs/architecture.md)
- [Phase 1 acceptance record](docs/phase-1-acceptance.md)
- [Phase 2 data model](docs/phase-2-data-model.md)
- [Phase 2 acceptance](docs/phase-2-acceptance.md)
- [Phase 3 implementation status](docs/phase-3-acceptance.md)
- [End-to-end setup, release, and update guide](docs/END_TO_END_GUIDE.md)
- [Hinglish product brochure](docs/brochure-hinglish.html)
- [Business app screen visual](docs/assets/business-app-screen.svg)
- [Customer app screen visual](docs/assets/customer-app-screen.svg)
- [Implementation plan](docs/implementation-plan.md)

## Repository layout

```text
goldsetu/
├── apps/
│   ├── business/                 # Next.js + Capacitor Android app
│   ├── customer/                 # Separate Next.js + Capacitor Android app
│   └── api/                      # FastAPI modular monolith
│       ├── app/domain/            # Pydantic models and Decimal-safe rules
│       ├── app/db/                # PyMongo Async, indexes, migrations
│       └── tests/                 # Synthetic Python tests
├── packages/
│   ├── ui/                       # Shared accessible UI
│   ├── validation/               # Shared Zod schemas
│   ├── domain/                   # Shared deterministic TypeScript rules
│   ├── api-client/               # Typed versioned REST client
│   └── i18n/                     # English, Hindi, Marathi
├── docs/
└── scripts/
```

The mobile database is SQLite. MongoDB Atlas is the synchronized server store. Every cross-device query is tenant-scoped by the authenticated server identity. Redux is transient UI state, not a durable store.

## Technology plan

- Frontend: Node.js LTS, pnpm, Next.js, React, TypeScript, Tailwind CSS, Redux Toolkit, Zod, Capacitor.
- Business offline store: native Capacitor SQLite behind repositories/services. The plugin and ORM choice remains an Android compatibility/license gate.
- Backend: Python 3.12+, FastAPI, Pydantic 2, PyMongo Async, MongoDB Atlas, versioned migrations.
- Tests: pytest, Vitest, React Testing Library, and Playwright for appropriate flows.

## Atlas Free boundary

Use Atlas Free for synthetic development and demonstration data. It currently has 512 MB storage including indexes, a 100 operations/second throughput limit, no Atlas-managed backups, and can pause after 30 idle days. Export and restore manually; do not put live customer, payment, or pledge data there. Move to a suitable paid tier with managed backup/monitoring before a real production launch. See the official [Free cluster limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/) and [cluster comparison](https://www.mongodb.com/docs/atlas/manage-clusters/).

## API run commands

From `goldsetu/apps/api`, after creating a virtual environment and installing dependencies:

```powershell
python -m pip install -e ".[test]"
python -m unittest discover -s tests -v
goldsetu-migrate
uvicorn app.main:app --reload
```

Set `MONGODB_URI` and `MONGODB_DATABASE` in `apps/api/.env` first. The migration command writes indexes to that database: use a synthetic development database only. Current tests are synthetic and do not connect to Atlas; API/transaction integration remains unverified. Open the Hinglish brochure HTML in a browser; use Print → Save as PDF. See the [end-to-end guide](docs/END_TO_END_GUIDE.md) for setup, safe release/update strategy, and exact feature limits.




