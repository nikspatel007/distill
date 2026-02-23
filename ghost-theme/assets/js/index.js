// TroopX Journal - Ghost Theme JavaScript

// Import CSS (processed by PostCSS via Rollup)
import "../css/index.css";

// Import modules
import menuOpen from "./menuOpen";

// Dark mode toggle
function initThemeToggle() {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;

    const html = document.documentElement;

    // Restore saved theme from localStorage
    const saved = localStorage.getItem('theme');
    if (saved) {
        html.setAttribute('data-theme', saved);
    }

    toggle.addEventListener('click', function () {
        const current = html.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    });
}

// Initialize
menuOpen();
initThemeToggle();
