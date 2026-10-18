"""Validated domain document shapes. Persistence adapters own BSON encoding."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=64)]
Paise = Annotated[int, Field(strict=True, ge=0, le=9_000_000_000_000_000)]
Quantity = Annotated[int, Field(strict=True, gt=0, le=1_000_000)]


def _decimal_without_float(value: Any) -> Decimal:
    if isinstance(value, float):
        raise ValueError("binary floating-point values are not accepted")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError("value must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError("value must be finite")
    return result


class Metal(StrEnum):
    GOLD = "gold"
    SILVER = "silver"


class StockMode(StrEnum):
    UNIQUE_ITEM = "unique_item"
    QUANTITY = "quantity"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    PENDING_SYNC = "pending_sync"
    POSTED = "posted"
    VOIDED_BY_REVERSAL = "voided_by_reversal"


class PaymentStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class ItemStatus(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"
    DAMAGED = "damaged"
    IN_TRANSIT = "in_transit"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def all_datetimes_are_aware_utc(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("timestamps must include a timezone")
            return value.astimezone(timezone.utc)
        return value


class TenantDocument(StrictModel):
    id: Identifier = Field(default_factory=lambda: str(uuid4()))
    shop_id: Identifier
    branch_id: Identifier | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: Annotated[int, Field(ge=1)] = 1

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_are_utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(timezone.utc)


class ShopDocument(StrictModel):
    id: Identifier = Field(default_factory=lambda: str(uuid4()))
    name: Annotated[str, Field(min_length=1, max_length=160)]
    slug: Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    currency: str = "INR"
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BranchDocument(TenantDocument):
    code: Annotated[str, Field(min_length=1, max_length=24)]
    name: Annotated[str, Field(min_length=1, max_length=160)]
    timezone: str = "Asia/Kolkata"
    is_active: bool = True


class ProductDocument(TenantDocument):
    sku: Annotated[str, Field(min_length=1, max_length=64)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    category: Annotated[str, Field(min_length=1, max_length=80)]
    stock_mode: StockMode
    purity: str | None = None
    published: bool = False
    reorder_threshold: Annotated[int, Field(ge=0)] = 0


class JewelleryItemDocument(TenantDocument):
    product_id: Identifier
    serial_number: Identifier
    barcode: Identifier | None = None
    status: ItemStatus = ItemStatus.AVAILABLE
    gross_weight_g: Decimal
    stone_weight_g: Decimal = Decimal("0")
    net_metal_weight_g: Decimal

    @field_validator("gross_weight_g", "stone_weight_g", "net_metal_weight_g", mode="before")
    @classmethod
    def finite_decimal_weights(cls, value: Any) -> Decimal:
        return _decimal_without_float(value)

    @model_validator(mode="after")
    def weights_are_consistent(self) -> "JewelleryItemDocument":
        if self.gross_weight_g <= 0 or self.stone_weight_g < 0 or self.net_metal_weight_g < 0:
            raise ValueError("weights must be positive/non-negative")
        if self.net_metal_weight_g > self.gross_weight_g:
            raise ValueError("net metal weight cannot exceed gross weight")
        if self.stone_weight_g > self.gross_weight_g:
            raise ValueError("stone weight cannot exceed gross weight")
        return self


class MetalRateDocument(TenantDocument):
    metal: Metal
    purity: Annotated[str, Field(min_length=1, max_length=16)]
    rate_paise_per_gram: Annotated[int, Field(strict=True, gt=0)]
    source: Annotated[str, Field(min_length=1, max_length=120)]
    effective_at: datetime
    authorized_by: Identifier
    is_manual: bool = True


class InvoiceLineSnapshot(StrictModel):
    product_id: Identifier
    item_id: Identifier | None = None
    description: Annotated[str, Field(min_length=1, max_length=240)]
    quantity: Quantity = 1
    gross_weight_g: Decimal | None = None
    net_metal_weight_g: Decimal | None = None
    metal_rate_paise_per_gram: Annotated[int, Field(strict=True, gt=0)] | None = None
    making_charge_paise: Paise = 0
    wastage_paise: Paise = 0
    stone_value_paise: Paise = 0
    taxable_value_paise: Paise
    tax_paise: Paise = 0
    total_paise: Paise

    @field_validator("gross_weight_g", "net_metal_weight_g", mode="before")
    @classmethod
    def optional_weights_are_decimal(cls, value: Any) -> Decimal | None:
        return None if value is None else _decimal_without_float(value)

    @model_validator(mode="after")
    def amount_components_are_consistent(self) -> "InvoiceLineSnapshot":
        if self.total_paise != self.taxable_value_paise + self.tax_paise:
            raise ValueError("line total must equal taxable value plus tax")
        return self


class InvoiceDocument(TenantDocument):
    branch_id: Identifier
    invoice_number: Identifier
    financial_year: Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
    customer_id: Identifier | None = None
    operation_id: Identifier
    status: InvoiceStatus
    lines: Annotated[list[InvoiceLineSnapshot], Field(min_length=1, max_length=500)]
    subtotal_paise: Paise
    discount_paise: Paise = 0
    tax_paise: Paise = 0
    total_paise: Paise
    amount_paid_paise: Paise = 0
    payment_state: PaymentStatus = PaymentStatus.PENDING_VERIFICATION
    currency: str = "INR"

    @model_validator(mode="after")
    def totals_are_consistent(self) -> "InvoiceDocument":
        if self.amount_paid_paise > self.total_paise:
            raise ValueError("paid amount cannot exceed invoice total")
        if self.total_paise != self.subtotal_paise - self.discount_paise + self.tax_paise:
            raise ValueError("invoice total does not match subtotal, discount, and tax")
        return self


class PaymentDocument(TenantDocument):
    invoice_id: Identifier | None = None
    pledge_account_id: Identifier | None = None
    operation_id: Identifier
    idempotency_key: Identifier
    method: Annotated[str, Field(min_length=1, max_length=32)]
    status: PaymentStatus
    amount_paise: Annotated[int, Field(strict=True, gt=0)]
    provider_reference: str | None = None
    verified_at: datetime | None = None
    verified_by: Identifier | None = None

    @model_validator(mode="after")
    def one_target_only(self) -> "PaymentDocument":
        if (self.invoice_id is None) == (self.pledge_account_id is None):
            raise ValueError("payment must target exactly one invoice or pledge account")
        if self.status == PaymentStatus.SUCCEEDED and self.verified_at is None:
            raise ValueError("successful payments require a server-side verification timestamp")
        return self


class InventoryMovementDocument(TenantDocument):
    movement_id: Identifier = Field(default_factory=lambda: str(uuid4()))
    operation_id: Identifier
    product_id: Identifier
    item_id: Identifier | None = None
    quantity_delta: Annotated[int, Field(strict=True, ne=0, ge=-1_000_000, le=1_000_000)]
    reason: Annotated[str, Field(min_length=1, max_length=80)]
    reference_id: Identifier | None = None
    recorded_by: Identifier


class JournalLine(StrictModel):
    account_id: Identifier
    debit_paise: Paise = 0
    credit_paise: Paise = 0

    @model_validator(mode="after")
    def exactly_one_side(self) -> "JournalLine":
        if (self.debit_paise > 0) == (self.credit_paise > 0):
            raise ValueError("each journal line must have either debit or credit")
        return self


class JournalEntryDocument(TenantDocument):
    transaction_id: Identifier
    posted_at: datetime
    source_type: Annotated[str, Field(min_length=1, max_length=40)]
    source_id: Identifier
    lines: Annotated[list[JournalLine], Field(min_length=2)]
    reversal_of: Identifier | None = None

    @model_validator(mode="after")
    def journal_balances(self) -> "JournalEntryDocument":
        debits = sum(line.debit_paise for line in self.lines)
        credits = sum(line.credit_paise for line in self.lines)
        if debits != credits or debits <= 0:
            raise ValueError("posted journal debits and credits must balance to a positive amount")
        return self


class PledgeAccountDocument(TenantDocument):
    account_number: Identifier
    customer_id: Identifier
    status: Annotated[str, Field(pattern=r"^(open|overdue|closed)$")]
    principal_disbursed_paise: Annotated[int, Field(strict=True, gt=0)]
    principal_outstanding_paise: Paise
    interest_outstanding_paise: Paise = 0
    interest_rate_basis_points: Annotated[int, Field(strict=True, ge=0, le=100_000)]
    interest_method: Annotated[str, Field(min_length=1, max_length=40)]
    due_at: datetime
    custody_reference: Identifier
    created_by: Identifier


    @model_validator(mode="after")
    def outstanding_principal_is_bounded(self) -> "PledgeAccountDocument":
        if self.principal_outstanding_paise > self.principal_disbursed_paise:
            raise ValueError("principal outstanding cannot exceed amount disbursed")
        return self


class AuditEventDocument(TenantDocument):
    event_id: Identifier
    actor_id: Identifier
    action: Annotated[str, Field(min_length=1, max_length=80)]
    entity_type: Annotated[str, Field(min_length=1, max_length=80)]
    entity_id: Identifier
    occurred_at: datetime
    reason: str | None = None
    before_hash: str | None = None
    after_hash: str | None = None


class SyncOperationDocument(TenantDocument):
    device_id: Identifier
    operation_id: Identifier
    entity_type: Annotated[str, Field(min_length=1, max_length=80)]
    entity_id: Identifier
    base_version: Annotated[int, Field(ge=0)]
    payload_version: Annotated[int, Field(ge=1)]
    state: Annotated[str, Field(pattern=r"^(queued|applied|conflict|rejected)$")]
    result_reference: Identifier | None = None




