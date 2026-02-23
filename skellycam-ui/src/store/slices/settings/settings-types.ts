import type { SupportedLocale } from "@/i18n";

export interface SettingsState {
  locale: SupportedLocale;
  showTranslationIndicator: boolean;
}
