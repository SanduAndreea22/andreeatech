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

/* Services: quick price estimate. Radios carry the base price and the target
   URL; checkboxes add the optional extras. */
(function () {
    'use strict';
    var form = document.getElementById('est');
    if (!form) return;
    var total = document.getElementById('estTotal');
    var cta = document.getElementById('estCta');
    function update() {
        var choice = form.querySelector('input[name="direction"]:checked');
        if (!choice) return;
        var sum = Number(choice.value);
        form.querySelectorAll('input.addon:checked').forEach(function (box) { sum += Number(box.value); });
        total.textContent = 'de la €' + sum;
        cta.setAttribute('href', choice.dataset.url);
    }
    form.addEventListener('change', update);
    form.addEventListener('submit', function (e) { e.preventDefault(); });
    update();
})();

/* Services (AI): booking-confirmation demo. Pure simulation, nothing is sent
   or stored. Steps appear one by one unless the visitor prefers reduced motion. */
(function () {
    'use strict';
    var form = document.getElementById('demoForm');
    if (!form) return;
    var log = document.getElementById('demoLog');
    var reset = document.getElementById('demoReset');
    var submit = form.querySelector('button[type="submit"]');
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var name = form.elements.name.value.trim();
        var service = form.elements.service.value.trim();
        var when = form.elements.when.value.trim();
        if (!name || !service || !when) {
            [form.elements.name, form.elements.service, form.elements.when].some(function (field) {
                if (!field.value.trim()) { field.focus(); return true; }
                return false;
            });
            return;
        }
        var steps = [
            'Cerere primită de la ' + name + '.',
            'Disponibilitatea a fost verificată în calendar.',
            'Confirmare trimisă clientului: ' + service + ', ' + when + '.',
            'Programarea a apărut în panoul de administrare.'
        ];
        log.textContent = '';
        submit.disabled = true;
        steps.forEach(function (text, i) {
            setTimeout(function () {
                var li = document.createElement('li');
                li.textContent = text;
                log.appendChild(li);
                if (i === steps.length - 1) reset.hidden = false;
            }, reduce ? 0 : i * 600);
        });
    });

    reset.querySelector('button').addEventListener('click', function () {
        log.textContent = '';
        reset.hidden = true;
        form.reset();
        submit.disabled = false;
        form.elements.name.focus();
    });
})();
