"""phase9 collapse roles to three

Collapses the original eight seeded roles down to the three a single-owner
agri-input shop actually staffs: Owner, Counter / Sales, Store / Inventory.

``DEFAULT_ROLES`` is only applied when an organization is provisioned, so every
database created before this migration still carries the old eight. This
migration converges them:

* ``billing_operator`` and ``inventory_manager`` are *renamed* in place to
  ``counter_sales`` / ``store_inventory``, so their users keep working.
* Missing roles are created for any organization that lacks them, and the
  permission set of all three is re-synced to ``DEFAULT_ROLES``.
* The five retired roles are deleted. Their users are deliberately left with
  **no role** rather than being auto-promoted into a surviving one — a
  migration must never hand somebody a permission they did not have. They can
  still sign in and land on the dashboard; the owner re-assigns them from
  Settings → Users.
* Every open session is revoked, because the access token carries a baked-in
  ``perms`` claim (see ``core/deps.py``) and would otherwise keep granting the
  old permissions until it expired.

Irreversible in the strict sense: ``downgrade()`` restores the eight role rows
and their permissions, but the user→role assignments deleted here are gone.

Revision ID: c9f1a70b34d2
Revises: e163dffac3e7
Create Date: 2026-08-25 10:15:00.000000
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9f1a70b34d2"
down_revision: str | None = "e163dffac3e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Renames rather than drop+create, so existing staff keep their assignment.
RENAMES: dict[str, tuple[str, str]] = {
    "billing_operator": ("counter_sales", "Counter / Sales"),
    "inventory_manager": ("store_inventory", "Store / Inventory"),
}

RETIRED = [
    "administrator",
    "billing_operator",
    "wholesale_salesperson",
    "inventory_manager",
    "accountant",
    "service_technician",
    "auditor",
]


def _role_specs(bind: sa.engine.Connection) -> dict[str, tuple[str, list[str]]]:
    """The role set this revision installs.

    Spelled out here rather than imported from ``app.core.permissions``: a
    migration describes one fixed point in history, so it must not shift when
    that module is edited again later. Owner is the sole exception — it means
    "everything", so its grants are read from the catalogue as it stands.
    """
    owner_perms = [row[0] for row in bind.execute(sa.text("SELECT code FROM permissions")).all()]
    return {
        "owner": ("Owner", owner_perms),
        "counter_sales": (
            "Counter / Sales",
            [
                "product.view",
                "inventory.view",
                "sales.create",
                "sales.finalize",
                "customer.view",
                "customer.create",
                "payment.receive",
            ],
        ),
        "store_inventory": (
            "Store / Inventory",
            [
                "product.view",
                "product.create",
                "product.update",
                "inventory.view",
                "inventory.adjust",
                "stock.transfer",
                "purchase.view",
                "purchase.create",
            ],
        ),
    }


def upgrade() -> None:
    bind = op.get_bind()
    specs = _role_specs(bind)

    # 1. Rename the two roles that survive under a new name — but only where the
    #    new code is free, or the org would violate uq_role_code.
    for old_code, (new_code, new_name) in RENAMES.items():
        bind.execute(
            sa.text(
                """
                UPDATE roles r
                   SET code = :new_code, name = :new_name, updated_at = now()
                 WHERE r.code = :old_code
                   AND NOT EXISTS (
                       SELECT 1 FROM roles other
                        WHERE other.organization_id = r.organization_id
                          AND other.code = :new_code
                   )
                """
            ),
            {"old_code": old_code, "new_code": new_code, "new_name": new_name},
        )

    # 2. Drop what is left of the retired roles. Assignments go with them; the
    #    owner re-assigns those people deliberately.
    retired_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM roles WHERE code = ANY(:codes)"), {"codes": RETIRED}
        ).fetchall()
    ]
    if retired_ids:
        for table in ("user_roles", "role_permissions"):
            bind.execute(
                sa.text(f"DELETE FROM {table} WHERE role_id = ANY(:ids)"), {"ids": retired_ids}
            )
        bind.execute(sa.text("DELETE FROM roles WHERE id = ANY(:ids)"), {"ids": retired_ids})

    # 3. Every org gets all three roles, even one provisioned mid-upgrade.
    org_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM organizations")).fetchall()]
    for org_id in org_ids:
        for code, (name, _perms) in specs.items():
            exists = bind.execute(
                sa.text("SELECT id FROM roles WHERE organization_id = :org AND code = :code"),
                {"org": org_id, "code": code},
            ).first()
            if exists is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO roles (id, organization_id, name, code, is_system,
                                           created_at, updated_at)
                        VALUES (:id, :org, :name, :code, true, now(), now())
                        """
                    ),
                    {"id": uuid.uuid4(), "org": org_id, "name": name, "code": code},
                )

    _sync_permissions(bind, specs)
    _revoke_all_sessions(bind)


