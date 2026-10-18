"""Minimal role vocabulary and permission checks; API dependencies enforce these server-side."""
from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    BRANCH_MANAGER = "branch_manager"
    CASHIER = "cashier"
    ACCOUNTANT = "accountant"
    INVENTORY_MANAGER = "inventory_manager"
    SALES_EXECUTIVE = "sales_executive"
    LOAN_MANAGER = "loan_manager"
    READ_ONLY_AUDITOR = "read_only_auditor"


ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.OWNER: frozenset({"*"}),
    Role.ADMINISTRATOR: frozenset({"shop:read", "branch:read", "branch:manage", "staff:manage", "customer:read", "customer:manage", "product:read", "product:manage", "inventory:read", "inventory:manage", "rate:read", "rate:manage", "invoice:read", "invoice:create", "invoice:reverse", "payment:read", "payment:record", "payment:refund", "accounting:read", "accounting:post", "report:read", "pledge:read", "pledge:manage", "pledge:release", "audit:read"}),
    Role.BRANCH_MANAGER: frozenset({"shop:read", "branch:read", "customer:read", "customer:manage", "product:read", "product:manage", "inventory:read", "inventory:manage", "rate:read", "invoice:read", "invoice:create", "payment:read", "payment:record", "report:read", "pledge:read", "pledge:manage", "audit:read"}),
    Role.CASHIER: frozenset({"shop:read", "branch:read", "customer:read", "invoice:read", "invoice:create", "payment:read", "payment:record"}),
    Role.ACCOUNTANT: frozenset({"shop:read", "branch:read", "customer:read", "invoice:read", "payment:read", "accounting:read", "accounting:post", "report:read", "audit:read"}),
    Role.INVENTORY_MANAGER: frozenset({"shop:read", "branch:read", "product:read", "product:manage", "inventory:read", "inventory:manage", "rate:read"}),
    Role.SALES_EXECUTIVE: frozenset({"shop:read", "branch:read", "customer:read", "product:read", "inventory:read", "rate:read", "invoice:read", "invoice:create", "payment:read"}),
    Role.LOAN_MANAGER: frozenset({"shop:read", "branch:read", "customer:read", "pledge:read", "pledge:manage", "payment:read", "payment:record"}),
    Role.READ_ONLY_AUDITOR: frozenset({"shop:read", "branch:read", "customer:read", "product:read", "inventory:read", "rate:read", "invoice:read", "payment:read", "accounting:read", "report:read", "pledge:read", "audit:read"}),
}


def role_allows(role: Role | str, permission: str) -> bool:
    try:
        canonical = role if isinstance(role, Role) else Role(role)
    except ValueError:
        return False
    grants = ROLE_PERMISSIONS[canonical]
    return "*" in grants or permission in grants
