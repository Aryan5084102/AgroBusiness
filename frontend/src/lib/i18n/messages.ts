// Translation catalogues. All user-facing text lives here — never hardcode
// strings in components. Regional languages can be added as new locale keys.

export const locales = ['en', 'hi'] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = 'en';

export const messages = {
  en: {
    'app.name': 'AgriFlow ERP',
    'app.tagline': 'Wholesale & retail operating system for agri-inputs',
    'nav.dashboard': 'Dashboard',
    'nav.sales': 'Sales',
    'nav.wholesale': 'Wholesale',
    'nav.purchases': 'Purchases',
    'nav.products': 'Products',
    'nav.inventory': 'Inventory',
    'nav.customers': 'Customers',
    'nav.reports': 'Reports',
    'nav.settings': 'Settings',
    'auth.signIn': 'Sign in',
    'auth.email': 'Email',
    'auth.password': 'Password',
    'auth.signInCta': 'Sign in to your account',
    'status.title': 'System status',
    'status.checking': 'Checking services…',
    'status.healthy': 'All systems operational',
    'status.degraded': 'Some services are degraded',
    'status.unreachable': 'Backend unreachable',
    'common.retry': 'Retry',
  },
  hi: {
    'app.name': 'एग्रीफ्लो ईआरपी',
    'app.tagline': 'कृषि-आदानों के लिए थोक और खुदरा प्रणाली',
    'nav.dashboard': 'डैशबोर्ड',
    'nav.sales': 'बिक्री',
    'nav.wholesale': 'थोक',
    'nav.purchases': 'खरीद',
    'nav.products': 'उत्पाद',
    'nav.inventory': 'स्टॉक',
    'nav.customers': 'ग्राहक',
    'nav.reports': 'रिपोर्ट',
    'nav.settings': 'सेटिंग्स',
    'auth.signIn': 'साइन इन',
    'auth.email': 'ईमेल',
    'auth.password': 'पासवर्ड',
    'auth.signInCta': 'अपने खाते में साइन इन करें',
    'status.title': 'सिस्टम स्थिति',
    'status.checking': 'सेवाओं की जाँच हो रही है…',
    'status.healthy': 'सभी सेवाएँ चालू हैं',
    'status.degraded': 'कुछ सेवाएँ बाधित हैं',
    'status.unreachable': 'बैकएंड उपलब्ध नहीं',
    'common.retry': 'पुनः प्रयास करें',
  },
} as const;

export type MessageKey = keyof (typeof messages)['en'];
