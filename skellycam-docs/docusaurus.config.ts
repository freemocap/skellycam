import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'SkellyCam',
  tagline: 'Frame-perfect multi-camera synchronization for USB webcams 💀📸',
  favicon: 'img/skellycam-favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://freemocap.github.io',
  baseUrl: '/skellycam/',

  organizationName: 'freemocap',
  projectName: 'skellycam',

  onBrokenLinks: 'throw',

  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  themes: ['@docusaurus/theme-mermaid'],

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'es', 'fr', 'de', 'it', 'pt-BR', 'nl', 'sv', 'pl', 'cs', 'uk', 'ru', 'tr', 'ar', 'fa', 'ur', 'hi', 'bn', 'ta', 'ne', 'si', 'zh-CN', 'ja', 'ko', 'th', 'vi', 'id', 'ms', 'tl', 'my', 'sw', 'am', 'ro', 'el', 'hu', 'ka', 'sr', 'hr', 'ca', 'chr', 'yi'],
    localeConfigs: {
      en: {label: 'English'},
      es: {label: 'Español'},
      fr: {label: 'Français'},
      de: {label: 'Deutsch'},
      it: {label: 'Italiano'},
      'pt-BR': {label: 'Português (Brasil)'},
      nl: {label: 'Nederlands'},
      sv: {label: 'Svenska'},
      pl: {label: 'Polski'},
      cs: {label: 'Čeština'},
      uk: {label: 'Українська'},
      ru: {label: 'Русский'},
      tr: {label: 'Türkçe'},
      ar: {label: 'العربية', direction: 'rtl'},
      fa: {label: 'فارسی', direction: 'rtl'},
      ur: {label: 'اردو', direction: 'rtl'},
      hi: {label: 'हिन्दी'},
      bn: {label: 'বাংলা'},
      ta: {label: 'தமிழ்'},
      ne: {label: 'नेपाली'},
      si: {label: 'සිංහල'},
      'zh-CN': {label: '简体中文'},
      ja: {label: '日本語'},
      ko: {label: '한국어'},
      th: {label: 'ไทย'},
      vi: {label: 'Tiếng Việt'},
      id: {label: 'Bahasa Indonesia'},
      ms: {label: 'Bahasa Melayu'},
      tl: {label: 'Tagalog'},
      my: {label: 'မြန်မာ'},
      sw: {label: 'Kiswahili'},
      am: {label: 'አማርኛ'},
      ro: {label: 'Română'},
      el: {label: 'Ελληνικά'},
      hu: {label: 'Magyar'},
      ka: {label: 'ქართული'},
      sr: {label: 'Српски'},
      hr: {label: 'Hrvatski'},
      ca: {label: 'Català'},
      chr: {label: 'ᏣᎳᎩ'},
      yi: {label: 'ייִדיש', direction: 'rtl'},
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: 'docs',
          editUrl:
            'https://github.com/freemocap/skellycam/tree/development/skellycam-docs/',
        },
        blog: {
          showReadingTime: true,
          feedOptions: {
            type: ['rss', 'atom'],
            xslt: true,
          },
          editUrl:
            'https://github.com/freemocap/skellycam/tree/development/skellycam-docs/',
          onInlineTags: 'warn',
          onInlineAuthors: 'warn',
          onUntruncatedBlogPosts: 'warn',
        },
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    image: 'img/skellycam-logo.png',
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'SkellyCam',
      logo: {
        alt: 'SkellyCam Logo',
        src: 'img/skellycam-logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {to: '/blog', label: 'Blog', position: 'left'},
        {to: '/download', label: 'Download', position: 'left'},
        {to: '/roadmap', label: 'Roadmap', position: 'left'},
        {
          href: 'https://github.com/freemocap/skellycam',
          label: 'GitHub',
          position: 'right',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Getting Started',
              to: '/docs/getting-started',
            },
            {
              label: 'Architecture',
              to: '/docs/architecture',
            },
            {
              label: 'API Reference',
              to: '/docs/api-reference',
            },
          ],
        },
        {
          title: 'Community',
          items: [
            {
              label: 'Discord',
              href: 'https://discord.gg/freemocap',
            },
            {
              label: 'GitHub Discussions',
              href: 'https://github.com/freemocap/skellycam/discussions',
            },
            {
              label: 'FreeMoCap',
              href: 'https://freemocap.org',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'Blog',
              to: '/blog',
            },
            {
              label: 'GitHub',
              href: 'https://github.com/freemocap/skellycam',
            },
            {
              label: 'Download',
              to: '/download',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} FreeMoCap Foundation. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'python', 'typescript'],
    },
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
    },
  } satisfies Preset.ThemeConfig & {mermaid?: {theme: {light: string; dark: string}}},
};

export default config;
