import { render as rtlRender, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api/client';
import type { Product, ProductPage } from './api';

// Mock the data hooks and permissions so the component test has no network
// dependency and renders as a user who may create/edit products.
const useProductsMock = vi.fn();
vi.mock('./useProducts', () => ({
  useProducts: () => useProductsMock(),
  useCategories: () => ({ data: [], isLoading: false, error: null }),
  useUnits: () => ({ data: [], isLoading: false, error: null }),
  useCreateProduct: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateProduct: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock('@/features/auth/usePermissions', () => ({
  usePermissions: () => ({
    isLoading: false,
    isOwner: true,
    permissions: new Set<string>(),
    can: () => true,
    canAny: () => true,
    canAll: () => true,
  }),
}));

import { ProductsTable } from './ProductsTable';

// Screens raise toasts after mutations, so tests need the provider in scope.
function render(ui: ReactElement) {
  return rtlRender(<ToastProvider>{ui}</ToastProvider>);
}

function result(overrides: Record<string, unknown>) {
  return {
    data: undefined,
    isLoading: false,
    error: null,
    isFetching: false,
    refetch: vi.fn(),
    ...overrides,
  };
}

const product: Product = {
  id: '1',
  name: 'Maize Seed',
  sku: 'MZ-1',
  barcode: null,
  category_id: 'cat-1',
  category_name: 'Seed',
  base_unit_id: 'unit-1',
  unit_code: 'pcs',
  hsn_code: null,
  retail_price: '120.00',
  wholesale_price: '100.00',
  mrp: '130.00',
  gst_rate: '5',
  min_stock: '10',
  on_hand: '42',
  tracks_batches: true,
  tracks_expiry: true,
  is_active: true,
};

const page: ProductPage = { items: [product], total: 1, limit: 25, offset: 0 };

describe('ProductsTable', () => {
  it('renders product rows with formatted currency', () => {
    useProductsMock.mockReturnValue(result({ data: page }));
    render(<ProductsTable />);
    expect(screen.getByText('Maize Seed')).toBeInTheDocument();
    expect(screen.getByText(/MZ-1/)).toBeInTheDocument();
    // ₹120.00 rendered via the currency formatter.
    expect(screen.getByText(/120\.00/)).toBeInTheDocument();
  });

  it('shows an empty state when there are no products', () => {
    useProductsMock.mockReturnValue(result({ data: { ...page, items: [], total: 0 } }));
    render(<ProductsTable />);
    expect(screen.getByText(/no products found/i)).toBeInTheDocument();
  });

  it('shows a readable error state on failure', () => {
    useProductsMock.mockReturnValue(
      result({
        error: new ApiError(500, {
          code: 'server_error',
          message: 'Something went wrong.',
          field_errors: {},
          correlation_id: null,
        }),
      }),
    );
    render(<ProductsTable />);
    expect(screen.getByText(/could not load this/i)).toBeInTheDocument();
  });
});
