/* Applies the visitor's saved theme choice before the page is painted, so a
   dark-mode visitor never sees a white flash. Without a saved choice nothing
   is set and the system setting (prefers-color-scheme) decides. */
(function () {
    try {
        var saved = localStorage.getItem('at-theme');
        if (saved === 'light' || saved === 'dark') {
            document.documentElement.setAttribute('data-theme', saved);
        }
    } catch (e) { /* storage blocked: follow the system setting */ }
})();
