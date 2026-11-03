/* Shared behaviour for the redesigned pages. No dependencies.
   Everything here is progressive enhancement: the site works without it. */
(function () {
    'use strict';

    /* Copy-to-clipboard buttons: <button data-copy="text">. Runs for every
       visitor, including those who prefer reduced motion. */
    document.addEventListener('click', function (event) {
        var btn = event.target.closest('[data-copy]');
        if (!btn) return;
        var original = btn.textContent;
        function flash(label) {
            btn.textContent = label;
            setTimeout(function () { btn.textContent = original; }, 1500);
        }
        if (!navigator.clipboard) { flash('Selectează manual'); return; }
        navigator.clipboard.writeText(btn.dataset.copy).then(
            function () { flash('Copiat'); },
            function () { flash('Selectează manual'); }
        );
    });

    /* Featured projects on Home: show the preview that matches the row under
       the pointer or keyboard focus. Without JavaScript the first preview
       stays visible. */
    var rows = document.querySelectorAll('.frow[data-panel]');
    if (rows.length) {
        var panels = document.querySelectorAll('.fpanel-item');
        var show = function (id) {
            rows.forEach(function (row) { row.classList.toggle('on', row.dataset.panel === id); });
            panels.forEach(function (panel) { panel.hidden = panel.id !== id; });
        };
        rows.forEach(function (row) {
            row.addEventListener('mouseenter', function () { show(row.dataset.panel); });
            row.addEventListener('focus', function () { show(row.dataset.panel); });
        });
    }
})();
