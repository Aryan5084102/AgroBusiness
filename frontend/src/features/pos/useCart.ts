'use client';

import { useCallback, useMemo, useState } from 'react';
import type { CartLine } from './api';

export interface CartItem {
  productId: string;
  name: string;
  quantity: number;
}

// Local POS cart state. Quantities are integers here (POS sells whole base units);
// money math stays on the backend via the quote endpoint.
export function useCart() {
  const [items, setItems] = useState<CartItem[]>([]);

  const add = useCallback((productId: string, name: string) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.productId === productId);
      if (existing) {
        return prev.map((i) =>
          i.productId === productId ? { ...i, quantity: i.quantity + 1 } : i,
        );
      }
      return [...prev, { productId, name, quantity: 1 }];
    });
  }, []);

  const setQuantity = useCallback((productId: string, quantity: number) => {
    // A blank or half-typed quantity box yields NaN. Left alone it would be
    // sent as `"NaN"` and the server would refuse to price the whole cart, so
    // it is treated as a removal — the same as clearing the line.
    const next = Number.isFinite(quantity) ? Math.floor(quantity) : 0;
    setItems((prev) =>
      prev
        .map((i) => (i.productId === productId ? { ...i, quantity: next } : i))
        .filter((i) => i.quantity > 0),
    );
  }, []);

  const remove = useCallback((productId: string) => {
    setItems((prev) => prev.filter((i) => i.productId !== productId));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const lines: CartLine[] = useMemo(
    () =>
      items.map((i) => ({
        product_id: i.productId,
        base_quantity: String(i.quantity),
      })),
    [items],
  );

  return { items, lines, add, setQuantity, remove, clear };
}
