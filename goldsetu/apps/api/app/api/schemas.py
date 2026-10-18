"""FastAPI schemas for identity and tenant administration."""
from typing import Annotated
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.security.permissions import Role


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OwnerRegistration(InputModel):
    full_name: Annotated[str, Field(min_length=1, max_length=120)]
    email: EmailStr
    password: Annotated[str, Field(min_length=12, max_length=256)]
    shop_name: Annotated[str, Field(min_length=2, max_length=160)]
    shop_slug: Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")]
    branch_name: Annotated[str, Field(min_length=2, max_length=160)]
    branch_code: Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")]


class LoginRequest(InputModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=256)]
    shop_id: str | None = None
    branch_id: str | None = None


class BranchCreate(InputModel):
    code: Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")]
    name: Annotated[str, Field(min_length=2, max_length=160)]
    timezone: Annotated[str, Field(min_length=1, max_length=64)] = "Asia/Kolkata"


class AcceptInvitation(InputModel):
    email: EmailStr
    invite_token: Annotated[str, Field(min_length=32, max_length=256)]
    password: Annotated[str, Field(min_length=12, max_length=256)]
    display_name: Annotated[str | None, Field(min_length=1, max_length=120)] = None


class StaffInvite(InputModel):
    email: EmailStr
    display_name: Annotated[str, Field(min_length=1, max_length=120)]
    role: Role
    branch_id: str
    expires_hours: Annotated[int, Field(ge=1, le=168)] = 48


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: dict
    shop: dict
    branch: dict | None = None
    role: Role


class MembershipView(BaseModel):
    shop_id: str
    branch_id: str | None
    role: Role
    status: str


class ProductCreate(InputModel):
    sku: Annotated[str, Field(min_length=1, max_length=64)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    category: Annotated[str, Field(min_length=1, max_length=80)]
    stock_mode: Annotated[str, Field(pattern=r"^(unique_item|quantity)$")]
    purity: Annotated[str | None, Field(max_length=16)] = None
    reorder_threshold: Annotated[int, Field(ge=0, le=1_000_000)] = 0


class JewelleryItemCreate(InputModel):
    product_id: str
    serial_number: Annotated[str, Field(min_length=1, max_length=64)]
    barcode: Annotated[str | None, Field(min_length=1, max_length=64)] = None
    gross_weight_g: Decimal
    stone_weight_g: Decimal = Decimal("0")
    net_metal_weight_g: Decimal

    @field_validator("gross_weight_g", "stone_weight_g", "net_metal_weight_g", mode="before")
    @classmethod
    def reject_binary_float_weights(cls, value):
        if isinstance(value, float):
            raise ValueError("weights must be decimal strings or Decimal values, not binary floats")
        return value


class RateCreate(InputModel):
    metal: Annotated[str, Field(pattern=r"^(gold|silver)$")]
    purity: Annotated[str, Field(min_length=1, max_length=16)]
    rate_paise_per_gram: Annotated[int, Field(gt=0)]
    source: Annotated[str, Field(min_length=1, max_length=120)]
    effective_at: str
    is_manual: bool = True


class CustomerCreate(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=160)]
    phone: Annotated[str, Field(min_length=7, max_length=20)]
    email: str | None = None
    communication_consent: bool = False


class StockAdjustment(InputModel):
    product_id: str
    item_id: str | None = None
    quantity_delta: Annotated[int, Field(ne=0, ge=-1_000_000, le=1_000_000)]
    reason: Annotated[str, Field(min_length=3, max_length=80)]
    operation_id: Annotated[str, Field(min_length=8, max_length=64)]
    expected_version: Annotated[int, Field(ge=1)]


class InvoiceLineInput(InputModel):
    product_id: str
    item_id: str | None = None
    quantity: Annotated[int, Field(gt=0, le=1000)] = 1
    description: Annotated[str, Field(min_length=1, max_length=240)]
    gross_weight_g: Decimal | None = None
    net_metal_weight_g: Decimal | None = None
    metal_rate_paise_per_gram: Annotated[int | None, Field(gt=0)] = None
    making_charge_paise: Annotated[int, Field(ge=0)] = 0
    wastage_paise: Annotated[int, Field(ge=0)] = 0
    stone_value_paise: Annotated[int, Field(ge=0)] = 0
    taxable_value_paise: Annotated[int, Field(ge=0)]
    tax_paise: Annotated[int, Field(ge=0)] = 0

    @field_validator("gross_weight_g", "net_metal_weight_g", mode="before")
    @classmethod
    def reject_binary_float_weights(cls, value):
        if isinstance(value, float):
            raise ValueError("weights must be decimal strings or Decimal values, not binary floats")
        return value


class InvoiceCreate(InputModel):
    operation_id: Annotated[str, Field(min_length=8, max_length=64)]
    financial_year: Annotated[str, Field(pattern=r"^\d{4}-\d{2}$")]
    customer_id: str | None = None
    lines: Annotated[list[InvoiceLineInput], Field(min_length=1, max_length=100)]
    discount_paise: Annotated[int, Field(ge=0)] = 0
    amount_paid_paise: Annotated[int, Field(ge=0)] = 0


class PledgeCreate(InputModel):
    operation_id: Annotated[str, Field(min_length=8, max_length=64)]
    customer_id: str
    account_number: Annotated[str, Field(min_length=1, max_length=64)]
    principal_disbursed_paise: Annotated[int, Field(gt=0)]
    interest_rate_basis_points: Annotated[int, Field(ge=0, le=100_000)]
    interest_method: Annotated[str, Field(min_length=1, max_length=40)]
    due_at: str
    custody_reference: Annotated[str, Field(min_length=1, max_length=64)]


class InvoicePayment(InputModel):
    invoice_id: str
    idempotency_key: Annotated[str, Field(min_length=8, max_length=64)]
    amount_paise: Annotated[int, Field(gt=0)]
    method: Annotated[str, Field(pattern=r"^(cash|upi|card|bank_transfer)$")]
    provider_reference: Annotated[str | None, Field(max_length=120)] = None

