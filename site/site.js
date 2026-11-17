(function () {
  var d = document.documentElement;
  // Each page sets data-title-de/-en and data-desc-de/-en on <html>.
  var themeLabel = { de: 'Dunkles/helles Design umschalten', en: 'Toggle dark mode' };
  function attr(k, l) { return d.getAttribute('data-' + k + '-' + l); }
  function save(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function setLang(l, persist) {
    d.lang = l;
    if (attr('title', l)) document.title = attr('title', l);
    var md = document.querySelector('meta[name=description]');
    if (md && attr('desc', l)) md.content = attr('desc', l);
    document.getElementById('theme').setAttribute('aria-label', themeLabel[l]);
    document.querySelectorAll('[data-lang]').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.lang === l); });
    if (persist) save('ro-lang', l);
  }
  document.querySelectorAll('[data-lang]').forEach(function (b) {
    b.addEventListener('click', function () { setLang(b.dataset.lang, true); });
  });
  setLang(d.lang === 'de' ? 'de' : 'en', false);

  document.getElementById('theme').addEventListener('click', function () {
    var t = d.dataset.theme === 'dark' ? 'light' : 'dark';
    d.dataset.theme = t; save('vitepress-theme-appearance', t);
  });

  document.querySelectorAll('.copy').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var text = btn.parentElement.querySelector('code').innerText.replace(/^\$ /gm, '');
      var orig = btn.innerHTML;
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = d.lang === 'de' ? 'Kopiert' : 'Copied';
        setTimeout(function () { btn.innerHTML = orig; }, 1500);
      });
    });
  });

  var els = document.querySelectorAll('.rv');
  if (!('IntersectionObserver' in window)) { els.forEach(function (e) { e.classList.add('in'); }); return; }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { rootMargin: '0px 0px -8% 0px' });
  els.forEach(function (e, i) { e.style.transitionDelay = (i % 3) * 70 + 'ms'; io.observe(e); });
})();
