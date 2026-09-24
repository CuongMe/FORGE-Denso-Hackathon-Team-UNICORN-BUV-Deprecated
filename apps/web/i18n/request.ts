import { getRequestConfig } from 'next-intl/server';

import { getMessages, type Language } from '@/lib/i18n';

const supportedLanguages: Language[] = ['en', 'ja', 'vi'];

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = supportedLanguages.includes(requested as Language) ? requested as Language : 'en';

  return {
    locale,
    timeZone: 'Asia/Ho_Chi_Minh',
    messages: getMessages(locale),
  };
});
