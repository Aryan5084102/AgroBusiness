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


# Owner is handled specially (implicit all-permissions) but also seeded here.
DEFAULT_ROLES: dict[str, RoleSpec] = {
    "owner": {
        "name": "Owner",
        "permissions": ALL_PERMISSION_CODES,
    },
    "administrator": {
        "name": "Administrator",
        "permissions": [
            "product.view",
            "product.create",
            "product.update",
            "inventory.view",
            "purchase.view",
            "purchase.create",
            "sales.create",
            "customer.view",
            "customer.create",
            "report.view",
            "user.manage",
            "settings.manage",
        ],
    },
    "billing_operator": {
        "name": "Billing Operator",
        "permissions": [
            "product.view",
            "inventory.view",
            "sales.create",
            "customer.view",
            "customer.create",
            "payment.receive",
        ],
    },
    "wholesale_salesperson": {
        "name": "Wholesale Salesperson",
        "permissions": [
            "product.view",
            "inventory.view",
            "sales.create",
            "customer.view",
            "customer.create",
            "payment.receive",
            "report.view",
        ],
    },
    "inventory_manager": {
        "name": "Inventory Manager",
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
    "accountant": {
        "name": "Accountant",
        "permissions": [
            "payment.receive",
            "report.view",
            "report.view_profit",
            "customer.view",
        ],
    },
    "service_technician": {
        "name": "Service Technician",
        "permissions": ["service.manage", "inventory.view", "product.view"],
    },
    "auditor": {
        "name": "Auditor",
        "permissions": [
            "product.view",
            "inventory.view",
            "purchase.view",
            "customer.view",
            "report.view",
            "report.view_profit",
            "audit.view",
        ],
    },
}
