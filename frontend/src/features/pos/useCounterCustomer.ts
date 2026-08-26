'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { createCustomer, fetchCustomers, type Customer } from '@/features/customers/api';
import { ApiError } from '@/lib/api/client';

export interface CustomerDraft {
  name: string;
  phone: string;
  address: string;
}

export const EMPTY_DRAFT: CustomerDraft = { name: '', phone: '', address: '' };

/**
 * Reduces whatever was typed to the ten digits that identify a customer.
 *
 * Counters type numbers every way there is — `+91 98765 43210`, `098765-43210` —
 * and all of them are the same person, so the last ten digits are what a lookup
 * and a customer code are built from.
 */
export function normalisePhone(value: string): string {
  return value.replace(/\D+/g, '').slice(-10);
}

export function isCompletePhone(value: string): boolean {
  return normalisePhone(value).length === 10;
}

/**
 * The customer behind a phone number, if the shop already has one on file.
 *
 * Runs as soon as ten digits are in, so a returning customer's name and address
 * fill themselves in and the sale attaches to their existing khata rather than
 * opening a second account for them.
 */
export function useCustomerByPhone(phone: string) {
  const digits = normalisePhone(phone);
  return useQuery({
    queryKey: ['customers', 'by-phone', digits],
    queryFn: async (): Promise<Customer | null> => {
      const matches = await fetchCustomers(digits);
      return matches.find((c) => normalisePhone(c.phone ?? '') === digits) ?? null;
    },
    enabled: digits.length === 10,
    staleTime: 60_000,
  });
}

/** The code a counter-created customer gets: stable, and derived from the phone. */
function codeFor(phone: string): string {
  return `RC-${normalisePhone(phone)}`;
}

/**
 * Turns the details typed at the counter into a saved customer.
 *
 * Every bill names its buyer, so the counter's name/mobile/address has to become
 * a real customer row — that is what puts the details on the invoice, keeps a
 * khata attachable, and means the second visit is recognised. An existing match
 * is reused; only a genuinely new number creates a row.
 */
export function useResolveCustomer() {
  const queryClient = useQueryClient();

  return useCallback(
    async (draft: CustomerDraft, known: Customer | null): Promise<Customer> => {
      if (known) return known;

      const phone = normalisePhone(draft.phone);
      const address = draft.address.trim();
      try {
        const created = await createCustomer({
          code: codeFor(phone),
          name: draft.name.trim(),
          customer_type: 'walk_in',
          phone,
          ...(address ? { address } : {}),
        });
        queryClient.invalidateQueries({ queryKey: ['customers'] });
        return created;
      } catch (error) {
        // Two tills can ring up the same new customer at once, and the loser of
        // that race gets a duplicate-code conflict. The row it wanted now
        // exists, so read it back instead of failing the sale.
        if (error instanceof ApiError && error.status === 409) {
          const matches = await fetchCustomers(phone);
          const existing =
            matches.find((c) => normalisePhone(c.phone ?? '') === phone) ??
            matches.find((c) => c.code === codeFor(phone));
          if (existing) return existing;
        }
        throw error;
      }
    },
    [queryClient],
  );
}
