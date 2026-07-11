import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ProductPage } from './api';

// Mock the data hook so the component test has no network dependency.
const useProductsMock = vi.fn();
vi.mock('./useProducts', () => ({
  useProducts: () => useProductsMock(),
}));

import { ProductsTable } from './ProductsTable';

function result(overrides: Record<string, unknown>) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    isFetching: false,
    ...overrides,
  };
}

const page: ProductPage = {
  items: [
    {
      id: '1',
      name: 'Maize Seed',
      sku: 'MZ-1',
      barcode: null,
      retail_price: '120.00',
      wholesale_price: '100.00',
      mrp: '130.00',
      gst_rate: '5',
      tracks_batches: true,
      is_active: true,
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
};

describe('ProductsTable', () => {
  it('renders product rows with formatted currency', () => {
    useProductsMock.mockReturnValue(result({ data: page }));
    render(<ProductsTable />);
    expect(screen.getByText('Maize Seed')).toBeInTheDocument();
    expect(screen.getByText('MZ-1')).toBeInTheDocument();
    // ₹120.00 rendered via the currency formatter.
    expect(screen.getByText(/120\.00/)).toBeInTheDocument();
  });

  it('shows an empty state when there are no products', () => {
    useProductsMock.mockReturnValue(result({ data: { ...page, items: [], total: 0 } }));
    render(<ProductsTable />);
    expect(screen.getByText(/no products found/i)).toBeInTheDocument();
  });

  it('shows an error state on failure', () => {
    useProductsMock.mockReturnValue(result({ isError: true }));
    render(<ProductsTable />);
    expect(screen.getByRole('alert')).toHaveTextContent(/could not load products/i);
  });
});
