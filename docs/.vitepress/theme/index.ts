import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import { useData } from 'vitepress'
import './custom.css'

const SITE = 'https://m4rcelnoel.github.io/ring-off/'

// The default footer is hidden on pages with a sidebar, which is every docs
// page here, so the privacy link goes under the content instead.
const DocFooterNote = {
  setup() {
    const { lang } = useData()
    return () => {
      const de = lang.value === 'de'
      return h('p', { class: 'ro-doc-note' }, [
        de ? 'MIT-Lizenz · ' : 'MIT License · ',
        h('a', { href: SITE + 'datenschutz.html' }, de ? 'Datenschutz' : 'Privacy policy'),
        de ? ' · Keine Verbindung zu Ring LLC oder Amazon.' : ' · Not affiliated with Ring LLC or Amazon.',
      ])
    }
  },
}

export default {
  extends: DefaultTheme,
  Layout: () => h(DefaultTheme.Layout, null, { 'doc-after': () => h(DocFooterNote) }),
}
