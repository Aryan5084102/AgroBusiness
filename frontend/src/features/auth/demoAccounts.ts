// Development-only demo accounts, shown on the login page for quick testing.
// These mirror the backend seed (app/seed.py) and never exist in production.

export const DEMO_PASSWORD = 'AgriFlow@123';

export interface DemoAccount {
  email: string;
  label: string;
}

export const DEMO_ACCOUNTS: DemoAccount[] = [
  { email: 'owner@agriflow.local', label: 'Owner (full access)' },
  { email: 'admin@agriflow.local', label: 'Administrator' },
  { email: 'billing@agriflow.local', label: 'Billing Operator' },
  { email: 'sales@agriflow.local', label: 'Wholesale Salesperson' },
  { email: 'inventory@agriflow.local', label: 'Inventory Manager' },
  { email: 'accountant@agriflow.local', label: 'Accountant' },
  { email: 'technician@agriflow.local', label: 'Service Technician' },
  { email: 'auditor@agriflow.local', label: 'Auditor (read-only)' },
];

// Only surface demo logins outside production builds.
export const showDemoAccounts = process.env.NODE_ENV !== 'production';
