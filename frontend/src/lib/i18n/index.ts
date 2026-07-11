// Lightweight translation helper. A full i18n runtime (locale routing,
// pluralisation) is layered on in a later phase; the message-key contract is
// stable so components never change.
import { defaultLocale, type Locale, type MessageKey, messages } from './messages';

export { defaultLocale, locales, type Locale, type MessageKey } from './messages';

export function translate(locale: Locale, key: MessageKey): string {
  return messages[locale][key] ?? messages[defaultLocale][key] ?? key;
}

export function createTranslator(locale: Locale) {
  return (key: MessageKey): string => translate(locale, key);
}
