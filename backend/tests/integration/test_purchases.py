"""Phase 3 purchase integration tests against real Postgres.

Full flow: create supplier + PO, receive goods (posts stock movements, captures a
batch, computes landed cost), and confirm inventory increased. Also asserts
duplicate supplier-invoice detection and HTTP RBAC on the supplier endpoint.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from app.core.database import get_sessionmaker
from app.core.exceptions import ConflictError
from app.modules.catalogue.models import Category, Product, ProductCategoryKind, Unit
from app.modules.inventory.models import StockBalance, StockMovement
from app.modules.organizations.models import Warehouse
from app.modules.organizations.service import OrganizationProvisioningService
from app.modules.purchases.service import (
    POLineInput,
    PurchaseService,
    ReceiptCharges,
    ReceiptLineInput,
)
from app.modules.suppliers.models import Supplier
from httpx import AsyncClient
from sqlalchemy import func, select

pytestmark = pytest.mark.usefixtures("db_ready")

TODAY = date(2026, 7, 11)


async def _setup() -> dict[str, uuid.UUID]:
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Purchase Co",
            owner_email="owner@pur.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        org_id = prov.organization.id
        unit = Unit(organization_id=org_id, code="pcs", name="Pieces")
        cat = Category(
            organization_id=org_id,
            name="Seeds",
            code="SEED",
            kind=ProductCategoryKind.SEED,
        )
        session.add_all([unit, cat])
        await session.flush()
        product = Product(
            organization_id=org_id,
            category_id=cat.id,
            base_unit_id=unit.id,
            name="Hybrid Maize Seed 1kg",
            sku="SEED-MZ-1",
            tracks_batches=True,
            tracks_expiry=True,
        )
        supplier = Supplier(organization_id=org_id, code="SUP1", name="AgriSeeds Pvt")
        wh = Warehouse(organization_id=org_id, branch_id=prov.branch.id, name="Main", code="WH1")
        session.add_all([product, supplier, wh])
        await session.flush()
        ids = {
            "org": org_id,
            "branch": prov.branch.id,
            "product": product.id,
            "supplier": supplier.id,
            "warehouse": wh.id,
        }
        await session.commit()
        return ids


async def test_po_to_grn_increases_stock_with_landed_cost() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = PurchaseService(session)
        po = await service.create_purchase_order(
            organization_id=ids["org"],
            supplier_id=ids["supplier"],
            branch_id=ids["branch"],
            order_date=TODAY,
            lines=[
                POLineInput(
                    product_id=ids["product"],
                    ordered_base_quantity=Decimal("100"),
                    unit_rate=Decimal("50"),
                )
            ],
        )
        # Branch-scoped sequences carry the branch code so numbers stay unique
        # across the organization: "MAIN-PO-00001".
        assert po.po_number.endswith("PO-00001")
        assert "MAIN" in po.po_number
        await session.commit()
        po_id = po.id

    # Fetch the PO item id for linking the receipt.
    async with factory() as session:
        from app.modules.purchases.models import PurchaseOrderItem

        item = (
            (
                await session.execute(
                    select(PurchaseOrderItem).where(PurchaseOrderItem.purchase_order_id == po_id)
                )
            )
            .scalars()
            .first()
        )
        assert item is not None
        po_item_id = item.id

    async with factory() as session:
        service = PurchaseService(session)
        result = await service.receive_goods(
            organization_id=ids["org"],
            warehouse_id=ids["warehouse"],
            supplier_id=ids["supplier"],
            branch_id=ids["branch"],
            purchase_order_id=po_id,
            receipt_date=TODAY,
            charges=ReceiptCharges(freight=Decimal("500")),
            lines=[
                ReceiptLineInput(
                    purchase_order_item_id=po_item_id,
                    product_id=ids["product"],
                    received_base_quantity=Decimal("100"),
                    unit_rate=Decimal("50"),
                    batch_number="MZ-B1",
                    expiry_date=date(2027, 6, 30),
                )
            ],
        )
        await session.commit()
        # Landed cost = (100*50 + 500 freight) / 100 units = 55.00
        assert result.landed_unit_costs[str(ids["product"])] == Decimal("55.0000")

    async with factory() as session:
        # Stock ledger and balance both reflect +100.
        ledger = await session.execute(
            select(func.coalesce(func.sum(StockMovement.base_quantity), 0)).where(
                StockMovement.product_id == ids["product"]
            )
        )
        assert Decimal(str(ledger.scalar())) == Decimal("100.000")
        bal = await session.execute(
            select(func.coalesce(func.sum(StockBalance.on_hand), 0)).where(
                StockBalance.product_id == ids["product"]
            )
        )
        assert Decimal(str(bal.scalar())) == Decimal("100.000")

        # PO is now fully received.
        from app.modules.purchases.models import PurchaseOrder, PurchaseOrderStatus

        po = await session.get(PurchaseOrder, po_id)
        assert po is not None
        assert po.status == PurchaseOrderStatus.RECEIVED


async def test_duplicate_supplier_invoice_is_rejected() -> None:
    ids = await _setup()
    factory = get_sessionmaker()
    async with factory() as session:
        service = PurchaseService(session)
        await service.record_purchase_invoice(
            organization_id=ids["org"],
            supplier_id=ids["supplier"],
            supplier_invoice_number="INV-777",
            invoice_date=TODAY,
            goods_value=Decimal("5000"),
            tax_amount=Decimal("250"),
        )
        await session.commit()

    async with factory() as session:
        service = PurchaseService(session)
        with pytest.raises(ConflictError) as exc:
            await service.record_purchase_invoice(
                organization_id=ids["org"],
                supplier_id=ids["supplier"],
                supplier_invoice_number="INV-777",
                invoice_date=TODAY,
                goods_value=Decimal("5000"),
                tax_amount=Decimal("250"),
            )
        assert exc.value.code == "duplicate_supplier_invoice"


async def test_supplier_endpoint_requires_permission(api: AsyncClient) -> None:
    # Provision an org with an owner and a billing operator (no purchase perms).
    factory = get_sessionmaker()
    async with factory() as session:
        prov = await OrganizationProvisioningService(session).provision(
            org_name="Perm Co",
            owner_email="owner@perm.local",
            owner_password="OwnerPass123",
            owner_name="Owner",
        )
        await OrganizationProvisioningService(session).create_user(
            organization_id=prov.organization.id,
            email="billing@perm.local",
            password="BillingPass1",
            full_name="Billing",
            role_code="counter_sales",
            branch_id=prov.branch.id,
        )
        await session.commit()

    # Counter staff lack purchase.view -> 403.
    await api.post(
        "/api/v1/auth/login",
        json={"email": "billing@perm.local", "password": "BillingPass1"},
    )
    resp = await api.get("/api/v1/suppliers")
    assert resp.status_code == 403

    # Owner can list suppliers.
    await api.post("/api/v1/auth/logout")
    await api.post(
        "/api/v1/auth/login",
        json={"email": "owner@perm.local", "password": "OwnerPass123"},
    )
    resp = await api.get("/api/v1/suppliers")
    assert resp.status_code == 200
