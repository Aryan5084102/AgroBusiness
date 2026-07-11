"""Import every ORM model so ``Base.metadata`` is complete.

Imported by Alembic's env and by test schema creation. Adding a new module's
models means adding an import here.
"""

from app.modules.accounting import models as accounting_models
from app.modules.audit import models as audit_models
from app.modules.auth import models as auth_models
from app.modules.catalogue import models as catalogue_models
from app.modules.customers import models as customer_models
from app.modules.idempotency import models as idempotency_models
from app.modules.inventory import models as inventory_models
from app.modules.numbering import models as numbering_models
from app.modules.organizations import models as org_models
from app.modules.payments import models as payment_models
from app.modules.purchases import models as purchase_models
from app.modules.sales import models as sales_models
from app.modules.sales import order_models as sales_order_models
from app.modules.service_jobs import models as service_job_models
from app.modules.suppliers import models as supplier_models
from app.modules.users import models as user_models
from app.modules.warranties import models as warranty_models

__all__ = [
    "accounting_models",
    "audit_models",
    "auth_models",
    "catalogue_models",
    "customer_models",
    "idempotency_models",
    "inventory_models",
    "numbering_models",
    "org_models",
    "payment_models",
    "purchase_models",
    "sales_models",
    "sales_order_models",
    "service_job_models",
    "supplier_models",
    "user_models",
    "warranty_models",
]
