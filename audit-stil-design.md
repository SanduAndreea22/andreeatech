# Audit stil & design — Andreea Tech

**Site:** https://andreeastech.pythonanywhere.com/
**Pagini verificate:** Home, Servicii, Servicii Restaurant, Servicii Programări, Portofoliu, Despre mine, Contact, FAQ
**Metodă:** verificare live (desktop) + verificare structurală în cod (Tailwind breakpoints, `base.html` nav) — `resize_window` nu a schimbat efectiv `window.innerWidth` în acest mediu, deci responsive-ul a fost validat din clasele CSS, nu din screenshot-uri la breakpoint real.

---

## OK

- **Paletă, tipografie (Poppins) și componente** (`.glass`, `.gradient-text`, `.btn-primary`) identice pe toate paginile verificate — nicio pagină nu „sare" din temă.
- **Nav responsive corect structurat** — `hidden md:flex` pentru desktop + `<details class="md:hidden">` pentru mobil (`base.html:55,65`) — două stări clare, fără suprapunere sau conflict.
- **Grid-urile sunt „mobile-first"** — o singură coloană implicit, `sm:`/`md:`/`lg:` adaugă coloane doar de la un anumit prag în sus (pachete, carduri portofoliu, liste de beneficii) — zero risc de conținut înghesuit pe ecrane mici.
- **Blob-urile decorative cu lățime fixă** (500-800px, din fiecare hero) stau consecvent într-o secțiune cu `overflow-hidden` pe toate paginile — zero risc de scroll orizontal pe mobil din cauza lor.
- **Pagini 404/500 personalizate, pe brand** — nimic „rupt" vizibil dacă apare o eroare de server.

---

## De reparat urgent

1. **[REZOLVAT — prin eliminarea paginilor de nișă]** **Prețurile pentru aceleași 3 niveluri de pachet diferă masiv între pagini** — Homepage: Digital Presence €150 / Full Experience €380 / Premium System de la €850; Servicii Restaurant: Digital Presence €92 / Full Experience €184 / Premium System €460; Servicii Programări: Simple Website €74 / Smart Booking €92 / Full Platform €110. Un antreprenor care deschide două pagini vede prețuri diferite pentru „același" pachet — cea mai gravă inconsistență găsită, pentru că lovește direct în încredere, nu doar în estetică.
2. **[REZOLVAT]** **Descriere de proiect duplicată, vizibilă live pe /portofoliu/** — cardul „Bookora" afișează același paragraf de două ori, lipit fără spațiu („...înainte-înapoi.Aplicație de programări...") — se vede instant pe pagina care ar trebui să demonstreze atenție la detaliu.
3. **[REZOLVAT — prin eliminarea paginilor de nișă]** **Nume de pachete inconsistente între paginile de servicii** — „Simple Website / Smart Booking / Full Platform" (Programări) vs „Digital Presence / Full Experience / Premium System" (Homepage, Restaurant) rupe senzația de sistem coerent de oferte — un vizitator care trece de pe o pagină pe alta nu regăsește aceeași „scară" de pachete.

---

## Îmbunătățiri opționale

- O trecere manuală pe un telefon real (nu doar verificare de cod) tot merită făcută măcar o dată — tool-ul de test automat nu a putut simula fidel un viewport îngust în această sesiune.
- Consideră o singură sursă de adevăr pentru cele 3 niveluri de pachet (nume + preț), afișată identic pe toate paginile de servicii, cu eventuale reduceri de preț per nișă explicate explicit („de la", nu cifră fixă diferită).

---

**Impresie generală:** structural și vizual, site-ul arată competent și consecvent — dar cele două inconsistențe de mai sus (prețuri diferite + text duplicat) sunt exact genul de detalii pe care un antreprenor atent le observă în primele minute și care transformă impresia din „profesionist" în „neterminat".
