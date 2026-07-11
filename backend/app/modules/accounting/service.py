"""Accounting service: standard chart of accounts + balanced journal posting."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.money import Money
from app.core.exceptions import BusinessRuleError
from app.modules.accounting.models import (
    Account,
    AccountType,
    JournalEntry,
    JournalEntryLine,
)

# Standard accounts seeded per organization. code -> (name, type).
STANDARD_ACCOUNTS: dict[str, tuple[str, AccountType]] = {
    "CASH": ("Cash", AccountType.ASSET),
    "BANK": ("Bank", AccountType.ASSET),
    "UPI": ("UPI Clearing", AccountType.ASSET),
    "CARD": ("Card Clearing", AccountType.ASSET),
    "AR": ("Accounts Receivable", AccountType.ASSET),
    "AP": ("Accounts Payable", AccountType.LIABILITY),
    "SALES": ("Sales", AccountType.INCOME),
    "GST_OUTPUT": ("GST Output (payable)", AccountType.LIABILITY),
    "GST_INPUT": ("GST Input (credit)", AccountType.ASSET),
    "PURCHASES": ("Purchases", AccountType.EXPENSE),
}

# Map a payment method to the debit account code.
PAYMENT_METHOD_ACCOUNT = {
    "cash": "CASH",
    "upi": "UPI",
    "card": "CARD",
    "bank_transfer": "BANK",
    "cheque": "BANK",
}


@dataclass
class JournalLine:
    account_code: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")


class AccountingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_accounts(self, organization_id: uuid.UUID) -> dict[str, Account]:
        """Idempotently ensure the standard chart of accounts exists."""
        existing = {
            a.code: a
            for a in (
                await self._session.execute(
                    select(Account).where(Account.organization_id == organization_id)
                )
            )
            .scalars()
            .all()
        }
        for code, (name, acc_type) in STANDARD_ACCOUNTS.items():
            if code not in existing:
                acct = Account(organization_id=organization_id, code=code, name=name, type=acc_type)
                self._session.add(acct)
                existing[code] = acct
        await self._session.flush()
        return existing

    async def post(
        self,
        *,
        organization_id: uuid.UUID,
        entry_date: date,
        lines: list[JournalLine],
        narration: str | None = None,
        branch_id: uuid.UUID | None = None,
        source_document_type: str | None = None,
        source_document_id: uuid.UUID | None = None,
        created_by: uuid.UUID | None = None,
    ) -> JournalEntry:
        """Post a balanced journal entry. Raises if debits != credits."""
        if len(lines) < 2:
            raise BusinessRuleError("A journal entry needs at least two lines.")
        total_debit = Money(sum((line.debit for line in lines), Decimal("0")))
        total_credit = Money(sum((line.credit for line in lines), Decimal("0")))
        if total_debit != total_credit:
            raise BusinessRuleError(
                f"Journal entry is unbalanced: debit {total_debit} != credit " f"{total_credit}.",
                code="unbalanced_journal",
            )
        if total_debit == 0:
            raise BusinessRuleError("Journal entry total cannot be zero.")

        accounts = await self.ensure_accounts(organization_id)
        entry = JournalEntry(
            organization_id=organization_id,
            branch_id=branch_id,
            entry_date=entry_date,
            narration=narration,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            created_by=created_by,
        )
        self._session.add(entry)
        await self._session.flush()

        for line in lines:
            account = accounts.get(line.account_code)
            if account is None:
                raise BusinessRuleError(f"Unknown account: {line.account_code}")
            self._session.add(
                JournalEntryLine(
                    journal_entry_id=entry.id,
                    account_id=account.id,
                    debit=Money(line.debit),
                    credit=Money(line.credit),
                )
            )
        await self._session.flush()
        return entry
