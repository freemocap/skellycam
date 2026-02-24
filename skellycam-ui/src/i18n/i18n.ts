import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

// Only eagerly load the fallback locale — all others are lazy-loaded on demand
import en from "./locales/en-english.json";

export const SUPPORTED_LOCALES = {
  en: { label: "English", dir: "ltr" as const, flag: "US" },
  es: { label: "Español", dir: "ltr" as const, flag: "ES" },
  fr: { label: "Français", dir: "ltr" as const, flag: "FR" },
  de: { label: "Deutsch", dir: "ltr" as const, flag: "DE" },
  it: { label: "Italiano", dir: "ltr" as const, flag: "IT" },
  "pt-BR": { label: "Português (Brasil)", dir: "ltr" as const, flag: "BR" },
  nl: { label: "Nederlands", dir: "ltr" as const, flag: "NL" },
  sv: { label: "Svenska", dir: "ltr" as const, flag: "SE" },
  pl: { label: "Polski", dir: "ltr" as const, flag: "PL" },
  cs: { label: "Čeština", dir: "ltr" as const, flag: "CZ" },
  uk: { label: "Українська", dir: "ltr" as const, flag: "UA" },
  ru: { label: "Русский", dir: "ltr" as const, flag: "RU" },
  tr: { label: "Türkçe", dir: "ltr" as const, flag: "TR" },
  ar: { label: "العربية", dir: "rtl" as const, flag: "PS" },
  fa: { label: "فارسی", dir: "rtl" as const, flag: "IR" },
  ur: { label: "اردو", dir: "rtl" as const, flag: "PK" },
  hi: { label: "हिन्दी", dir: "ltr" as const, flag: "IN" },
  bn: { label: "বাংলা", dir: "ltr" as const, flag: "BD" },
  ta: { label: "தமிழ்", dir: "ltr" as const, flag: "IN" },
  ne: { label: "नेपाली", dir: "ltr" as const, flag: "NP" },
  si: { label: "සිංහල", dir: "ltr" as const, flag: "LK" },
  "zh-CN": { label: "简体中文", dir: "ltr" as const, flag: "CN" },
  ja: { label: "日本語", dir: "ltr" as const, flag: "JP" },
  ko: { label: "한국어", dir: "ltr" as const, flag: "KR" },
  th: { label: "ไทย", dir: "ltr" as const, flag: "TH" },
  vi: { label: "Tiếng Việt", dir: "ltr" as const, flag: "VN" },
  id: { label: "Bahasa Indonesia", dir: "ltr" as const, flag: "ID" },
  ms: { label: "Bahasa Melayu", dir: "ltr" as const, flag: "MY" },
  tl: { label: "Tagalog", dir: "ltr" as const, flag: "PH" },
  my: { label: "မြန်မာ", dir: "ltr" as const, flag: "MM" },
  sw: { label: "Kiswahili", dir: "ltr" as const, flag: "KE" },
  am: { label: "አማርኛ", dir: "ltr" as const, flag: "ET" },
  ro: { label: "Română", dir: "ltr" as const, flag: "RO" },
  el: { label: "Ελληνικά", dir: "ltr" as const, flag: "GR" },
  hu: { label: "Magyar", dir: "ltr" as const, flag: "HU" },
  ka: { label: "ქართული", dir: "ltr" as const, flag: "GE" },
  sr: { label: "Српски", dir: "ltr" as const, flag: "RS" },
  hr: { label: "Hrvatski", dir: "ltr" as const, flag: "HR" },
  ca: { label: "Català", dir: "ltr" as const, flag: "ES" },
} as const;

export type SupportedLocale = keyof typeof SUPPORTED_LOCALES;

export const FALLBACK_LOCALE: SupportedLocale = "en";

/**
 * Returns the text direction for the given locale.
 * Defaults to "ltr" for unknown locales.
 */
export function getLocaleDirection(locale: string): "ltr" | "rtl" {
  if (locale in SUPPORTED_LOCALES) {
    return SUPPORTED_LOCALES[locale as SupportedLocale].dir;
  }
  return "ltr";
}

/**
 * Dynamic import loaders for each non-English locale.
 * Vite splits each into a separate chunk that's only fetched when needed.
 */
