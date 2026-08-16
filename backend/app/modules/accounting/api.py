"""Accounting endpoints: trial balance, journal register and customer ledger.

Ledger views are gated by ``report.view_profit`` (owner, accountant, auditor);
the per-customer statement only needs ``customer.view`` so sales staff can
explain a dealer's balance without seeing company-wide books.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.context import CurrentUser
from app.core.deps import db_session, require_permission
from app.core.exceptions import NotFoundError
from app.modules.accounting.models import (
    Account,
    AccountType,
    JournalEntry,
    JournalEntryLine,
)
from app.modules.customers.models import Customer
from app.modules.payments.models import Payment, PaymentDirection
from app.modules.sales.models import SalesInvoice

router = APIRouter(tags=["accounting"])


# --- Trial balance ----------------------------------------------------------
class TrialBalanceRow(BaseModel):
    account_code: str
    account_name: str
    account_type: AccountType
    debit: Decimal
    credit: Decimal
    balance: Decimal


class TrialBalanceResponse(BaseModel):
    rows: list[TrialBalanceRow]
    total_debit: Decimal
    total_credit: Decimal
    is_balanced: bool


@router.get("/trial-balance", response_model=TrialBalanceResponse)
async def trial_balance(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: CurrentUser = Depends(require_permission("report.view_profit")),
    session: AsyncSession = Depends(db_session),
) -> TrialBalanceResponse:
    stmt = (
        select(
            Account.code,
            Account.name,
            Account.type,
            func.coalesce(func.sum(JournalEntryLine.debit), 0),
            func.coalesce(func.sum(JournalEntryLine.credit), 0),
        )
        .join(JournalEntryLine, JournalEntryLine.account_id == Account.id)
        .join(JournalEntry, JournalEntry.id == JournalEntryLine.journal_entry_id)
        .where(Account.organization_id == user.organization_id)
        .group_by(Account.code, Account.name, Account.type)
        .order_by(Account.code)
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)

    rows: list[TrialBalanceRow] = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")
    for code, name, acc_type, debit, credit in (await session.execute(stmt)).all():
        debit_dec = Money(Decimal(str(debit)))
        credit_dec = Money(Decimal(str(credit)))
        total_debit = Money(total_debit + debit_dec)
        total_credit = Money(total_credit + credit_dec)
        rows.append(
            TrialBalanceRow(
                account_code=code,
                account_name=name,
                account_type=acc_type,
                debit=debit_dec,
                credit=credit_dec,
                balance=Money(debit_dec - credit_dec),
            )
        )
    return TrialBalanceResponse(
        rows=rows,
        total_debit=total_debit,
        total_credit=total_credit,
        is_balanced=total_debit == total_credit,
    )


# --- Journal register -------------------------------------------------------
class JournalLineOut(BaseModel):
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal


class JournalEntryOut(BaseModel):
    id: uuid.UUID
    entry_date: date
    narration: str | None
    source_document_type: str | None
    source_document_id: uuid.UUID | None
    total: Decimal
    lines: list[JournalLineOut]


class JournalPage(BaseModel):
    items: list[JournalEntryOut]
    total: int
    limit: int
    offset: int


@router.get("/journals", response_model=JournalPage)
async def list_journals(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(require_permission("report.view_profit")),
    session: AsyncSession = Depends(db_session),
) -> JournalPage:
    base = select(JournalEntry).where(JournalEntry.organization_id == user.organization_id)
    if date_from is not None:
        base = base.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        base = base.where(JournalEntry.entry_date <= date_to)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    entries = list(
        (
            await session.execute(
                base.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    if not entries:
        return JournalPage(items=[], total=int(total or 0), limit=limit, offset=offset)

    line_rows = await session.execute(
        select(JournalEntryLine, Account.code, Account.name)
        .join(Account, Account.id == JournalEntryLine.account_id)
        .where(JournalEntryLine.journal_entry_id.in_([e.id for e in entries]))
    )
    by_entry: dict[uuid.UUID, list[JournalLineOut]] = {}
    totals: dict[uuid.UUID, Decimal] = {}
    for line, code, name in line_rows.all():
        by_entry.setdefault(line.journal_entry_id, []).append(
            JournalLineOut(
                account_code=code, account_name=name, debit=line.debit, credit=line.credit
            )
        )
        totals[line.journal_entry_id] = Money(
            totals.get(line.journal_entry_id, Decimal("0")) + line.debit
        )

    return JournalPage(
        items=[
            JournalEntryOut(
                id=e.id,
                entry_date=e.entry_date,
                narration=e.narration,
                source_document_type=e.source_document_type,
                source_document_id=e.source_document_id,
                total=totals.get(e.id, Decimal("0.00")),
                lines=by_entry.get(e.id, []),
            )
            for e in entries
        ],
        total=int(total or 0),
        limit=limit,
        offset=offset,
    )


# --- Customer statement -----------------------------------------------------
class LedgerRow(BaseModel):
    entry_date: date
    kind: str
    reference: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


class CustomerLedgerResponse(BaseModel):
    customer_id: uuid.UUID
    customer_name: str
    opening_balance: Decimal
    rows: list[LedgerRow]
    closing_balance: Decimal
    credit_limit: Decimal
    available_credit: Decimal


@router.get("/customers/{customer_id}/ledger", response_model=CustomerLedgerResponse)
async def customer_ledger(
    customer_id: uuid.UUID,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    user: CurrentUser = Depends(require_permission("customer.view")),
    session: AsyncSession = Depends(db_session),
) -> CustomerLedgerResponse:
    """Chronological statement: invoices debit the customer, payments credit them."""
    customer = await session.get(Customer, customer_id)
    if customer is None or customer.organization_id != user.organization_id:
        raise NotFoundError("Unknown customer.")

    invoice_stmt = select(SalesInvoice).where(
        SalesInvoice.organization_id == user.organization_id,
        SalesInvoice.customer_id == customer_id,
    )
    payment_stmt = select(Payment).where(
        Payment.organization_id == user.organization_id,
        Payment.customer_id == customer_id,
        Payment.direction == PaymentDirection.INBOUND,
    )
    if date_from is not None:
        invoice_stmt = invoice_stmt.where(SalesInvoice.invoice_date >= date_from)
        payment_stmt = payment_stmt.where(func.date(Payment.received_at) >= date_from)
    if date_to is not None:
        invoice_stmt = invoice_stmt.where(SalesInvoice.invoice_date <= date_to)
        payment_stmt = payment_stmt.where(func.date(Payment.received_at) <= date_to)

    invoices = list((await session.execute(invoice_stmt)).scalars().all())
    payments = list((await session.execute(payment_stmt)).scalars().all())

    events: list[tuple[date, str, str, Decimal, Decimal]] = []
    for inv in invoices:
        events.append(
            (inv.invoice_date, "invoice", inv.invoice_number, inv.grand_total, Decimal("0.00"))
        )
    for pay in payments:
        events.append(
            (
                pay.received_at.date(),
                "payment",
                pay.reference or pay.method.value.upper(),
                Decimal("0.00"),
                pay.amount,
            )
        )
    events.sort(key=lambda e: (e[0], e[1]))

    balance = customer.opening_balance
    rows: list[LedgerRow] = []
    for entry_date, kind, reference, debit, credit in events:
        balance = Money(balance + debit - credit)
        rows.append(
            LedgerRow(
                entry_date=entry_date,
                kind=kind,
                reference=reference,
                debit=Money(debit),
                credit=Money(credit),
                running_balance=balance,
            )
        )

    return CustomerLedgerResponse(
        customer_id=customer.id,
        customer_name=customer.name,
        opening_balance=Money(customer.opening_balance),
        rows=rows,
        closing_balance=balance,
        credit_limit=customer.credit_limit,
        available_credit=Money(customer.credit_limit - balance),
    )
