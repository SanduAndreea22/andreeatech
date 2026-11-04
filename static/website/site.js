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
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var shown = null;   // the number currently on screen
    var frame = 0;
    /* The total counts up (or down) to the new value instead of jumping.
       Visitors who prefer reduced motion, and the first paint, get it at once. */
    function show(target) {
        window.cancelAnimationFrame(frame);
        if (shown === null || reduce || shown === target) {
            shown = target;
            total.textContent = 'de la €' + target;
            return;
        }
        var from = shown;
        var start = null;
        function step(now) {
            if (start === null) start = now;
            var t = Math.min(1, (now - start) / 350);
            var eased = 1 - Math.pow(1 - t, 3);
            shown = Math.round(from + (target - from) * eased);
            total.textContent = 'de la €' + shown;
            if (t < 1) frame = window.requestAnimationFrame(step);
        }
        frame = window.requestAnimationFrame(step);
    }
    function update() {
        var choice = form.querySelector('input[name="direction"]:checked');
        if (!choice) return;
        var sum = Number(choice.value);
        form.querySelectorAll('input.addon:checked').forEach(function (box) { sum += Number(box.value); });
        show(sum);
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

/* Forms (Contact, brief, reviews):
   1. Romanian validation messages instead of the browser's own language.
   2. Visible "Se trimite..." state, because the view sends the notification
      email before redirecting and a slow connection would look dead. */
(function () {
    'use strict';
    document.querySelectorAll('form[method="POST"], form[method="post"]').forEach(function (form) {
        form.removeAttribute('novalidate');
        form.querySelectorAll('input, textarea, select').forEach(function (field) {
            field.addEventListener('invalid', function () {
                if (field.validity.valueMissing) {
                    field.setCustomValidity('Acest câmp este obligatoriu.');
                } else if (field.validity.typeMismatch && field.type === 'email') {
                    field.setCustomValidity('Adresa de email nu pare validă. Verific-o și mai încearcă o dată.');
                } else if (field.validity.tooShort || field.validity.tooLong || field.validity.patternMismatch) {
                    field.setCustomValidity('Verifică ce ai completat aici: nu pare în formatul așteptat.');
                } else {
                    field.setCustomValidity('');
                }
            });
            field.addEventListener('input', function () { field.setCustomValidity(''); });
        });
        var button = form.querySelector('button[type="submit"]');
        if (!button) return;
        var label = button.textContent;
        form.addEventListener('submit', function () {
            button.disabled = true;
            button.textContent = 'Se trimite...';
        });
        window.addEventListener('pageshow', function () {
            button.disabled = false;
            button.textContent = label;
        });
    });
})();

/* Brief form: the progress bar reflects how much of each step is actually
   filled in, not how far the page is scrolled. */
(function () {
    'use strict';
    var form = document.getElementById('briefForm');
    if (!form) return;
    var steps = form.querySelectorAll('[data-step]');
    var fills = document.querySelectorAll('#briefProgress .progress-fill');
    if (!steps.length || steps.length !== fills.length) return;

    function fieldNames(step) {
        var names = [];
        step.querySelectorAll('input, textarea, select').forEach(function (el) {
            if (el.type === 'hidden' || !el.name || names.indexOf(el.name) !== -1) return;
            names.push(el.name);
        });
        return names;
    }
    function isFilled(step, name) {
        var els = step.querySelectorAll('[name="' + name + '"]');
        if (!els.length) return false;
        if (els[0].type === 'checkbox' || els[0].type === 'radio') {
            return Array.prototype.some.call(els, function (el) { return el.checked; });
        }
        return els[0].value.trim() !== '';
    }
    var names = Array.prototype.map.call(steps, fieldNames);
    function update() {
        steps.forEach(function (step, i) {
            var filled = names[i].filter(function (n) { return isFilled(step, n); }).length;
            fills[i].style.width = names[i].length ? Math.round((filled / names[i].length) * 100) + '%' : '100%';
        });
    }
    form.addEventListener('input', update);
    form.addEventListener('change', update);
    update();
})();

/* About: enlarge a certificate in a native <dialog>. Without JavaScript the
   link opens the image in a new tab. */
(function () {
    'use strict';
    var dialog = document.getElementById('certDialog');
    if (!dialog || typeof dialog.showModal !== 'function') return;
    var img = dialog.querySelector('img');
    document.querySelectorAll('[data-cert]').forEach(function (link) {
        link.addEventListener('click', function (event) {
            event.preventDefault();
            img.src = link.getAttribute('href');
            img.alt = link.dataset.alt || '';
            dialog.showModal();
        });
    });
    dialog.addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('close', function () { img.removeAttribute('src'); });
})();

/* Theme: a manual switch next to the system setting. The saved choice is
   applied before first paint by theme.js; this only drives the button. The
   button stays hidden without JavaScript, because it could not work. */
(function () {
    'use strict';
    var button = document.getElementById('themeToggle');
    if (!button) return;
    var root = document.documentElement;
    var query = window.matchMedia('(prefers-color-scheme: dark)');
    function isDark() {
        var set = root.getAttribute('data-theme');
        return set ? set === 'dark' : query.matches;
    }
    function sync() {
        var dark = isDark();
        button.setAttribute('aria-pressed', dark ? 'true' : 'false');
        button.setAttribute('aria-label', dark ? 'Schimbă tema: luminos' : 'Schimbă tema: întunecat');
    }
    button.hidden = false;
    sync();
    button.addEventListener('click', function () {
        var next = isDark() ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try { localStorage.setItem('at-theme', next); } catch (e) { /* not saved, still applied */ }
        sync();
    });
    if (query.addEventListener) query.addEventListener('change', sync);
})();

/* Sections that start below the fold fade in once, when scrolled to. Anything
   already on screen is left alone, and nothing is hidden for visitors who
   prefer reduced motion or whose browser lacks IntersectionObserver. */
(function () {
    'use strict';
    if (!('IntersectionObserver' in window)) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var limit = window.innerHeight * 0.92;
    var targets = [];
    document.querySelectorAll('main .sec:not(.first) > .wrap').forEach(function (el) {
        if (el.getBoundingClientRect().top < limit) return;
        el.classList.add('rv');
        targets.push(el);
    });
    if (!targets.length) return;
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('rv-in');
            observer.unobserve(entry.target);
        });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    targets.forEach(function (el) { observer.observe(el); });
    /* Safety net: a link to #section, or a restored scroll position, must never
       leave a section invisible. */
    window.addEventListener('hashchange', function () {
        var hit = document.querySelector(location.hash || '#__none__');
        var wrap = hit && (hit.classList.contains('rv') ? hit : hit.querySelector('.rv'));
        if (wrap) wrap.classList.add('rv-in');
    });
})();

