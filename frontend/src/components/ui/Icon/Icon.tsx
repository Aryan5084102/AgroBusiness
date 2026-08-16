import type { SVGProps } from 'react';

/**
 * Inline SVG icon set. Icons are drawn with `currentColor` and a 1.75 stroke so
 * they inherit text colour and stay legible at 16–20px. Keeping them inline
 * avoids an icon-font/CDN dependency and keeps the bundle honest.
 */
export type IconName =
  | 'dashboard'
  | 'pos'
  | 'wholesale'
  | 'purchases'
  | 'products'
  | 'inventory'
  | 'customers'
  | 'collections'
  | 'service'
  | 'reports'
  | 'accounting'
  | 'audit'
  | 'settings'
  | 'invoices'
  | 'search'
  | 'plus'
  | 'close'
  | 'check'
  | 'alert'
  | 'info'
  | 'bell'
  | 'logout'
  | 'menu'
  | 'chevronLeft'
  | 'chevronRight'
  | 'chevronDown'
  | 'download'
  | 'print'
  | 'trash'
  | 'edit'
  | 'refresh'
  | 'user'
  | 'lock'
  | 'trendUp'
  | 'warehouse';

const PATHS: Record<IconName, string> = {
  dashboard: 'M4 13h6V4H4v9Zm0 7h6v-5H4v5Zm10 0h6v-9h-6v9Zm0-16v5h6V4h-6Z',
  pos: 'M3 6h18l-1.5 9H5.5L4 6Zm0 0-.7-3H1M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm8 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
  wholesale: 'M3 9 12 4l9 5v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1V9Z',
  purchases:
    'M3 4h2l2.5 11h10L20 7H6.5M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm8 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z',
  products: 'M20 7.5 12 3 4 7.5v9L12 21l8-4.5v-9Zm-8 4.5L4 7.5M12 12l8-4.5M12 12v9',
  inventory: 'M3 7h18v4H3V7Zm1 4v9h16v-9M9.5 15h5',
  customers:
    'M16 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-5A3.5 3.5 0 0 0 4 18.5V20M10 11.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm10 8.5v-1.5a3.5 3.5 0 0 0-2.6-3.4M15.5 4.6a3.5 3.5 0 0 1 0 6.8',
  collections: 'M3 7h18v10H3V7Zm9 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM6.5 7v.01M17.5 17v.01',
  service:
    'm14.7 6.3 3 3M3 21l1-4 10.5-10.5a2.1 2.1 0 0 1 3 3L7 20l-4 1Zm14-14 2-2 2 2-2 2',
  reports: 'M4 20V10m5 10V4m5 16v-7m5 7V8',
  accounting: 'M5 3h14v18H5V3Zm3 4h8M8 11h3m2 0h3M8 15h3m2 0h3',
  audit: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13ZM20 20l-4.9-4.9',
  settings:
    'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm8-3.5a8 8 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a8 8 0 0 0-2-1.2L15 3H9l-.5 2.6a8 8 0 0 0-2 1.2l-2.4-1-2 3.5 2 1.5a8 8 0 0 0 0 2.4l-2 1.5 2 3.5 2.4-1a8 8 0 0 0 2 1.2L9 21h6l.5-2.6a8 8 0 0 0 2-1.2l2.4 1 2-3.5-2-1.5c.07-.4.1-.8.1-1.2Z',
  invoices: 'M6 3h9l3 3v15l-2-1.5L14 21l-2-1.5L10 21l-2-1.5L6 21V3Zm3 5h6M9 12h6M9 16h4',
  search: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14Zm10 3-5-5',
  plus: 'M12 5v14M5 12h14',
  close: 'M6 6l12 12M18 6 6 18',
  check: 'm5 13 4.5 4.5L19 7',
  alert:
    'M12 8v5m0 3.5v.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-9v4.5M12 7.5v.01',
  bell: 'M18 9a6 6 0 1 0-12 0c0 5-2 6-2 6h16s-2-1-2-6ZM10.3 20a2 2 0 0 0 3.4 0',
  logout: 'M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14 5-5-5-5M20 12H9',
  menu: 'M4 7h16M4 12h16M4 17h16',
  chevronLeft: 'm14 6-6 6 6 6',
  chevronRight: 'm10 6 6 6-6 6',
  chevronDown: 'm6 10 6 6 6-6',
  download: 'M12 3v12m0 0 4.5-4.5M12 15l-4.5-4.5M4 19h16',
  print:
    'M7 9V3h10v6M7 19H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2M7 15h10v6H7v-6Z',
  trash: 'M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v6m4-6v6',
  edit: 'M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17l-1 3Zm11-13 3 3',
  refresh: 'M20 11A8 8 0 0 0 6 6.3L4 8m0-4v4h4m-4 4a8 8 0 0 0 14 4.7l2-1.7m0 4v-4h-4',
  user: 'M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  lock: 'M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5V11Z',
  trendUp: 'm3 17 6-6 4 4 8-8m0 0h-5m5 0v5',
  warehouse: 'M3 21V9l9-5 9 5v12M8 21v-7h8v7M3 21h18',
};

export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'name'> {
  name: IconName;
  size?: number;
  title?: string;
}

export function Icon({ name, size = 18, title, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      focusable="false"
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}
