import type { MessageKey } from '@/lib/i18n';

// Primary navigation. Each item declares the permission that will gate it in
// Phase 1+ (RBAC). Phase 0 renders them all; PermissionGuard enforces later.
export interface NavItem {
  href: string;
  labelKey: MessageKey;
  permission: string | null;
}

export const navItems: NavItem[] = [
  { href: '/dashboard', labelKey: 'nav.dashboard', permission: null },
  { href: '/sales', labelKey: 'nav.sales', permission: 'sales.create' },
  { href: '/wholesale', labelKey: 'nav.wholesale', permission: 'sales.create' },
  { href: '/purchases', labelKey: 'nav.purchases', permission: 'purchase.view' },
  { href: '/products', labelKey: 'nav.products', permission: 'product.view' },
  { href: '/inventory', labelKey: 'nav.inventory', permission: 'inventory.view' },
  { href: '/customers', labelKey: 'nav.customers', permission: 'customer.view' },
  { href: '/reports', labelKey: 'nav.reports', permission: 'report.view' },
  { href: '/settings', labelKey: 'nav.settings', permission: 'user.manage' },
];