const LOCALE_LOADERS: Record<string, () => Promise<{ default: Record<string, any> }>> = {
  es: () => import("./locales/es-espanol.json"),
  fr: () => import("./locales/fr-francais.json"),
  de: () => import("./locales/de-deutsch.json"),
  it: () => import("./locales/it-italiano.json"),
  "pt-BR": () => import("./locales/pt-BR-portugues-brasil.json"),
  nl: () => import("./locales/nl-nederlands.json"),
  sv: () => import("./locales/sv-svenska.json"),
  pl: () => import("./locales/pl-polski.json"),
  cs: () => import("./locales/cs-cestina.json"),
  uk: () => import("./locales/uk-ukrainska.json"),
  ru: () => import("./locales/ru-russkiy.json"),
  tr: () => import("./locales/tr-turkce.json"),
  ar: () => import("./locales/ar-arabic.json"),
  fa: () => import("./locales/fa-farsi.json"),
  ur: () => import("./locales/ur-urdu.json"),
  hi: () => import("./locales/hi-hindi.json"),
  bn: () => import("./locales/bn-bangla.json"),
  ta: () => import("./locales/ta-tamil.json"),
  ne: () => import("./locales/ne-nepali.json"),
  si: () => import("./locales/si-sinhala.json"),
  "zh-CN": () => import("./locales/zh-CN-zhongwen.json"),
  ja: () => import("./locales/ja-nihongo.json"),
  ko: () => import("./locales/ko-hangugeo.json"),
  th: () => import("./locales/th-thai.json"),
  vi: () => import("./locales/vi-tieng-viet.json"),
  id: () => import("./locales/id-bahasa-indonesia.json"),
  ms: () => import("./locales/ms-melayu.json"),
  tl: () => import("./locales/tl-tagalog.json"),
  my: () => import("./locales/my-myanmar.json"),
  sw: () => import("./locales/sw-kiswahili.json"),
  am: () => import("./locales/am-amharic.json"),
  ro: () => import("./locales/ro-romana.json"),
  el: () => import("./locales/el-ellinika.json"),
  hu: () => import("./locales/hu-magyar.json"),
  ka: () => import("./locales/ka-kartuli.json"),
  sr: () => import("./locales/sr-srpski.json"),
  hr: () => import("./locales/hr-hrvatski.json"),
  ca: () => import("./locales/ca-catala.json"),
};

/** Tracks which locales have already been loaded to avoid duplicate fetches. */
const loadedLocales = new Set<string>(["en"]);

/**
 * Load a locale's translations on demand. If already loaded, resolves immediately.
 * Called automatically by the languageChanged event and can be called manually.
 */
export async function loadLocale(locale: string): Promise<void> {
  if (loadedLocales.has(locale)) return;

  const loader = LOCALE_LOADERS[locale];
  if (!loader) {
    throw new Error(`No locale loader registered for "${locale}". Supported: ${Object.keys(LOCALE_LOADERS).join(", ")}`);
  }

  const module = await loader();
  const translations = module.default;
  i18n.addResourceBundle(locale, "translation", translations, true, true);
  loadedLocales.add(locale);
}

/**
 * Returns the _meta.translationSource value from a locale's translations.
 * Only works for locales that have already been loaded.
 */
export function getTranslationSource(
  locale: string
): "human-authored" | "ai-generated" | "human-validated" {
  const resources = i18n.getResourceBundle(locale, "translation");
  const meta = resources?._meta;
  if (
    meta?.translationSource === "human-authored" ||
    meta?.translationSource === "ai-generated" ||
    meta?.translationSource === "human-validated"
  ) {
    return meta.translationSource;
  }
  return "ai-generated";
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
    },
    lng: FALLBACK_LOCALE,
    fallbackLng: FALLBACK_LOCALE,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage"],
      lookupLocalStorage: "skellycam:locale",
      caches: ["localStorage"],
    },
  });

// When the language changes (via user selection or detection), load the locale on demand.
// The UI briefly shows English keys until the async load completes, then re-renders.
i18n.on("languageChanged", (lng: string) => {
  if (lng !== FALLBACK_LOCALE) {
    loadLocale(lng);
  }
});

// If the detected language on startup is not English, load it immediately
const detectedLng = i18n.language;
if (detectedLng && detectedLng !== FALLBACK_LOCALE && !loadedLocales.has(detectedLng)) {
  loadLocale(detectedLng);
}

export default i18n;
