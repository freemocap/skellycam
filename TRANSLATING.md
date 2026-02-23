# 🌐 Translating SkellyCam

We use community translations to make motion capture accessible worldwide. No coding required — just edit a JSON file and open a PR.

**[→ Browse translation files on GitHub](https://github.com/freemocap/skellycam/tree/development/skellycam-ui/src/i18n/locales)**

## Current status

All non-English translations are **AI-generated and unreviewed** — they almost certainly contain errors. Even fixing a few strings helps!

## Translation files

All UI strings live in `skellycam-ui/src/i18n/locales/`:

| File | Language | Status |
|------|----------|--------|
| `en-english.json` | 🇬🇧 English | ✅ Source of truth |
| `es-espanol.json` | 🇪🇸 Español | 🤖 AI-generated |
| `fr-francais.json` | 🇫🇷 Français | 🤖 AI-generated |
| `de-deutsch.json` | 🇩🇪 Deutsch | 🤖 AI-generated |
| `it-italiano.json` | 🇮🇹 Italiano | 🤖 AI-generated |
| `pt-BR-portugues-brasil.json` | 🇧🇷 Português (Brasil) | 🤖 AI-generated |
| `ca-catala.json` | 🇪🇸 Català | 🤖 AI-generated |
| `nl-nederlands.json` | 🇳🇱 Nederlands | 🤖 AI-generated |
| `sv-svenska.json` | 🇸🇪 Svenska | 🤖 AI-generated |
| `pl-polski.json` | 🇵🇱 Polski | 🤖 AI-generated |
| `cs-cestina.json` | 🇨🇿 Čeština | 🤖 AI-generated |
| `ro-romana.json` | 🇷🇴 Română | 🤖 AI-generated |
| `hu-magyar.json` | 🇭🇺 Magyar | 🤖 AI-generated |
| `el-ellinika.json` | 🇬🇷 Ελληνικά | 🤖 AI-generated |
| `hr-hrvatski.json` | 🇭🇷 Hrvatski | 🤖 AI-generated |
| `sr-srpski.json` | 🇷🇸 Српски | 🤖 AI-generated |
| `uk-ukrainska.json` | 🇺🇦 Українська | 🤖 AI-generated |
| `ru-russkiy.json` | 🇷🇺 Русский | 🤖 AI-generated |
| `ka-kartuli.json` | 🇬🇪 ქართული | 🤖 AI-generated |
| `tr-turkce.json` | 🇹🇷 Türkçe | 🤖 AI-generated |
| `ar-arabic.json` | 🇸🇦 العربية | 🤖 AI-generated |
| `fa-farsi.json` | 🇮🇷 فارسی | 🤖 AI-generated |
| `ur-urdu.json` | 🇵🇰 اردو | 🤖 AI-generated |
| `hi-hindi.json` | 🇮🇳 हिन्दी | 🤖 AI-generated |
| `bn-bangla.json` | 🇧🇩 বাংলা | 🤖 AI-generated |
| `ta-tamil.json` | 🇮🇳 தமிழ் | 🤖 AI-generated |
| `ne-nepali.json` | 🇳🇵 नेपाली | 🤖 AI-generated |
| `si-sinhala.json` | 🇱🇰 සිංහල | 🤖 AI-generated |
| `zh-CN-zhongwen.json` | 🇨🇳 简体中文 | 🤖 AI-generated |
| `ja-nihongo.json` | 🇯🇵 日本語 | 🤖 AI-generated |
| `ko-hangugeo.json` | 🇰🇷 한국어 | 🤖 AI-generated |
| `th-thai.json` | 🇹🇭 ไทย | 🤖 AI-generated |
| `vi-tieng-viet.json` | 🇻🇳 Tiếng Việt | 🤖 AI-generated |
| `id-bahasa-indonesia.json` | 🇮🇩 Bahasa Indonesia | 🤖 AI-generated |
| `ms-melayu.json` | 🇲🇾 Bahasa Melayu | 🤖 AI-generated |
| `tl-tagalog.json` | 🇵🇭 Tagalog | 🤖 AI-generated |
| `my-myanmar.json` | 🇲🇲 မြန်မာ | 🤖 AI-generated |
| `sw-kiswahili.json` | 🇰🇪 Kiswahili | 🤖 AI-generated |
| `am-amharic.json` | 🇪🇹 አማርኛ | 🤖 AI-generated |

## How to contribute

1. Click any language file above (or find it in `skellycam-ui/src/i18n/locales/`)
2. Click the pencil icon to edit directly on GitHub
3. Fix any translations you see that are wrong or awkward
4. Submit a pull request

Strings use i18next format — preserve `{{variables}}` exactly as-is and keep `_one`/`_other` suffixes for plurals.

Backend strings (camera names, log messages, codecs, file paths) don't need translation.

## Adding a new language

1. Copy `en-english.json` to `<locale-code>-<language-name>.json`
2. Translate the values (not the keys)
3. Set `_meta.translationSource` to `"ai-generated"` or `"human-authored"`
4. Open an issue or PR — we'll wire it into the app

## Questions?

Open an issue on GitHub or reach out on the [FreeMoCap Discord](https://discord.gg/freemocap).