def _sync_permissions(bind: sa.engine.Connection, specs: dict[str, tuple[str, list[str]]]) -> None:
    """Make every surviving role's grants match the catalogue exactly.

    Renamed roles carry their old grants, so this both adds what the new role
    needs and strips what it should no longer hold.
    """
    perm_ids = {
        code: pid for pid, code in bind.execute(sa.text("SELECT id, code FROM permissions")).all()
    }
    for code, (_name, perms) in specs.items():
        roles = bind.execute(
            sa.text("SELECT id FROM roles WHERE code = :code"), {"code": code}
        ).fetchall()
        for (role_id,) in roles:
            bind.execute(
                sa.text("DELETE FROM role_permissions WHERE role_id = :rid"), {"rid": role_id}
            )
            for perm_code in perms:
                pid = perm_ids.get(perm_code)
                if pid is None:  # catalogue entry not seeded yet; nothing to grant
                    continue
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO role_permissions (id, role_id, permission_id)
                        VALUES (:id, :rid, :pid)
                        """
                    ),
                    {"id": uuid.uuid4(), "rid": role_id, "pid": pid},
                )


def _revoke_all_sessions(bind: sa.engine.Connection) -> None:
    """Force a fresh sign-in so nobody keeps a token minted under the old roles."""
    bind.execute(sa.text("UPDATE sessions SET revoked_at = now() WHERE revoked_at IS NULL"))
    bind.execute(sa.text("UPDATE refresh_tokens SET revoked_at = now() WHERE revoked_at IS NULL"))


def downgrade() -> None:
    """Recreate the eight legacy roles. User assignments are NOT restored."""
    legacy: dict[str, tuple[str, list[str]]] = {
        "owner": ("Owner", []),  # filled below from the catalogue
        "administrator": (
            "Administrator",
            [
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
        ),
        "billing_operator": (
            "Billing Operator",
            [
                "product.view",
                "inventory.view",
                "sales.create",
                "customer.view",
                "customer.create",
                "payment.receive",
            ],
        ),
        "wholesale_salesperson": (
            "Wholesale Salesperson",
            [
                "product.view",
                "inventory.view",
                "sales.create",
                "customer.view",
                "customer.create",
                "payment.receive",
                "report.view",
            ],
        ),
        "inventory_manager": (
            "Inventory Manager",
            [
                "product.view",
                "product.create",
                "product.update",
                "inventory.view",
                "inventory.adjust",
                "stock.transfer",
                "purchase.view",
                "purchase.create",
            ],
        ),
        "accountant": (
            "Accountant",
            ["payment.receive", "report.view", "report.view_profit", "customer.view"],
        ),
        "service_technician": (
            "Service Technician",
            ["service.manage", "inventory.view", "product.view"],
        ),
        "auditor": (
            "Auditor",
            [
                "product.view",
                "inventory.view",
                "purchase.view",
                "customer.view",
                "report.view",
                "report.view_profit",
                "audit.view",
            ],
        ),
    }

    bind = op.get_bind()
    all_codes = [row[0] for row in bind.execute(sa.text("SELECT code FROM permissions")).fetchall()]
    legacy["owner"] = ("Owner", all_codes)

    # Rename the two survivors back before creating the rest, so codes stay free.
    for old_code, (new_code, _new_name) in RENAMES.items():
        legacy_name = legacy[old_code][0]
        bind.execute(
            sa.text(
                """
                UPDATE roles r
                   SET code = :old_code, name = :old_name, updated_at = now()
                 WHERE r.code = :new_code
                   AND NOT EXISTS (
                       SELECT 1 FROM roles other
                        WHERE other.organization_id = r.organization_id
                          AND other.code = :old_code
                   )
                """
            ),
            {"old_code": old_code, "old_name": legacy_name, "new_code": new_code},
        )

    # Drop whatever remains of the three-role set (owner is recreated below).
    stale_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM roles WHERE code = ANY(:codes)"),
            {"codes": ["counter_sales", "store_inventory"]},
        ).fetchall()
    ]
    if stale_ids:
        for table in ("user_roles", "role_permissions"):
            bind.execute(
                sa.text(f"DELETE FROM {table} WHERE role_id = ANY(:ids)"), {"ids": stale_ids}
            )
        bind.execute(sa.text("DELETE FROM roles WHERE id = ANY(:ids)"), {"ids": stale_ids})

    org_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM organizations")).fetchall()]
    for org_id in org_ids:
        for code, (name, _perms) in legacy.items():
            exists = bind.execute(
                sa.text("SELECT id FROM roles WHERE organization_id = :org AND code = :code"),
                {"org": org_id, "code": code},
            ).first()
            if exists is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO roles (id, organization_id, name, code, is_system,
                                           created_at, updated_at)
                        VALUES (:id, :org, :name, :code, true, now(), now())
                        """
                    ),
                    {"id": uuid.uuid4(), "org": org_id, "name": name, "code": code},
                )

    _sync_permissions(bind, legacy)
    _revoke_all_sessions(bind)
