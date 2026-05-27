/**
 * LibreCrawl i18n — lightweight translation engine
 * Usage in HTML:  data-i18n="key"            → sets textContent
 *                 data-i18n-placeholder="key" → sets placeholder
 *                 data-i18n-title="key"       → sets title attribute
 *                 data-i18n-html="key"        → sets innerHTML (use sparingly)
 * Usage in JS:    i18n.t('key')
 */
const i18n = (() => {
    const STORAGE_KEY = 'librecrawl_lang';
    const DEFAULT_LANG = 'de';
    let translations = {};
    let currentLang = localStorage.getItem(STORAGE_KEY) || DEFAULT_LANG;

    async function load(lang) {
        try {
            const res = await fetch(`/static/locales/${lang}.json?v=${Date.now()}`);
            if (!res.ok) throw new Error(`Failed to load ${lang}.json`);
            translations = await res.json();
            currentLang = lang;
            localStorage.setItem(STORAGE_KEY, lang);
            apply();
            updateToggleButtons();
        } catch (e) {
            console.warn('i18n: could not load', lang, e);
        }
    }

    function t(key, vars) {
        let str = translations[key] || key;
        if (vars) {
            Object.entries(vars).forEach(([k, v]) => {
                str = str.replace(new RegExp(`{${k}}`, 'g'), v);
            });
        }
        return str;
    }

    function apply(root) {
        const scope = root || document;
        scope.querySelectorAll('[data-i18n]').forEach(el => {
            const val = translations[el.dataset.i18n];
            if (val !== undefined) el.textContent = val;
        });
        scope.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const val = translations[el.dataset.i18nPlaceholder];
            if (val !== undefined) el.placeholder = val;
        });
        scope.querySelectorAll('[data-i18n-title]').forEach(el => {
            const val = translations[el.dataset.i18nTitle];
            if (val !== undefined) el.title = val;
        });
        scope.querySelectorAll('[data-i18n-html]').forEach(el => {
            const val = translations[el.dataset.i18nHtml];
            if (val !== undefined) el.innerHTML = val;
        });
        if (!root) document.documentElement.lang = currentLang;
    }

    function updateToggleButtons() {
        document.querySelectorAll('.i18n-toggle').forEach(btn => {
            btn.textContent = currentLang === 'de' ? '🇬🇧 EN' : '🇩🇪 DE';
            btn.title = currentLang === 'de' ? 'Switch to English' : 'Auf Deutsch wechseln';
        });
    }

    function toggle() {
        load(currentLang === 'de' ? 'en' : 'de');
    }

    function getLang() { return currentLang; }

    // Auto-init on DOM ready
    function init() {
        load(currentLang);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return { t, load, apply, toggle, getLang };
})();
