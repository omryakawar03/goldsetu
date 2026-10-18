"""Tenant-aware MongoDB collections and required indexes."""
from dataclasses import dataclass
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase


@dataclass(frozen=True)
class IndexSpec:
    collection: str
    keys: tuple[tuple[str, int], ...]
    name: str
    unique: bool = False
    partial: dict[str, object] | None = None
    ttl_seconds: int | None = None


SPECS = (
    IndexSpec("shops", (("slug", ASCENDING),), "uq_shop_slug", True),
    IndexSpec("branches", (("shop_id", ASCENDING), ("code", ASCENDING)), "uq_branch_shop_code", True),
    IndexSpec("users", (("normalized_email", ASCENDING),), "uq_user_email", True),
    IndexSpec("memberships", (("shop_id", ASCENDING), ("user_id", ASCENDING), ("scope_id", ASCENDING)), "uq_membership_scope", True),
    IndexSpec("sessions", (("token_hash", ASCENDING),), "uq_session_token_hash", True),
    IndexSpec("sessions", (("expires_at", ASCENDING),), "ttl_session_expiry", ttl_seconds=0),
    IndexSpec("login_attempts", (("expires_at", ASCENDING),), "ttl_login_attempt_expiry", ttl_seconds=0),
    IndexSpec("staff_invitations", (("token_hash", ASCENDING),), "uq_invitation_token_hash", True),
    IndexSpec("staff_invitations", (("expires_at", ASCENDING),), "ttl_invitation_expiry", ttl_seconds=0),
    IndexSpec("customers", (("shop_id", ASCENDING), ("customer_number", ASCENDING)), "uq_customer_shop_number", True),
    IndexSpec("products", (("shop_id", ASCENDING), ("sku", ASCENDING)), "uq_product_shop_sku", True),
    IndexSpec("products", (("shop_id", ASCENDING), ("category", ASCENDING), ("published", ASCENDING)), "ix_product_catalogue"),
    IndexSpec("jewellery_items", (("shop_id", ASCENDING), ("serial_number", ASCENDING)), "uq_item_shop_serial", True),
    IndexSpec("jewellery_items", (("shop_id", ASCENDING), ("barcode", ASCENDING)), "uq_item_shop_barcode", True, {"barcode": {"$type": "string"}}),
    IndexSpec("suppliers", (("shop_id", ASCENDING), ("supplier_number", ASCENDING)), "uq_supplier_shop_number", True),
    IndexSpec("inventory_movements", (("shop_id", ASCENDING), ("movement_id", ASCENDING)), "uq_inventory_shop_movement", True),
    IndexSpec("inventory_movements", (("shop_id", ASCENDING), ("operation_id", ASCENDING)), "ix_inventory_operation"),
    IndexSpec("inventory_movements", (("shop_id", ASCENDING), ("branch_id", ASCENDING), ("created_at", DESCENDING)), "ix_inventory_branch_time"),
    IndexSpec("inventory_balances", (("shop_id", ASCENDING), ("branch_id", ASCENDING), ("product_id", ASCENDING)), "uq_inventory_balance_scope", True),
    IndexSpec("metal_rates", (("shop_id", ASCENDING), ("metal", ASCENDING), ("purity", ASCENDING), ("effective_at", DESCENDING)), "ix_rate_history"),
    IndexSpec("invoices", (("shop_id", ASCENDING), ("branch_id", ASCENDING), ("financial_year", ASCENDING), ("invoice_number", ASCENDING)), "uq_invoice_branch_number", True),
    IndexSpec("invoices", (("shop_id", ASCENDING), ("operation_id", ASCENDING)), "uq_invoice_shop_operation", True),
    IndexSpec("invoices", (("shop_id", ASCENDING), ("customer_id", ASCENDING), ("created_at", DESCENDING)), "ix_invoice_customer_history"),
    IndexSpec("invoice_counters", (("shop_id", ASCENDING), ("branch_id", ASCENDING), ("financial_year", ASCENDING)), "uq_invoice_counter_scope", True),
    IndexSpec("payments", (("shop_id", ASCENDING), ("idempotency_key", ASCENDING)), "uq_payment_idempotency", True),
    IndexSpec("payments", (("shop_id", ASCENDING), ("provider_reference", ASCENDING)), "uq_payment_provider_reference", True, {"provider_reference": {"$type": "string"}}),
    IndexSpec("journal_entries", (("shop_id", ASCENDING), ("transaction_id", ASCENDING)), "uq_journal_shop_transaction", True),
    IndexSpec("journal_entries", (("shop_id", ASCENDING), ("posted_at", DESCENDING)), "ix_journal_posted_at"),
    IndexSpec("pledge_accounts", (("shop_id", ASCENDING), ("branch_id", ASCENDING), ("account_number", ASCENDING)), "uq_pledge_branch_account", True),
    IndexSpec("pledge_accounts", (("shop_id", ASCENDING), ("operation_id", ASCENDING)), "uq_pledge_shop_operation", True),
    IndexSpec("pledge_accounts", (("shop_id", ASCENDING), ("status", ASCENDING), ("due_at", ASCENDING)), "ix_pledge_due"),
    IndexSpec("audit_events", (("shop_id", ASCENDING), ("event_id", ASCENDING)), "uq_audit_event", True),
    IndexSpec("audit_events", (("shop_id", ASCENDING), ("entity_type", ASCENDING), ("entity_id", ASCENDING), ("occurred_at", DESCENDING)), "ix_audit_entity_history"),
    IndexSpec("sync_operations", (("shop_id", ASCENDING), ("device_id", ASCENDING), ("operation_id", ASCENDING)), "uq_sync_device_operation", True),
    IndexSpec("sync_operations", (("shop_id", ASCENDING), ("state", ASCENDING), ("created_at", ASCENDING)), "ix_sync_pending"),
)


async def create_required_indexes(database: AsyncDatabase) -> None:
    """Create all declared indexes idempotently; intended for one migration runner."""
    by_collection: dict[str, list[IndexModel]] = {}
    for spec in SPECS:
        options: dict[str, object] = {"name": spec.name, "unique": spec.unique}
        if spec.partial is not None:
            options["partialFilterExpression"] = spec.partial
        if spec.ttl_seconds is not None:
            options["expireAfterSeconds"] = spec.ttl_seconds
        by_collection.setdefault(spec.collection, []).append(IndexModel(list(spec.keys), **options))
    for collection, indexes in by_collection.items():
        await database[collection].create_indexes(indexes)






