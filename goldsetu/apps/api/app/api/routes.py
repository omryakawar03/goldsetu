"""Authentication and tenant-scoped shop administration endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from decimal import Decimal
import hashlib
import secrets
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.errors import DuplicateKeyError
from pymongo.asynchronous.database import AsyncDatabase

from app.api.schemas import (AcceptInvitation, BranchCreate, CustomerCreate, InvoiceCreate, InvoicePayment, JewelleryItemCreate,
    LoginRequest, OwnerRegistration, PledgeCreate, ProductCreate, RateCreate,
    SessionResponse, StaffInvite, StockAdjustment)
from app.db.connection import get_database
from app.domain.models import AuditEventDocument, InvoiceDocument, InvoiceLineSnapshot, InvoiceStatus, JewelleryItemDocument, PledgeAccountDocument, PaymentDocument, PaymentStatus
from app.security.credentials import hash_password, new_session_token, token_digest, verify_password
from app.security.permissions import ROLE_PERMISSIONS, Role, role_allows

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)
SESSION_HOURS = 12
LOGIN_WINDOW_MINUTES = 15
LOGIN_MAX_FAILURES = 8
_DUMMY_HASH = hash_password("GOLDSETU-invalid-password-placeholder")


class Identity(dict):
    """Trusted identity assembled from a live server session and active membership."""


def normalized_email(value: str) -> str:
    return value.strip().casefold()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_user(user: dict[str, Any]) -> dict[str, str]:
    return {"id": str(user["id"]), "display_name": str(user["display_name"]), "email": str(user["normalized_email"])}


async def _audit(db: AsyncDatabase, *, shop_id: str, actor_id: str, action: str, entity_type: str, entity_id: str, branch_id: str | None = None, reason: str | None = None, session: Any = None) -> None:
    event = AuditEventDocument(shop_id=shop_id, branch_id=branch_id, event_id=str(uuid4()), actor_id=actor_id, action=action, entity_type=entity_type, entity_id=entity_id, occurred_at=_now(), reason=reason)
    await db.audit_events.insert_one(event.model_dump(), session=session)


async def _new_session(db: AsyncDatabase, user: dict[str, Any], membership: dict[str, Any], branch: dict[str, Any] | None, *, client_label: str) -> tuple[str, datetime]:
    token = new_session_token()
    expiry = _now() + timedelta(hours=SESSION_HOURS)
    session_doc = {
        "id": str(uuid4()), "token_hash": token_digest(token), "user_id": user["id"],
        "membership_id": membership["id"], "shop_id": membership["shop_id"],
        "branch_id": branch["id"] if branch else membership.get("branch_id"),
        "role": membership["role"], "client_label": client_label[:120],
        "created_at": _now(), "expires_at": expiry, "revoked_at": None,
    }
    await db.sessions.insert_one(session_doc)
    return token, expiry


def _session_response(token: str, expiry: datetime, user: dict[str, Any], shop: dict[str, Any], branch: dict[str, Any] | None, role: str) -> SessionResponse:
    return SessionResponse(access_token=token, expires_at=expiry.isoformat(), user=_safe_user(user), shop={"id": str(shop["id"]), "name": str(shop["name"]), "slug": str(shop["slug"])}, branch={"id": str(branch["id"]), "name": str(branch["name"]), "code": str(branch["code"])} if branch else None, role=Role(role))


async def _rate_limit_login(db: AsyncDatabase, email: str, client_ip: str) -> None:
    now = _now()
    key = hashlib.sha256(f"{email}|{client_ip}".encode()).hexdigest()
    attempt = await db.login_attempts.find_one({"_id": key, "expires_at": {"$gt": now}})
    if attempt and int(attempt.get("failures", 0)) >= LOGIN_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.", headers={"Retry-After": "900"})


async def _record_login_failure(db: AsyncDatabase, email: str, client_ip: str) -> None:
    key = hashlib.sha256(f"{email}|{client_ip}".encode()).hexdigest()
    await db.login_attempts.update_one({"_id": key}, {"$inc": {"failures": 1}, "$set": {"expires_at": _now() + timedelta(minutes=LOGIN_WINDOW_MINUTES)}}, upsert=True)


async def _choose_membership(db: AsyncDatabase, user_id: str, shop_id: str | None, branch_id: str | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    query: dict[str, Any] = {"user_id": user_id, "status": "active"}
    if shop_id:
        query["shop_id"] = shop_id
    memberships = await db.memberships.find(query).to_list(length=100)
    if branch_id:
        memberships = [m for m in memberships if m.get("branch_id") in (None, branch_id)]
    if not memberships:
        raise HTTPException(status_code=403, detail="No active membership matches this shop and branch")
    if len(memberships) != 1:
        raise HTTPException(status_code=409, detail="Choose a shop and, when needed, a branch to continue")
    membership = memberships[0]
    shop = await db.shops.find_one({"id": membership["shop_id"], "status": "active"})
    if not shop:
        raise HTTPException(status_code=403, detail="Shop access is unavailable")
    branch = None
    selected_branch = branch_id or membership.get("branch_id")
    if selected_branch:
        branch = await db.branches.find_one({"id": selected_branch, "shop_id": membership["shop_id"], "is_active": True})
        if not branch:
            raise HTTPException(status_code=403, detail="Branch access is unavailable")
    return membership, shop, branch


async def current_identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncDatabase = Depends(get_database)) -> Identity:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status_code=401, detail="Sign in required", headers={"WWW-Authenticate": "Bearer"})
    session = await db.sessions.find_one({"token_hash": token_digest(credentials.credentials), "revoked_at": None, "expires_at": {"$gt": _now()}})
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or revoked", headers={"WWW-Authenticate": "Bearer"})
    user = await db.users.find_one({"id": session["user_id"], "status": "active"})
    membership = await db.memberships.find_one({"id": session["membership_id"], "user_id": session["user_id"], "shop_id": session["shop_id"], "status": "active"})
    if not user or not membership:
        raise HTTPException(status_code=401, detail="Account access is unavailable", headers={"WWW-Authenticate": "Bearer"})
    shop = await db.shops.find_one({"id": session["shop_id"], "status": "active"})
    if not shop:
        raise HTTPException(status_code=403, detail="Shop access is unavailable")
    branch_id = session.get("branch_id")
    if membership.get("branch_id") and membership["branch_id"] != branch_id:
        raise HTTPException(status_code=403, detail="Session branch no longer matches this membership")
    branch = None
    if branch_id:
        branch = await db.branches.find_one({"id": branch_id, "shop_id": session["shop_id"], "is_active": True})
        if not branch:
            raise HTTPException(status_code=403, detail="Branch access is unavailable")
    return Identity(user=user, membership=membership, session=session, shop_id=session["shop_id"], branch_id=branch_id, role=Role(membership["role"]), branch=branch)


def require_permission(permission: str):
    async def dependency(identity: Identity = Depends(current_identity)) -> Identity:
        if not role_allows(identity["role"], permission):
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return identity
    return dependency


@router.post("/auth/register-owner", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def register_owner(payload: OwnerRegistration, request: Request, db: AsyncDatabase = Depends(get_database)) -> SessionResponse:
    now = _now()
    email = normalized_email(str(payload.email))
    user_id, shop_id, branch_id, membership_id = (str(uuid4()) for _ in range(4))
    token = new_session_token()
    expiry = now + timedelta(hours=SESSION_HOURS)
    user = {"id": user_id, "normalized_email": email, "display_name": payload.full_name, "password_hash": hash_password(payload.password), "status": "active", "created_at": now, "updated_at": now}
    shop = {"id": shop_id, "name": payload.shop_name, "slug": payload.shop_slug, "currency": "INR", "status": "active", "created_at": now}
    branch = {"id": branch_id, "shop_id": shop_id, "code": payload.branch_code.upper(), "name": payload.branch_name, "timezone": "Asia/Kolkata", "is_active": True, "created_at": now, "updated_at": now, "version": 1}
    membership = {"id": membership_id, "shop_id": shop_id, "user_id": user_id, "branch_id": None, "scope_id": "*", "role": Role.OWNER.value, "status": "active", "created_at": now}
    session_doc = {"id": str(uuid4()), "token_hash": token_digest(token), "user_id": user_id, "membership_id": membership_id, "shop_id": shop_id, "branch_id": branch_id, "role": Role.OWNER.value, "client_label": (request.headers.get("user-agent") or "new-device")[:120], "created_at": now, "expires_at": expiry, "revoked_at": None}
    try:
        async with await db.client.start_session() as mongo_session:
            async with mongo_session.start_transaction():
                await db.users.insert_one(user, session=mongo_session)
                await db.shops.insert_one(shop, session=mongo_session)
                await db.branches.insert_one(branch, session=mongo_session)
                await db.memberships.insert_one(membership, session=mongo_session)
                await db.sessions.insert_one(session_doc, session=mongo_session)
                await _audit(db, shop_id=shop_id, actor_id=user_id, action="shop.owner_registered", entity_type="shop", entity_id=shop_id, branch_id=branch_id, session=mongo_session)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="That email or shop URL is already registered") from None
    return _session_response(token, expiry, user, shop, branch, Role.OWNER.value)


@router.post("/auth/login", response_model=SessionResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncDatabase = Depends(get_database)) -> SessionResponse:
    email = normalized_email(str(payload.email))
    client_ip = request.client.host if request.client else "unknown"
    await _rate_limit_login(db, email, client_ip)
    user = await db.users.find_one({"normalized_email": email, "status": "active"})
    stored_hash = user.get("password_hash") if user else _DUMMY_HASH
    if not verify_password(payload.password, stored_hash):
        await _record_login_failure(db, email, client_ip)
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    try:
        membership, shop, branch = await _choose_membership(db, user["id"], payload.shop_id, payload.branch_id)
    except HTTPException:
        raise
    token, expiry = await _new_session(db, user, membership, branch, client_label=(request.headers.get("user-agent") or "mobile")[:120])
    key = hashlib.sha256(f"{email}|{client_ip}".encode()).hexdigest()
    await db.login_attempts.delete_one({"_id": key})
    return _session_response(token, expiry, user, shop, branch, membership["role"])


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(identity: Identity = Depends(current_identity), db: AsyncDatabase = Depends(get_database)) -> None:
    await db.sessions.update_one({"id": identity["session"]["id"], "revoked_at": None}, {"$set": {"revoked_at": _now()}})


@router.post("/auth/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(identity: Identity = Depends(current_identity), db: AsyncDatabase = Depends(get_database)) -> None:
    await db.sessions.update_many({"user_id": identity["user"]["id"], "revoked_at": None}, {"$set": {"revoked_at": _now()}})


@router.get("/auth/me")
async def me(identity: Identity = Depends(current_identity)) -> dict[str, Any]:
    grants = ROLE_PERMISSIONS[identity["role"]]
    permissions = sorted({p for role_grants in ROLE_PERMISSIONS.values() for p in role_grants if p != "*"}) if "*" in grants else sorted(grants)
    return {"user": _safe_user(identity["user"]), "shop_id": identity["shop_id"], "branch_id": identity["branch_id"], "role": identity["role"].value, "permissions": permissions}


@router.get("/branches")
async def list_branches(identity: Identity = Depends(require_permission("branch:read")), db: AsyncDatabase = Depends(get_database)) -> list[dict[str, Any]]:
    query: dict[str, Any] = {"shop_id": identity["shop_id"], "is_active": True}
    if identity["membership"].get("branch_id"):
        query["id"] = identity["membership"]["branch_id"]
    cursor = db.branches.find(query, {"_id": 0, "id": 1, "code": 1, "name": 1, "timezone": 1})
    return await cursor.to_list(length=500)


@router.post("/branches", status_code=status.HTTP_201_CREATED)
async def create_branch(payload: BranchCreate, identity: Identity = Depends(require_permission("branch:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, str]:
    now = _now()
    branch = {"id": str(uuid4()), "shop_id": identity["shop_id"], "code": payload.code.upper(), "name": payload.name, "timezone": payload.timezone, "is_active": True, "created_at": now, "updated_at": now, "version": 1}
    try:
        await db.branches.insert_one(branch)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Branch code already exists in this shop") from None
    await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="branch.created", entity_type="branch", entity_id=branch["id"], branch_id=branch["id"])
    return {"id": branch["id"], "code": branch["code"], "name": branch["name"]}


@router.post("/staff/invitations", status_code=status.HTTP_201_CREATED)
async def invite_staff(payload: StaffInvite, identity: Identity = Depends(require_permission("staff:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, str]:
    if payload.role == Role.OWNER:
        raise HTTPException(status_code=403, detail="Owner access cannot be granted through a staff invitation")
    if identity["role"] != Role.OWNER and payload.role == Role.ADMINISTRATOR:
        raise HTTPException(status_code=403, detail="Only the owner may invite an administrator")
    branch = await db.branches.find_one({"id": payload.branch_id, "shop_id": identity["shop_id"], "is_active": True})
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    invite_token = secrets.token_urlsafe(32)
    now = _now()
    invite = {"id": str(uuid4()), "token_hash": token_digest(invite_token), "shop_id": identity["shop_id"], "branch_id": branch["id"], "email": normalized_email(str(payload.email)), "display_name": payload.display_name, "role": payload.role.value, "status": "pending", "created_by": identity["user"]["id"], "created_at": now, "expires_at": now + timedelta(hours=payload.expires_hours)}
    await db.staff_invitations.insert_one(invite)
    await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="staff.invitation_created", entity_type="staff_invitation", entity_id=invite["id"], branch_id=branch["id"])
    # Return once so the owner can hand this to an authorized messaging channel; no message is sent.
    return {"invitation_id": invite["id"], "invite_token": invite_token, "expires_at": invite["expires_at"].isoformat(), "delivery": "manual_share_required"}



@router.post("/auth/accept-invitation", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def accept_invitation(payload: AcceptInvitation, request: Request, db: AsyncDatabase = Depends(get_database)) -> SessionResponse:
    now = _now()
    email = normalized_email(str(payload.email))
    invitation = await db.staff_invitations.find_one({"token_hash": token_digest(payload.invite_token), "email": email, "status": "pending", "expires_at": {"$gt": now}})
    if not invitation:
        raise HTTPException(status_code=400, detail="Invitation is invalid, expired, or already used")
    user = await db.users.find_one({"normalized_email": email, "status": "active"})
    if user:
        if not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Sign in with the existing account password to accept this invitation")
    else:
        if not payload.display_name:
            raise HTTPException(status_code=422, detail="display_name is required for a new account")
        user = {"id": str(uuid4()), "normalized_email": email, "display_name": payload.display_name, "password_hash": hash_password(payload.password), "status": "active", "created_at": now, "updated_at": now}
    user_id = user["id"]
    membership = {"id": str(uuid4()), "shop_id": invitation["shop_id"], "user_id": user_id, "branch_id": invitation["branch_id"], "scope_id": invitation["branch_id"], "role": invitation["role"], "status": "active", "created_at": now}
    token = new_session_token()
    expiry = now + timedelta(hours=SESSION_HOURS)
    session_doc = {"id": str(uuid4()), "token_hash": token_digest(token), "user_id": user_id, "membership_id": membership["id"], "shop_id": invitation["shop_id"], "branch_id": invitation["branch_id"], "role": invitation["role"], "client_label": (request.headers.get("user-agent") or "mobile")[:120], "created_at": now, "expires_at": expiry, "revoked_at": None}
    try:
        async with await db.client.start_session() as mongo_session:
            async with mongo_session.start_transaction():
                current_invite = await db.staff_invitations.find_one({"id": invitation["id"], "status": "pending", "expires_at": {"$gt": now}}, session=mongo_session)
                if not current_invite:
                    raise HTTPException(status_code=409, detail="Invitation was already accepted")
                if not await db.users.find_one({"id": user_id}, session=mongo_session):
                    await db.users.insert_one(user, session=mongo_session)
                await db.memberships.insert_one(membership, session=mongo_session)
                updated = await db.staff_invitations.update_one({"id": invitation["id"], "status": "pending"}, {"$set": {"status": "accepted", "accepted_at": now, "accepted_by": user_id}}, session=mongo_session)
                if updated.modified_count != 1:
                    raise HTTPException(status_code=409, detail="Invitation was already accepted")
                await db.sessions.insert_one(session_doc, session=mongo_session)
                await _audit(db, shop_id=invitation["shop_id"], actor_id=user_id, action="staff.invitation_accepted", entity_type="membership", entity_id=membership["id"], branch_id=invitation["branch_id"], session=mongo_session)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="This account already has a membership for the invited branch") from None
    shop = await db.shops.find_one({"id": invitation["shop_id"]})
    branch = await db.branches.find_one({"id": invitation["branch_id"], "shop_id": invitation["shop_id"]})
    return _session_response(token, expiry, user, shop, branch, invitation["role"])
@router.get("/security/ping")
async def security_ping(identity: Identity = Depends(current_identity)) -> dict[str, str]:
    return {"status": "authenticated", "shop_id": identity["shop_id"]}


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, identity: Identity = Depends(require_permission("product:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    now = _now()
    product = {"id": str(uuid4()), "shop_id": identity["shop_id"], "sku": payload.sku.strip().upper(), "name": payload.name, "category": payload.category, "stock_mode": payload.stock_mode, "purity": payload.purity, "published": False, "reorder_threshold": payload.reorder_threshold, "created_at": now, "updated_at": now, "version": 1}
    try:
        await db.products.insert_one(product)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="SKU already exists in this shop") from None
    await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="product.created", entity_type="product", entity_id=product["id"], branch_id=identity["branch_id"])
    product.pop("_id", None)
    return product


@router.get("/products")
async def list_products(identity: Identity = Depends(require_permission("product:read")), db: AsyncDatabase = Depends(get_database), limit: int = 100) -> list[dict[str, Any]]:
    limit = min(max(limit, 1), 500)
    cursor = db.products.find({"shop_id": identity["shop_id"]}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1, "stock_mode": 1, "purity": 1, "reorder_threshold": 1, "version": 1})
    return await cursor.to_list(length=limit)


@router.post("/inventory/items", status_code=status.HTTP_201_CREATED)
async def receive_unique_item(payload: JewelleryItemCreate, identity: Identity = Depends(require_permission("inventory:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    if not identity["branch_id"]:
        raise HTTPException(status_code=409, detail="Select a branch to receive stock")
    product = await db.products.find_one({"id": payload.product_id, "shop_id": identity["shop_id"], "stock_mode": "unique_item"})
    if not product:
        raise HTTPException(status_code=404, detail="Unique-item product not found")
    item = JewelleryItemDocument(shop_id=identity["shop_id"], branch_id=identity["branch_id"], product_id=payload.product_id, serial_number=payload.serial_number, barcode=payload.barcode, gross_weight_g=payload.gross_weight_g, stone_weight_g=payload.stone_weight_g, net_metal_weight_g=payload.net_metal_weight_g)
    now = _now()
    item_doc = item.model_dump()
    item_doc.update({"created_at": now, "updated_at": now})
    movement = {"id": str(uuid4()), "shop_id": identity["shop_id"], "branch_id": identity["branch_id"], "movement_id": str(uuid4()), "operation_id": f"receive:{item.id}", "product_id": payload.product_id, "item_id": item.id, "quantity_delta": 1, "reason": "stock_receipt", "recorded_by": identity["user"]["id"], "created_at": now}
    try:
        async with await db.client.start_session() as mongo_session:
            async with mongo_session.start_transaction():
                await db.jewellery_items.insert_one(item_doc, session=mongo_session)
                await db.inventory_movements.insert_one(movement, session=mongo_session)
                await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="inventory.unique_item_received", entity_type="jewellery_item", entity_id=item.id, branch_id=identity["branch_id"], session=mongo_session)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Serial number or barcode already exists in this shop") from None
    return {"id": item.id, "serial_number": item.serial_number, "barcode": item.barcode, "status": item.status.value}


@router.get("/inventory/scan/{barcode}")
async def scan_barcode(barcode: str, identity: Identity = Depends(require_permission("inventory:read")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    item = await db.jewellery_items.find_one({"shop_id": identity["shop_id"], "barcode": barcode, **({"branch_id": identity["branch_id"]} if identity["branch_id"] else {})}, {"_id": 0})
    if item:
        product = await db.products.find_one({"id": item["product_id"], "shop_id": identity["shop_id"]}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1, "purity": 1})
        return {"type": "unique_item", "item": item, "product": product, "available": item["status"] == "available"}
    product = await db.products.find_one({"shop_id": identity["shop_id"], "$or": [{"sku": barcode}, {"barcode": barcode}]}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1, "stock_mode": 1, "purity": 1})
    if product:
        return {"type": "product", "product": product}
    raise HTTPException(status_code=404, detail="Barcode or SKU not found")


@router.post("/rates", status_code=status.HTTP_201_CREATED)
async def create_rate(payload: RateCreate, identity: Identity = Depends(require_permission("rate:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    try:
        effective_at = datetime.fromisoformat(payload.effective_at.replace("Z", "+00:00"))
        if effective_at.tzinfo is None:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="effective_at must be an ISO-8601 timestamp with timezone") from None
    now = _now()
    rate = {"id": str(uuid4()), "shop_id": identity["shop_id"], "branch_id": identity["branch_id"], "metal": payload.metal, "purity": payload.purity, "rate_paise_per_gram": payload.rate_paise_per_gram, "source": payload.source, "effective_at": effective_at.astimezone(timezone.utc), "is_manual": payload.is_manual, "authorized_by": identity["user"]["id"], "created_at": now, "updated_at": now, "version": 1}
    await db.metal_rates.insert_one(rate)
    await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="rate.created", entity_type="metal_rate", entity_id=rate["id"], branch_id=identity["branch_id"])
    rate.pop("_id", None)
    return rate


@router.get("/rates/current")
async def current_rates(identity: Identity = Depends(require_permission("rate:read")), db: AsyncDatabase = Depends(get_database)) -> list[dict[str, Any]]:
    branch_scope = {"branch_id": {"$in": [None, identity["branch_id"]]}} if identity["branch_id"] else {}
    pipeline = [{"$match": {"shop_id": identity["shop_id"], **branch_scope, "effective_at": {"$lte": _now()}}}, {"$sort": {"branch_id": -1, "effective_at": -1}}, {"$group": {"_id": {"metal": "$metal", "purity": "$purity"}, "rate": {"$first": "$$ROOT"}}}, {"$replaceRoot": {"newRoot": "$rate"}}, {"$project": {"_id": 0, "id": 1, "metal": 1, "purity": 1, "rate_paise_per_gram": 1, "source": 1, "is_manual": 1, "effective_at": 1, "authorized_by": 1}}]
    return await db.metal_rates.aggregate(pipeline).to_list(length=100)


@router.post("/customers", status_code=status.HTTP_201_CREATED)
async def create_customer(payload: CustomerCreate, identity: Identity = Depends(require_permission("customer:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    now = _now()
    customer = {"id": str(uuid4()), "shop_id": identity["shop_id"], "customer_number": uuid4().hex[:12].upper(), "name": payload.name, "phone": payload.phone, "email": payload.email, "communication_consent": payload.communication_consent, "consent_recorded_at": now if payload.communication_consent else None, "created_at": now, "updated_at": now, "version": 1}
    await db.customers.insert_one(customer)
    await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="customer.created", entity_type="customer", entity_id=customer["id"], branch_id=identity["branch_id"])
    customer.pop("_id", None)
    return customer


@router.post("/inventory/adjustments", status_code=status.HTTP_201_CREATED)
async def adjust_inventory(payload: StockAdjustment, identity: Identity = Depends(require_permission("inventory:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, str]:
    if not identity["branch_id"]:
        raise HTTPException(status_code=409, detail="Select a branch before recording stock")
    previous = await db.inventory_movements.find_one({"shop_id": identity["shop_id"], "operation_id": payload.operation_id})
    if previous:
        return {"movement_id": previous["movement_id"], "status": "already_applied"}
    product = await db.products.find_one({"id": payload.product_id, "shop_id": identity["shop_id"]})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product["stock_mode"] == "unique_item" and (payload.item_id is None or abs(payload.quantity_delta) != 1):
        raise HTTPException(status_code=422, detail="Unique jewellery stock adjustments require one item record")
    now, movement_id = _now(), str(uuid4())
    movement = {"id": str(uuid4()), "shop_id": identity["shop_id"], "branch_id": identity["branch_id"], "movement_id": movement_id, "operation_id": payload.operation_id, "product_id": payload.product_id, "item_id": payload.item_id, "quantity_delta": payload.quantity_delta, "reason": payload.reason, "recorded_by": identity["user"]["id"], "created_at": now}
    try:
        async with await db.client.start_session() as mongo_session:
            async with mongo_session.start_transaction():
                if payload.item_id:
                    item = await db.jewellery_items.find_one({"id": payload.item_id, "shop_id": identity["shop_id"], "product_id": payload.product_id}, session=mongo_session)
                    if payload.quantity_delta < 0 and (not item or item.get("status") != "available"):
                        raise HTTPException(status_code=409, detail="Unique item is unavailable")
                    if payload.quantity_delta < 0:
                        new_state = "sold" if payload.reason.casefold() == "sale" else ("damaged" if "damage" in payload.reason.casefold() else "reserved")
                        item_update = await db.jewellery_items.update_one({"id": payload.item_id, "status": "available"}, {"$set": {"status": new_state, "updated_at": now}, "$inc": {"version": 1}}, session=mongo_session)
                        if item_update.modified_count != 1:
                            raise HTTPException(status_code=409, detail="Unique item changed during this adjustment")
                else:
                    balance_scope = {"shop_id": identity["shop_id"], "branch_id": identity["branch_id"], "product_id": payload.product_id}
                    if payload.quantity_delta > 0:
                        await db.inventory_balances.update_one(balance_scope, {"$inc": {"on_hand": payload.quantity_delta}, "$set": {"updated_at": now}, "$setOnInsert": {"id": str(uuid4()), "created_at": now}}, upsert=True, session=mongo_session)
                    else:
                        result = await db.inventory_balances.update_one({**balance_scope, "on_hand": {"$gte": abs(payload.quantity_delta)}}, {"$inc": {"on_hand": payload.quantity_delta}, "$set": {"updated_at": now}}, session=mongo_session)
                        if result.modified_count != 1:
                            raise HTTPException(status_code=409, detail="Insufficient branch stock for this adjustment")
                await db.inventory_movements.insert_one(movement, session=mongo_session)
                await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="inventory.adjusted", entity_type="product", entity_id=payload.product_id, branch_id=identity["branch_id"], reason=payload.reason, session=mongo_session)
    except DuplicateKeyError:
        existing = await db.inventory_movements.find_one({"shop_id": identity["shop_id"], "operation_id": payload.operation_id})
        if existing:
            return {"movement_id": existing["movement_id"], "status": "already_applied"}
        raise HTTPException(status_code=409, detail="Duplicate inventory operation") from None
    return {"movement_id": movement_id, "status": "recorded"}


@router.get("/inventory/balances")
async def inventory_balances(identity: Identity = Depends(require_permission("inventory:read")), db: AsyncDatabase = Depends(get_database)) -> list[dict[str, Any]]:
    if not identity["branch_id"]:
        raise HTTPException(status_code=409, detail="Select a branch to view stock")
    cursor = db.inventory_balances.find({"shop_id": identity["shop_id"], "branch_id": identity["branch_id"]}, {"_id": 0, "product_id": 1, "on_hand": 1, "updated_at": 1})
    return await cursor.to_list(length=1000)


@router.post("/invoices/drafts", status_code=status.HTTP_201_CREATED)
async def create_invoice_draft(payload: InvoiceCreate, identity: Identity = Depends(require_permission("invoice:create")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    if not identity["branch_id"]:
        raise HTTPException(status_code=409, detail="Select a branch before billing")
    existing = await db.invoices.find_one({"shop_id": identity["shop_id"], "operation_id": payload.operation_id}, {"_id": 0})
    if existing:
        return {"id": existing["id"], "draft_reference": existing["invoice_number"], "status": existing["status"], "total_paise": existing["total_paise"], "idempotent_replay": True}
    if payload.amount_paid_paise:
        raise HTTPException(status_code=422, detail="Payments must be recorded through the payment verification workflow")
    lines, subtotal = [], 0
    for source in payload.lines:
        if not await db.products.find_one({"id": source.product_id, "shop_id": identity["shop_id"]}, {"_id": 1}):
            raise HTTPException(status_code=404, detail="A selected product does not belong to this shop")
        if source.item_id:
            item = await db.jewellery_items.find_one({"id": source.item_id, "shop_id": identity["shop_id"], "branch_id": identity["branch_id"], "status": "available"})
            if not item:
                raise HTTPException(status_code=409, detail="A selected unique item is unavailable")
        total = source.taxable_value_paise + source.tax_paise
        lines.append(InvoiceLineSnapshot(product_id=source.product_id, item_id=source.item_id, description=source.description, quantity=source.quantity, gross_weight_g=source.gross_weight_g, net_metal_weight_g=source.net_metal_weight_g, metal_rate_paise_per_gram=source.metal_rate_paise_per_gram, making_charge_paise=source.making_charge_paise, wastage_paise=source.wastage_paise, stone_value_paise=source.stone_value_paise, taxable_value_paise=source.taxable_value_paise, tax_paise=source.tax_paise, total_paise=total))
        subtotal += source.taxable_value_paise
    tax = sum(line.tax_paise for line in lines)
    total = subtotal - payload.discount_paise + tax
    if total < 0:
        raise HTTPException(status_code=422, detail="Discount cannot exceed taxable subtotal")
    now = _now()
    try:
        invoice_number = f"DRAFT-{uuid4().hex[:20].upper()}"
        invoice = InvoiceDocument(shop_id=identity["shop_id"], branch_id=identity["branch_id"], invoice_number=invoice_number, financial_year=payload.financial_year, customer_id=payload.customer_id, operation_id=payload.operation_id, status=InvoiceStatus.DRAFT, lines=lines, subtotal_paise=subtotal, discount_paise=payload.discount_paise, tax_paise=tax, total_paise=total, amount_paid_paise=0, payment_state=PaymentStatus.PENDING_VERIFICATION, created_at=now, updated_at=now)
        # Draft values are proposals supplied by the client: they are not tax-approved,
        # do not reserve/deduct inventory, and cannot receive payments or be printed as final.
        await db.invoices.insert_one(invoice.model_dump())
        await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="invoice.draft_created", entity_type="invoice", entity_id=invoice.id, branch_id=identity["branch_id"])
    except DuplicateKeyError:
        existing = await db.invoices.find_one({"shop_id": identity["shop_id"], "operation_id": payload.operation_id}, {"_id": 0})
        if existing:
            return {"id": existing["id"], "draft_reference": existing["invoice_number"], "status": existing["status"], "total_paise": existing["total_paise"], "idempotent_replay": True}
        raise HTTPException(status_code=409, detail="Draft reference collision; retry with the same operation_id") from None
    return {"id": invoice.id, "draft_reference": invoice_number, "status": invoice.status.value, "total_paise": total, "requires_server_pricing_and_tax_review": True, "idempotent_replay": False}


@router.post("/payments", status_code=status.HTTP_201_CREATED)
async def record_payment(payload: InvoicePayment, identity: Identity = Depends(require_permission("payment:record")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    replay = await db.payments.find_one({"shop_id": identity["shop_id"], "idempotency_key": payload.idempotency_key})
    if replay:
        return {"id": replay["id"], "status": replay["status"], "idempotent_replay": True}
    invoice = await db.invoices.find_one({"id": payload.invoice_id, "shop_id": identity["shop_id"], "branch_id": identity["branch_id"]})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.get("status") != InvoiceStatus.POSTED.value:
        raise HTTPException(status_code=409, detail="Only a server-priced, posted invoice can receive payments")
    if payload.amount_paise > invoice["total_paise"] - invoice["amount_paid_paise"]:
        raise HTTPException(status_code=422, detail="Payment exceeds the remaining invoice balance")
    now = _now()
    verified = payload.method == "cash"
    payment = PaymentDocument(shop_id=identity["shop_id"], branch_id=identity["branch_id"], invoice_id=invoice["id"], operation_id=str(uuid4()), idempotency_key=payload.idempotency_key, method=payload.method, status=PaymentStatus.SUCCEEDED if verified else PaymentStatus.PENDING_VERIFICATION, amount_paise=payload.amount_paise, provider_reference=payload.provider_reference, verified_at=now if verified else None, verified_by=identity["user"]["id"] if verified else None, created_at=now, updated_at=now)
    try:
        async with await db.client.start_session() as mongo_session:
            async with mongo_session.start_transaction():
                await db.payments.insert_one(payment.model_dump(), session=mongo_session)
                # Non-cash collections stay unconfirmed until verified by an authorized reconciliation flow.
                if verified:
                    current = await db.invoices.find_one({"id": invoice["id"], "amount_paid_paise": invoice["amount_paid_paise"]}, session=mongo_session)
                    if not current:
                        raise HTTPException(status_code=409, detail="Invoice changed during payment recording; retry")
                    paid = current["amount_paid_paise"] + payload.amount_paise
                    await db.invoices.update_one({"id": invoice["id"]}, {"$set": {"amount_paid_paise": paid, "payment_state": "succeeded" if paid >= invoice["total_paise"] else "pending", "updated_at": now}, "$inc": {"version": 1}}, session=mongo_session)
                await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="payment.recorded", entity_type="payment", entity_id=payment.id, branch_id=identity["branch_id"], session=mongo_session)
    except DuplicateKeyError:
        replay = await db.payments.find_one({"shop_id": identity["shop_id"], "idempotency_key": payload.idempotency_key})
        if replay:
            return {"id": replay["id"], "status": replay["status"], "idempotent_replay": True}
        raise HTTPException(status_code=409, detail="Payment reference or idempotency key is already used") from None
    return {"id": payment.id, "status": payment.status.value, "amount_paise": payment.amount_paise, "confirmed": verified, "idempotent_replay": False}


@router.post("/pledges", status_code=status.HTTP_201_CREATED)
async def create_pledge(payload: PledgeCreate, identity: Identity = Depends(require_permission("pledge:manage")), db: AsyncDatabase = Depends(get_database)) -> dict[str, Any]:
    if os.getenv("GOLDSETU_ENABLE_PLEDGE_RECORDS", "false").casefold() != "true":
        raise HTTPException(status_code=503, detail="Pledge workflows are disabled until legal, custody, and servicing controls are reviewed")
    if not identity["branch_id"]:
        raise HTTPException(status_code=409, detail="Select a branch before opening a pledge")
    try:
        due_at = datetime.fromisoformat(payload.due_at.replace("Z", "+00:00"))
        if due_at.tzinfo is None or due_at <= _now():
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=422, detail="due_at must be a future ISO-8601 timestamp with timezone") from None
    customer = await db.customers.find_one({"id": payload.customer_id, "shop_id": identity["shop_id"]})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    previous = await db.pledge_accounts.find_one({"shop_id": identity["shop_id"], "operation_id": payload.operation_id})
    if previous:
        return {"id": previous["id"], "account_number": previous["account_number"], "principal_outstanding_paise": previous["principal_outstanding_paise"], "interest_outstanding_paise": previous["interest_outstanding_paise"], "status": previous["status"], "idempotent_replay": True}
    pledge = PledgeAccountDocument(shop_id=identity["shop_id"], branch_id=identity["branch_id"], account_number=payload.account_number, customer_id=payload.customer_id, status="open", principal_disbursed_paise=payload.principal_disbursed_paise, principal_outstanding_paise=payload.principal_disbursed_paise, interest_rate_basis_points=payload.interest_rate_basis_points, interest_method=payload.interest_method, due_at=due_at.astimezone(timezone.utc), custody_reference=payload.custody_reference, created_by=identity["user"]["id"])
    pledge_doc = pledge.model_dump()
    pledge_doc["operation_id"] = payload.operation_id
    try:
        await db.pledge_accounts.insert_one(pledge_doc)
    except DuplicateKeyError:
        previous = await db.pledge_accounts.find_one({"shop_id": identity["shop_id"], "operation_id": payload.operation_id})
        if previous:
            return {"id": previous["id"], "account_number": previous["account_number"], "principal_outstanding_paise": previous["principal_outstanding_paise"], "interest_outstanding_paise": previous["interest_outstanding_paise"], "status": previous["status"], "idempotent_replay": True}
        raise HTTPException(status_code=409, detail="Pledge account number already exists in this branch") from None
    await _audit(db, shop_id=identity["shop_id"], actor_id=identity["user"]["id"], action="pledge.opened", entity_type="pledge_account", entity_id=pledge.id, branch_id=identity["branch_id"])
    return {"id": pledge.id, "account_number": pledge.account_number, "principal_outstanding_paise": pledge.principal_outstanding_paise, "interest_outstanding_paise": 0, "status": pledge.status, "idempotent_replay": False}

