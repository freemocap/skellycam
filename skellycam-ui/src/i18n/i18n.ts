import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./locales/en-english.json";
import es from "./locales/es-espanol.json";
import ar from "./locales/ar-arabic.json";
import zhCN from "./locales/zh-CN-zhongwen.json";
import hi from "./locales/hi-hindi.json";
import fr from "./locales/fr-francais.json";
import ptBR from "./locales/pt-BR-portugues-brasil.json";
import bn from "./locales/bn-bangla.json";
import ru from "./locales/ru-russkiy.json";
import ja from "./locales/ja-nihongo.json";
import de from "./locales/de-deutsch.json";
import ko from "./locales/ko-hangugeo.json";
import tr from "./locales/tr-turkce.json";
import it from "./locales/it-italiano.json";
import vi from "./locales/vi-tieng-viet.json";
import pl from "./locales/pl-polski.json";
import uk from "./locales/uk-ukrainska.json";
import nl from "./locales/nl-nederlands.json";
import th from "./locales/th-thai.json";
import id from "./locales/id-bahasa-indonesia.json";
import sv from "./locales/sv-svenska.json";
import cs from "./locales/cs-cestina.json";
import fa from "./locales/fa-farsi.json";
import sw from "./locales/sw-kiswahili.json";
import am from "./locales/am-amharic.json";
import tl from "./locales/tl-tagalog.json";
import ms from "./locales/ms-melayu.json";
import ro from "./locales/ro-romana.json";
import el from "./locales/el-ellinika.json";
import hu from "./locales/hu-magyar.json";
import ta from "./locales/ta-tamil.json";
import ur from "./locales/ur-urdu.json";
import my from "./locales/my-myanmar.json";
import ne from "./locales/ne-nepali.json";
import si from "./locales/si-sinhala.json";
import ka from "./locales/ka-kartuli.json";
import sr from "./locales/sr-srpski.json";
import hr from "./locales/hr-hrvatski.json";
import ca from "./locales/ca-catala.json";

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

const ALL_RESOURCES: Record<string, { _meta?: { translationSource?: string } }> = {
  en, es, fr, de, it, "pt-BR": ptBR, nl, sv, pl, cs, uk, ru, tr,
  ar, fa, ur, hi, bn, ta, ne, si,
  "zh-CN": zhCN, ja, ko, th, vi, id, ms, tl, my,
  sw, am, ro, el, hu, ka, sr, hr, ca,
};

/**
 * Returns the _meta.translationSource value from a locale's translations.
 * Used to display AI-translation warnings in the UI.
 */
export function getTranslationSource(
  locale: string
): "human-authored" | "ai-generated" | "human-validated" {
  const meta = ALL_RESOURCES[locale]?._meta;
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
    resources: Object.fromEntries(
      Object.entries(ALL_RESOURCES).map(([code, data]) => [code, { translation: data }])
    ),
    fallbackLng: FALLBACK_LOCALE,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "skellycam:locale",
      caches: ["localStorage"],
    },
  });

export default i18n;