/* Home: two-screen booking demo. Simulation only: nothing is sent or saved. The
   first state is rendered by the template; the data comes from data-demo, so the
   page and this script share one source. All visitor text goes in with
   textContent, never as HTML. */
(function () {
    'use strict';
    var root = document.getElementById('bkDemo');
    if (!root) return;
    var data;
    try { data = JSON.parse(root.getAttribute('data-demo')); } catch (e) { return; }

    var form = document.getElementById('bkForm');
    var slotsBox = document.getElementById('bkSlots');
    var tbody = document.getElementById('bkRows');
    var log = document.getElementById('bkLog');
    var msg = document.getElementById('bkMsg');
    var go = document.getElementById('bkGo');
    var wait = document.getElementById('bkWait');
    var sent = document.getElementById('bkSent');
    var sentD = document.getElementById('bkSentD');
    var reset = document.getElementById('bkReset');
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    var seed = data.rows.map(function (r) { return { time: r.time, name: r.name, service: r.service, example: true, status: 'ok' }; });
    var rows = seed.slice();
    var confirmed = seed.length;
    var busy = false;
    var timers = [];

    function cell(tag, text, cls) {
        var td = document.createElement(tag);
        if (cls) td.className = cls;
        td.textContent = text;
        return td;
    }
    function renderSlots(keep) {
        var taken = rows.map(function (r) { return r.time; });
        slotsBox.textContent = '';
        data.slots.forEach(function (t) {
            var isTaken = taken.indexOf(t) !== -1;
            var label = document.createElement('label');
            label.className = 'bk-slot';
            var input = document.createElement('input');
            input.type = 'radio';
            input.name = 'slot';
            input.value = t;
            input.disabled = isTaken || busy;
            if (keep === t && !isTaken) input.checked = true;
            var span = document.createElement('span');
            span.appendChild(document.createTextNode(t));
            var small = document.createElement('small');
            small.textContent = isTaken ? 'ocupat' : 'liber';
            span.appendChild(small);
            label.appendChild(input);
            label.appendChild(span);
            slotsBox.appendChild(label);
        });
    }
    function renderRows(freshTime) {
        tbody.textContent = '';
        rows.slice().sort(function (a, b) { return a.time < b.time ? -1 : 1; }).forEach(function (r) {
            var tr = document.createElement('tr');
            if (r.time === freshTime) tr.className = 'is-new';
            tr.appendChild(cell('td', r.time, 't'));
            var who = cell('td', r.name);
            if (r.example) {
                var tag = document.createElement('span');
                tag.className = 'bk-ex';
                tag.textContent = 'exemplu';
                who.appendChild(tag);
            }
            tr.appendChild(who);
            tr.appendChild(cell('td', r.service));
            var state = document.createElement('td');
            var chip = document.createElement('span');
            chip.className = 'chip' + (r.status === 'new' ? ' st-new' : '');
            chip.textContent = r.status === 'new' ? 'Nouă' : 'Confirmată';
            state.appendChild(chip);
            tr.appendChild(state);
            tbody.appendChild(tr);
        });
        document.getElementById('bkStBk').textContent = rows.length;
        document.getElementById('bkStOk').textContent = confirmed;
    }
    function step(text) {
        var li = document.createElement('li');
        li.textContent = text;
        log.appendChild(li);
    }
    function later(fn, ms) {
        if (reduce) { fn(); return; }
        timers.push(window.setTimeout(fn, ms));
    }
    function restart() {
        timers.forEach(window.clearTimeout);
        timers = [];
        rows = seed.slice();
        confirmed = seed.length;
        busy = false;
        log.textContent = '';
        sent.hidden = true;
        wait.hidden = true;
        msg.textContent = '';
        go.disabled = false;
        document.getElementById('bkName').value = '';
        renderSlots();
        renderRows();
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();
        if (busy) return;
        var nameField = document.getElementById('bkName');
        var name = nameField.value.trim();
        var picked = slotsBox.querySelector('input[name="slot"]:checked');
        msg.textContent = '';
        if (!name) { msg.textContent = 'Scrie numele tău ca să trimiți cererea.'; nameField.focus(); return; }
        if (!picked) { msg.textContent = 'Alege o oră liberă.'; return; }
        var time = picked.value;
        var service = document.getElementById('bkService').value;
        busy = true;
        go.disabled = true;
        sent.hidden = true;
        wait.hidden = false;
        log.textContent = '';
        renderSlots(time);
        rows.push({ time: time, name: name, service: service, status: 'new' });
        renderRows(time);
        step('Cerere primită de la ' + name + ', ora ' + time + '.');
        later(function () { step('Disponibilitatea a fost verificată în calendar.'); }, 700);
        later(function () {
            step('Confirmare trimisă clientului.');
            rows.forEach(function (r) { if (r.time === time) r.status = 'ok'; });
            confirmed += 1;
            renderRows(time);
            wait.hidden = true;
            sent.hidden = false;
            sentD.textContent = ' ' + service + ', azi la ' + time + ', pe numele ' + name + '.';
        }, 1500);
        later(function () {
            step('Intervalul ' + time + ' a fost blocat pentru alți clienți.');
            busy = false;
            go.disabled = false;
            renderSlots();
        }, 2200);
    });
    reset.addEventListener('click', restart);

    /* Ready: enable the controls that need JavaScript and hide the notice. */
    document.getElementById('bkNoJs').hidden = true;
    go.disabled = false;
    reset.hidden = false;
    renderSlots();
    renderRows();
})();

