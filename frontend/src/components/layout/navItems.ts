import type { IconName } from '@/components/ui/Icon';

/**
 * Primary navigation, grouped by the job the user is doing.
 *
 * Each item declares the permissions that reveal it. A user sees an item only
 * when they hold **at least one** of them, so nobody is offered a page that
 * would 403 — the backend still enforces the same rules on every request.
 */
export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  /** Any one of these grants visibility. Empty means "everyone signed in". */
  permissions: string[];
}

export interface NavGroup {
  id: string;
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    id: 'overview',
    label: 'Overview',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: 'dashboard', permissions: [] },
    ],
  },
  {
    id: 'sell',
    label: 'Sell',
    items: [
      {
        href: '/sales',
        label: 'Retail counter',
        icon: 'pos',
        permissions: ['sales.create'],
      },
      {
        href: '/wholesale',
        label: 'Wholesale orders',
        icon: 'wholesale',
        permissions: ['sales.create'],
      },
      {
        href: '/invoices',
        label: 'Invoices',
        icon: 'invoices',
        permissions: ['sales.create'],
      },
      {
        href: '/customers',
        label: 'Customers',
        icon: 'customers',
        permissions: ['customer.view'],
      },
      {
        href: '/collections',
        label: 'Collections',
        icon: 'collections',
        permissions: ['payment.receive'],
      },
    ],
  },
  {
    id: 'stock',
    label: 'Stock',
    items: [
      {
        href: '/products',
        label: 'Products',
        icon: 'products',
        permissions: ['product.view'],
      },
      {
        href: '/inventory',
        label: 'Inventory',
        icon: 'inventory',
        permissions: ['inventory.view'],
      },
      {
        href: '/purchases',
        label: 'Purchases',
        icon: 'purchases',
        permissions: ['purchase.view'],
      },
    ],
  },
  {
    id: 'service',
    label: 'Service',
    items: [
      {
        href: '/service',
        label: 'Repair jobs',
        icon: 'service',
        permissions: ['service.manage'],
      },
    ],
  },
  {
    id: 'insights',
    label: 'Insights',
    items: [
      {
        href: '/reports',
        label: 'Reports',
        icon: 'reports',
        permissions: ['report.view'],
      },
      {
        href: '/accounting',
        label: 'Accounting',
        icon: 'accounting',
        permissions: ['report.view_profit'],
      },
      { href: '/audit', label: 'Audit log', icon: 'audit', permissions: ['audit.view'] },
    ],
  },
  {
    id: 'admin',
    label: 'Administration',
    items: [
      {
        href: '/settings',
        label: 'Settings',
        icon: 'settings',
        permissions: ['user.manage', 'settings.manage'],
      },
    ],
  },
];

/** Flattened list — used to resolve a landing page and page-level guards. */
export const allNavItems: NavItem[] = navGroups.flatMap((group) => group.items);

export function visibleGroups(can: (code: string) => boolean): NavGroup[] {
  return navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => item.permissions.length === 0 || item.permissions.some(can),
      ),
    }))
    .filter((group) => group.items.length > 0);
}

/**
 * Where a role should land after signing in: the dashboard for anyone, but for
 * single-purpose roles the first page they can actually work in is friendlier.
 */
export function defaultRouteFor(can: (code: string) => boolean): string {
  if (can('report.view')) return '/dashboard';
  const first = allNavItems.find(
    (item) => item.href !== '/dashboard' && item.permissions.some(can),
  );
  return first?.href ?? '/dashboard';
}
