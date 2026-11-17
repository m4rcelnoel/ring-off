import { defineConfig, type DefaultTheme } from 'vitepress'

// The landing page (site/) lives at /ring-off/, these docs at /ring-off/docs/.
// See .github/workflows/pages.yml for how both are put together.
const SITE = 'https://m4rcelnoel.github.io/ring-off/'
const REPO = 'https://github.com/m4rcelnoel/ring-off'

function sidebarEn(): DefaultTheme.SidebarItem[] {
  return [
    {
      text: 'Getting started',
      items: [
        { text: 'Introduction', link: '/' },
        { text: 'Installation', link: '/guide/installation' },
        { text: 'Updating', link: '/guide/updating' },
        { text: 'Architecture', link: '/guide/architecture' },
      ],
    },
    {
      text: 'Configuration',
      items: [
        { text: 'Environment variables', link: '/configuration/environment' },
        { text: 'Settings in the web UI', link: '/configuration/settings' },
        { text: 'Ports & security', link: '/configuration/ports' },
      ],
    },
    {
      text: 'Guides',
      items: [
        { text: 'Live streaming', link: '/guides/streaming' },
        { text: 'Recording & NAS', link: '/guides/recording' },
        { text: 'Push notifications', link: '/guides/notifications' },
        { text: 'Home Assistant', link: '/guides/home-assistant' },
        { text: 'Existing MQTT broker', link: '/guides/mqtt-broker' },
      ],
    },
    {
      text: 'Help',
      items: [
        { text: 'Troubleshooting', link: '/troubleshooting' },
        { text: 'Development', link: '/development' },
      ],
    },
  ]
}

function sidebarDe(): DefaultTheme.SidebarItem[] {
  return [
    {
      text: 'Erste Schritte',
      items: [
        { text: 'Einführung', link: '/de/' },
        { text: 'Installation', link: '/de/guide/installation' },
        { text: 'Aktualisieren', link: '/de/guide/updating' },
        { text: 'Architektur', link: '/de/guide/architecture' },
      ],
    },
    {
      text: 'Konfiguration',
      items: [
        { text: 'Umgebungsvariablen', link: '/de/configuration/environment' },
        { text: 'Einstellungen in der Weboberfläche', link: '/de/configuration/settings' },
        { text: 'Ports & Sicherheit', link: '/de/configuration/ports' },
      ],
    },
    {
      text: 'Anleitungen',
      items: [
        { text: 'Live-Streaming', link: '/de/guides/streaming' },
        { text: 'Aufnahmen & NAS', link: '/de/guides/recording' },
        { text: 'Push-Benachrichtigungen', link: '/de/guides/notifications' },
        { text: 'Home Assistant', link: '/de/guides/home-assistant' },
        { text: 'Eigener MQTT-Broker', link: '/de/guides/mqtt-broker' },
      ],
    },
    {
      text: 'Hilfe',
      items: [
        { text: 'Fehlerbehebung', link: '/de/troubleshooting' },
        { text: 'Entwicklung', link: '/de/development' },
      ],
    },
  ]
}

export default defineConfig({
  base: '/ring-off/docs/',
  title: 'Ring Off',
  cleanUrls: true,
  lastUpdated: true,
  srcExclude: ['README.md'],

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/ring-off/docs/logo.svg' }],
    ['meta', { name: 'theme-color', content: '#6366f1' }],
    ['meta', { property: 'og:image', content: SITE + 'webinterface.png' }],
  ],

  // Same key the landing page uses, so light/dark carries over between them.
  appearance: true,

  themeConfig: {
    logo: '/logo.svg',
    socialLinks: [{ icon: 'github', link: REPO }],
    search: {
      provider: 'local',
      options: {
        // Don't keep the search term in sessionStorage (see site/datenschutz.html).
        disableQueryPersistence: true,
        locales: {
          de: {
            translations: {
              button: { buttonText: 'Suchen', buttonAriaLabel: 'Suchen' },
              modal: {
                displayDetails: 'Details anzeigen',
                resetButtonTitle: 'Suche zurücksetzen',
                backButtonTitle: 'Suche schließen',
                noResultsText: 'Keine Ergebnisse für',
                footer: { selectText: 'auswählen', navigateText: 'navigieren', closeText: 'schließen' },
              },
            },
          },
        },
      },
    },
  },

  locales: {
    root: {
      label: 'English',
      lang: 'en',
      description: 'Documentation for Ring Off – self-hosted Ring doorbell management without a subscription.',
      themeConfig: {
        nav: [
          { text: 'Home', link: SITE, target: '_self', rel: '', noIcon: true },
          { text: 'Guide', link: '/guide/installation', activeMatch: '^/(guide|configuration|guides)/' },
          { text: 'Troubleshooting', link: '/troubleshooting' },
          { text: 'Changelog', link: REPO + '/blob/main/CHANGELOG.md' },
        ],
        sidebar: sidebarEn(),
        editLink: { pattern: REPO + '/edit/main/docs/:path', text: 'Edit this page on GitHub' },
        footer: {
          message: `MIT License · <a href="${SITE}datenschutz.html">Privacy policy</a> · Not affiliated with Ring LLC or Amazon.`,
        },
        outline: { level: [2, 3], label: 'On this page' },
      },
    },
    de: {
      label: 'Deutsch',
      lang: 'de',
      link: '/de/',
      description: 'Dokumentation für Ring Off – Ring-Klingel selbst gehostet, ohne Abo.',
      themeConfig: {
        nav: [
          { text: 'Startseite', link: SITE, target: '_self', rel: '', noIcon: true },
          { text: 'Anleitung', link: '/de/guide/installation', activeMatch: '^/de/(guide|configuration|guides)/' },
          { text: 'Fehlerbehebung', link: '/de/troubleshooting' },
          { text: 'Changelog', link: REPO + '/blob/main/CHANGELOG.md' },
        ],
        sidebar: sidebarDe(),
        editLink: { pattern: REPO + '/edit/main/docs/:path', text: 'Diese Seite auf GitHub bearbeiten' },
        footer: {
          message: `MIT-Lizenz · <a href="${SITE}datenschutz.html">Datenschutz</a> · Keine Verbindung zu Ring LLC oder Amazon.`,
        },
        outline: { level: [2, 3], label: 'Auf dieser Seite' },
        docFooter: { prev: 'Vorherige Seite', next: 'Nächste Seite' },
        lastUpdated: { text: 'Zuletzt aktualisiert' },
        darkModeSwitchLabel: 'Design',
        lightModeSwitchTitle: 'Helles Design',
        darkModeSwitchTitle: 'Dunkles Design',
        sidebarMenuLabel: 'Menü',
        returnToTopLabel: 'Nach oben',
        langMenuLabel: 'Sprache ändern',
        notFound: {
          title: 'Seite nicht gefunden',
          quote: 'Diese Seite gibt es nicht – vielleicht hilft die Suche.',
          linkText: 'Zur Einführung',
        },
      },
    },
  },
})