/* Calculator: live result from the three fields. The same arithmetic as
   website/calculator.py (a test keeps them in step). Nothing is sent or saved. */
(function () {
    'use strict';
    var root = document.getElementById('calcRoot');
    if (!root) return;
    var weeks = parseFloat(String(root.getAttribute('data-weeks')).replace(',', '.')) || 4.33;
    var form = document.getElementById('calcForm');
    var live = document.getElementById('oLive');
    var byId = function (id) { return document.getElementById(id); };

    function read(id, max) {
        var v = parseFloat(String(byId(id).value).replace(',', '.'));
        if (!isFinite(v) || v < 0) v = 0;
        if (max !== undefined && v > max) v = max;
        return v;
    }
    function fmt(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }

    function update() {
        var perWeek = read('cA'), pct = read('cP', 100), value = read('cV');
        var total = perWeek * weeks;
        var lost = total * pct / 100;
        var month = lost * value;
        byId('oMonth').textContent = fmt(month) + ' lei';
        byId('oYear').textContent = fmt(month * 12) + ' lei';
        byId('oCount').textContent = fmt(lost);
        byId('oOne').textContent = fmt(weeks * value) + ' lei / lună';
        byId('oLost').style.width = pct + '%';
        byId('oKept').style.width = (100 - pct) + '%';
        byId('oKeptL').textContent = fmt(total - lost) + ' programări onorate';
        byId('oLostL').textContent = fmt(lost) + ' ratate';
        byId('oBar').setAttribute('aria-label', fmt(lost) + ' din ' + fmt(total) + ' programări lunare sunt ratate');
        return fmt(month);
    }
    form.addEventListener('input', update);
    /* Screen readers hear the result once the visitor leaves a field, not on every keystroke. */
    form.addEventListener('change', function () {
        live.textContent = 'Pierdere estimată: ' + update() + ' lei pe lună.';
    });
    form.addEventListener('submit', function (event) { event.preventDefault(); });
    update();
})();
