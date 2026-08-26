"""Central permission catalogue and default role → permission mapping.

Permissions are action-level (``sales.finalize``) and enforced on every API
route via :func:`require_permission`. Roles are seeded from ``DEFAULT_ROLES``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


@dataclass(frozen=True)
class PermissionDef:
    code: str
    category: str
    description: str


# --- Catalogue --------------------------------------------------------------
PERMISSIONS: list[PermissionDef] = [
    PermissionDef("product.view", "catalogue", "View products"),
    PermissionDef("product.create", "catalogue", "Create products"),
    PermissionDef("product.update", "catalogue", "Update products"),
    PermissionDef("pricing.view_cost", "pricing", "View product cost/margin"),
    PermissionDef("pricing.override", "pricing", "Override price beyond limits"),
    PermissionDef("inventory.view", "inventory", "View stock"),
    PermissionDef("inventory.adjust", "inventory", "Adjust stock"),
    PermissionDef("stock.transfer", "inventory", "Transfer stock between warehouses"),
    PermissionDef("purchase.view", "purchases", "View purchases"),
    PermissionDef("purchase.create", "purchases", "Create purchase orders/receipts"),
    PermissionDef("sales.create", "sales", "Create sales/invoices"),
    PermissionDef("sales.finalize", "sales", "Finalize invoices"),
    PermissionDef("sales.cancel", "sales", "Cancel invoices"),
    PermissionDef("customer.view", "crm", "View customers"),
    PermissionDef("customer.create", "crm", "Create customers"),
    PermissionDef("payment.receive", "payments", "Receive payments"),
    PermissionDef("report.view", "reports", "View operational reports"),
    PermissionDef("report.view_profit", "reports", "View profit reports"),
    PermissionDef("service.manage", "service", "Manage repair jobs"),
    PermissionDef("user.manage", "admin", "Manage users and roles"),
    PermissionDef("settings.manage", "admin", "Change organization settings"),
    PermissionDef("audit.view", "admin", "View audit logs"),
]

ALL_PERMISSION_CODES: list[str] = [p.code for p in PERMISSIONS]


# --- Default roles ----------------------------------------------------------
class RoleSpec(TypedDict):
    name: str
    permissions: list[str]


# The shop runs on three roles: the owner, whoever is on the counter, and
# whoever keeps the godown. Everything the owner does alone — books, profit,
# cost price, users, settings, the audit trail — stays with the owner, so no
# staff role can see a margin or change a setting.
#
# Owner is handled specially (implicit all-permissions) but also seeded here.
DEFAULT_ROLES: dict[str, RoleSpec] = {
    "owner": {
        "name": "Owner",
        "permissions": ALL_PERMISSION_CODES,
    },
    # One counter role covers both halves of the shop: walk-in retail billing
    # and dealer/wholesale orders. `sales.finalize` is included so the counter
    # can dispatch a wholesale order end-to-end without the owner; revoke it
    # from this role if dispatch should stay an owner decision.
    "counter_sales": {
        "name": "Counter / Sales",
        "permissions": [
            "product.view",
            "inventory.view",
            "sales.create",
            "sales.finalize",
            "customer.view",
            "customer.create",
            "payment.receive",
        ],
    },
    # Godown side: what comes in, what is on hand, what is about to expire.
    # Deliberately no sales and no payments — stock and cash stay separate.
    "store_inventory": {
        "name": "Store / Inventory",
        "permissions": [
            "product.view",
            "product.create",
            "product.update",
            "inventory.view",
            "inventory.adjust",
            "stock.transfer",
            "purchase.view",
            "purchase.create",
        ],
    },
}
