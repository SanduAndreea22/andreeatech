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

/* Portfolio: filter the list by direction. The filter buttons are hidden in
   the HTML and revealed here, so without JavaScript the full list shows. */
(function () {
    'use strict';
    var group = document.getElementById('pFilters');
    var list = document.getElementById('pList');
    if (!group || !list) return;
    var empty = document.getElementById('pEmpty');
    group.hidden = false;
    group.addEventListener('click', function (event) {
        var btn = event.target.closest('[data-filter]');
        if (!btn) return;
        var wanted = btn.dataset.filter;
        group.querySelectorAll('[data-filter]').forEach(function (b) {
            b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
        });
        var shown = 0;
        list.querySelectorAll('.prow').forEach(function (row) {
            var match = wanted === 'all' || row.dataset.direction === wanted;
            row.hidden = !match;
            if (match) shown += 1;
        });
        if (empty) empty.hidden = shown !== 0;
    });
})();

/* Products: Emotional Planner demo. Simulation only, nothing is saved. */
(function () {
    'use strict';
    var form = document.getElementById('plannerForm');
    if (!form) return;
    var moodGroup = document.getElementById('plannerMood');
    var output = document.getElementById('plannerOutput');
    var mood = 'ok';
    var copy = {
        grea: {
            intro: 'Azi pare o zi grea. E ok să mergi mai încet: un singur pas contează.',
            closing: 'Nu trebuie să fii productiv(ă) azi. Trebuie doar să fii sincer(ă) cu tine.'
        },
        ok: {
            intro: 'O zi obișnuită: poți avansa în ritmul tău, fără presiune.',
            closing: 'Bifează ce poți azi, restul rămâne pentru mâine.'
        },
        buna: {
            intro: 'Ai energie azi: e un moment bun să avansezi cu ce contează.',
            closing: 'O victorie mică contează la fel de mult ca una mare.'
        }
    };
    moodGroup.addEventListener('click', function (event) {
        var btn = event.target.closest('[data-mood]');
        if (!btn) return;
        mood = btn.dataset.mood;
        moodGroup.querySelectorAll('[data-mood]').forEach(function (b) {
            b.setAttribute('aria-pressed', b === btn ? 'true' : 'false');
        });
    });
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        var task = document.getElementById('plannerTask').value.trim() || 'Un task important pentru azi';
        var text = copy[mood];
        output.textContent = '';
        [['p', text.intro, ''], ['div', task, 'demo-task'], ['p', text.closing, 'muted']].forEach(function (item) {
            var el = document.createElement(item[0]);
            el.textContent = item[1];
            if (item[2]) el.className = item[2];
            output.appendChild(el);
        });
        output.hidden = false;
    });
})();

/* Products: MyBudget demo. Simulation only, nothing is saved. */
(function () {
    'use strict';
    var form = document.getElementById('budgetForm');
    if (!form) return;
    var output = document.getElementById('budgetOutput');
    var balanceEl = document.getElementById('budgetBalance');
    var bar = document.getElementById('budgetBar');
    var barLabel = document.getElementById('budgetBarLabel');
    var status = document.getElementById('budgetStatus');
    var euro = function (n) { return '€' + Math.round(n).toLocaleString('ro-RO'); };
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        var income = parseFloat(document.getElementById('budgetIncome').value) || 0;
        var spent = (parseFloat(document.getElementById('budgetFixed').value) || 0) +
                    (parseFloat(document.getElementById('budgetVariable').value) || 0);
        var balance = income - spent;
        var pct = income > 0 ? Math.min(100, (spent / income) * 100) : 0;
        balanceEl.textContent = (balance < 0 ? '-' : '') + euro(Math.abs(balance));
        balanceEl.className = balance < 0 ? 'is-negative' : 'is-positive';
        bar.style.width = pct + '%';
        barLabel.textContent = Math.round(pct) + '% din venit cheltuit';
        if (balance < 0) {
            status.textContent = 'Cheltuielile depășesc venitul cu ' + euro(Math.abs(balance)) + '.';
            status.className = 'status is-negative';
        } else {
            status.textContent = '';
            status.className = 'status';
        }
        output.hidden = false;
    });
})();
