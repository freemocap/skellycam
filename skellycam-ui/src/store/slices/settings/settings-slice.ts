import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { SettingsState } from "./settings-types";
import type { SupportedLocale } from "@/i18n";
import { FALLBACK_LOCALE, getLocaleDirection } from "@/i18n";
import i18n from "@/i18n/i18n";

const STORAGE_KEYS = {
  LOCALE: "skellycam:locale",
  SHOW_TRANSLATION_INDICATOR: "skellycam:showTranslationIndicator",
} as const;

function loadLocale(): SupportedLocale {
  if (typeof window === "undefined") return FALLBACK_LOCALE;
  const saved = localStorage.getItem(STORAGE_KEYS.LOCALE);
  if (saved) return saved as SupportedLocale;
  return (i18n.language as SupportedLocale) || FALLBACK_LOCALE;
}

function loadShowTranslationIndicator(): boolean {
  if (typeof window === "undefined") return true;
  const saved = localStorage.getItem(STORAGE_KEYS.SHOW_TRANSLATION_INDICATOR);
  if (saved !== null) return JSON.parse(saved) as boolean;
  return true;
}

const initialState: SettingsState = {
  locale: loadLocale(),
  showTranslationIndicator: loadShowTranslationIndicator(),
};

export const settingsSlice = createSlice({
  name: "settings",
  initialState,
  reducers: {
    localeChanged: (state, action: PayloadAction<SupportedLocale>) => {
      state.locale = action.payload;
      localStorage.setItem(STORAGE_KEYS.LOCALE, action.payload);

      // Sync i18next and document direction
      i18n.changeLanguage(action.payload);
      const dir = getLocaleDirection(action.payload);
      document.documentElement.dir = dir;
      document.documentElement.lang = action.payload;
    },
    showTranslationIndicatorToggled: (state) => {
      state.showTranslationIndicator = !state.showTranslationIndicator;
      localStorage.setItem(
        STORAGE_KEYS.SHOW_TRANSLATION_INDICATOR,
        JSON.stringify(state.showTranslationIndicator)
      );
    },
  },
});

export const { localeChanged, showTranslationIndicatorToggled } =
  settingsSlice.actions;
