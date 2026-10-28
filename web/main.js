(function () {
  var root = document.documentElement;
  var toggle = document.getElementById('lang-toggle');
  var mail = document.getElementById('mail-cta');
  var subjects = {
    es: 'Baula - Quiero participar',
    en: 'Baula - I want in'
  };
  var titles = {
    es: 'Baula · Planificá tu salida de VMware',
    en: 'Baula · Plan your exit from VMware'
  };

  function pick() {
    var saved = null;
    try { saved = localStorage.getItem('baula-lang'); } catch (e) {}
    if (saved === 'es' || saved === 'en') return saved;
    var nav = (navigator.language || 'es').toLowerCase();
    return nav.indexOf('es') === 0 ? 'es' : 'en';
  }

  function apply(lang) {
    root.setAttribute('lang', lang);
    root.setAttribute('data-lang', lang);
    document.title = titles[lang];
    toggle.textContent = lang === 'es' ? 'EN' : 'ES';
    mail.href = 'mailto:hola@baulashift.com?subject=' + encodeURIComponent(subjects[lang]);
  }

  var lang = pick();
  apply(lang);

  toggle.addEventListener('click', function () {
    lang = lang === 'es' ? 'en' : 'es';
    apply(lang);
    try { localStorage.setItem('baula-lang', lang); } catch (e) {}
  });

  document.getElementById('year').textContent = new Date().getFullYear();
})();
