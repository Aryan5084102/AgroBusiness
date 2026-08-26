'use client';

import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Field';
import { formatCurrency } from '@/lib/formatting/currency';
import type { Customer } from '@/features/customers/api';
import type { CustomerDraft } from './useCounterCustomer';
import styles from './PosScreen.module.scss';

interface CustomerCardProps {
  draft: CustomerDraft;
  onChange: (field: keyof CustomerDraft, value: string) => void;
  /** The customer already on file for this mobile number, once one is found. */
  known: Customer | null;
  isLooking: boolean;
  errors: Partial<Record<keyof CustomerDraft, string>>;
}

/**
 * Who the bill is for — the first thing the counter fills in.
 *
 * Name and mobile are what the invoice prints and what a khata is kept under,
 * so both are required; the address is optional because most walk-ins are known
 * by their village alone. Typing a mobile that is already on file recognises
 * the customer instead of opening a second account for them.
 */
export function CustomerFields({
  draft,
  onChange,
  known,
  isLooking,
  errors,
}: CustomerCardProps) {
  const typedName = draft.name.trim();
  const knownUnderAnotherName =
    known !== null && typedName !== '' && known.name.trim() !== typedName;

  return (
    <div className={styles.customerBlock}>
      <div className={styles.customerRow}>
        <Input
          label="Customer name"
          required
          autoComplete="off"
          placeholder="e.g. Ramesh Patil"
          value={draft.name}
          error={errors.name}
          onChange={(event) => onChange('name', event.target.value)}
        />
        <Input
          label="Mobile number"
          required
          type="tel"
          inputMode="numeric"
          autoComplete="off"
          placeholder="10-digit number"
          maxLength={15}
          value={draft.phone}
          error={errors.phone}
          hint={isLooking ? 'Checking if they are on file…' : undefined}
          onChange={(event) => onChange('phone', event.target.value)}
        />
        <Input
          label="Address"
          autoComplete="off"
          placeholder="Village, taluka"
          value={draft.address}
          error={errors.address}
          onChange={(event) => onChange('address', event.target.value)}
        />
      </div>

      {known ? (
        <p className={styles.knownCustomer}>
          <Badge tone="success" dot>
            On file
          </Badge>
          <span>
            {knownUnderAnotherName
              ? `This number is saved as ${known.name}. The bill will use that name.`
              : `${known.name} has bought here before.`}
            {Number(known.outstanding) > 0
              ? ` ${formatCurrency(known.outstanding)} is still open on their khata.`
              : ''}
          </span>
        </p>
      ) : null}
    </div>
  );
}
