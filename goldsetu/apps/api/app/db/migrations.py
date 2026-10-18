"""Small, explicit, sequential migration runner. Execute once per release job."""
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pymongo import IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from app.db.indexes import create_required_indexes

Migration = Callable[[AsyncDatabase], Awaitable[None]]


async def migration_0001_tenant_indexes(database: AsyncDatabase) -> None:
    await create_required_indexes(database)


async def migration_0002_identity_indexes(database: AsyncDatabase) -> None:
    # Identity indexes were added after the original core index release.
    await database.users.create_index("normalized_email", unique=True, name="uq_user_email")
    await database.memberships.create_index([("shop_id", 1), ("user_id", 1), ("scope_id", 1)], unique=True, name="uq_membership_scope")
    await database.sessions.create_indexes([
        IndexModel([("token_hash", 1)], unique=True, name="uq_session_token_hash"),
        IndexModel([("expires_at", 1)], name="ttl_session_expiry", expireAfterSeconds=0),
    ])
    await database.login_attempts.create_index("expires_at", name="ttl_login_attempt_expiry", expireAfterSeconds=0)
    await database.staff_invitations.create_indexes([
        IndexModel([("token_hash", 1)], unique=True, name="uq_invitation_token_hash"),
        IndexModel([("expires_at", 1)], name="ttl_invitation_expiry", expireAfterSeconds=0),
    ])


async def migration_0003_invoice_counter_index(database: AsyncDatabase) -> None:
    await database.invoice_counters.create_index(
        [("shop_id", 1), ("branch_id", 1), ("financial_year", 1)],
        unique=True,
        name="uq_invoice_counter_scope",
    )


async def migration_0004_inventory_balance_index(database: AsyncDatabase) -> None:
    await database.inventory_balances.create_index(
        [("shop_id", 1), ("branch_id", 1), ("product_id", 1)],
        unique=True,
        name="uq_inventory_balance_scope",
    )


async def migration_0005_pledge_operation_index(database: AsyncDatabase) -> None:
    await database.pledge_accounts.create_index(
        [("shop_id", 1), ("operation_id", 1)], unique=True, name="uq_pledge_shop_operation"
    )


MIGRATIONS: tuple[tuple[int, str, Migration], ...] = (
    (1, "tenant_scoped_core_indexes", migration_0001_tenant_indexes),
    (2, "identity_session_indexes", migration_0002_identity_indexes),
    (3, "invoice_counter_scope_index", migration_0003_invoice_counter_index),
    (4, "inventory_balance_scope_index", migration_0004_inventory_balance_index),
    (5, "pledge_operation_index", migration_0005_pledge_operation_index),
)


async def migrate(database: AsyncDatabase) -> list[int]:
    """Apply missing migrations; index creation and migration records are idempotent.

    Run one migration process at a time. Never invoke this automatically from API workers.
    """
    applied = database["schema_migrations"]
    await applied.create_index("version", unique=True, name="uq_schema_migration_version")
    existing = await applied.find({}, {"version": 1}).to_list(length=1000)
    versions = {doc["version"] for doc in existing}
    completed: list[int] = []
    for version, name, operation in MIGRATIONS:
        if version in versions:
            continue
        await operation(database)
        await applied.insert_one({
            "version": version,
            "name": name,
            "applied_at": datetime.now(timezone.utc),
        })
        completed.append(version)
    return completed

