# Audit texte — Andreea Tech

**Site:** https://andreeastech.pythonanywhere.com/
**Pagini verificate:** Home, Despre mine, Servicii, Servicii Restaurant, Servicii Programări, Contact, Începe un proiect, Produse, `base.html` (meta tags sitewide)
**Poziționare de referință:** "Digital Products & Experiences" — "De la o interacțiune obișnuită, la o experiență de care oamenii își amintesc"

---

## OK

- **Structura narativă cerută e prezentă** — unde ești acum → ce se întâmplă dacă aștepți → cum arată după — pe homepage ("Nu poți construi...", "Cum arată experiența înainte și după", "Tu alegi ce faci în continuare") și pe paginile de servicii ("Povestea clientului").
- **Ton specific, nu generic** — exemple concrete ("un client scrie și așteaptă", "o programare notată în grabă pe hârtie") în loc de fraze corporate abstracte, pe homepage și pe paginile de servicii restaurant/programări.
- **CTA prezent la finalul fiecărei secțiuni majore**, nu doar la finalul paginii — utilizatorul nu trebuie să scroleze mult ca să găsească un buton de acțiune.
- **Zero greșeli gramaticale grave** (acorduri, diacritice, punctuație) în textele verificate.

---

## De corectat urgent

1. **[REZOLVAT]** **`/despre-mine/` afișează încă vechea poziționare, vizibil, direct sub H1** — subtitlul e literal „Full-Stack Developer & AI Automation" (`about.html`), exact fraza înlocuită pe homepage cu „Digital Products & Experiences".
   **Corectat:** „Digital Products & Experiences — de la idee la sistem care funcționează."

2. **[REZOLVAT]** **Meta tags Open Graph/Twitter rămân pe vechea poziționare pe toate paginile, inclusiv homepage** — `base.html` definește default-urile ca „Andreea Sandu | Full-Stack Developer & AI Automation" + descrierea tehnică veche; `home.html` suprascrie doar `title`/`meta_description`, nu și `og_title`/`og_description`/`twitter_title`/`twitter_description`. Orice share pe LinkedIn/WhatsApp/Slack arată azi vechea poziționare.
   **Corectat (de adăugat în `home.html`):** `og_title`/`twitter_title` → „Andreea Sandu | Digital Products & Experiences"; `og_description`/`twitter_description` → „De la o interacțiune obișnuită, la o experiență de care oamenii își amintesc — construiesc produsul digital din spate: website, sistem, automatizare."

3. **[REZOLVAT]** **Footer-ul de pe toate paginile spune „Sisteme Web Django"** — limbaj de tehnologie, nu de beneficiu, vizibil peste tot pe site.
   **Corectat:** „© 2026 Andreea Sandu — Digital Products & Experiences" sau „...— Produse digitale care lucrează pentru tine."

4. **[REZOLVAT]** **Eyebrow-ul de pe `/servicii/` e „Dezvoltare Django & Python"** — vorbește tehnologie (framework/limbaj), nu problema antreprenorului — exact opusul recomandării din brief.
   **Corectat:** „Pentru afaceri care vor sisteme, nu doar site-uri" sau „Produse digitale, gândite pentru fluxul tău real."

5. **[REZOLVAT]** **Meta description-urile de pe `/contact/` și `/start-project/` rămân restrânse la „restaurantul sau afacerea ta bazată pe programări"**, deși homepage vorbește generic despre „antreprenori" — un vizitator din salon/clinică/alt domeniu se simte exclus înainte să deschidă pagina.
   **Corectat (`contact.html`):** „Contactează-mă ca să vorbim despre proiectul tău — website, sistem sau automatizare — și despre fluxul de lucru pe care vrei să-l îmbunătățești."

---

## Îmbunătățiri opționale

- **[REZOLVAT]** CTA-ul „Hai să discutăm proiectul tău" se repetă identic de 3 ori doar pe homepage — variază-l contextual (ex. „Vreau un audit al ideii mele →", „Spune-mi ce ai nevoie →") ca fiecare apariție să pară scrisă pentru locul ei.
- `services.html` („Sisteme web care lucrează pentru tine") și homepage („De la o interacțiune obișnuită, la o experiență...") au voci ușor diferite — una funcțională, alta emoțională/experiențială. Merită aliniate mai strâns, mai ales fiind unul dintre primele linkuri accesate din navigare.
- `products.html` are ton complet diferit (B2C, lifestyle: „Instrumente practice pentru o viață mai echilibrată") față de restul site-ului (B2B, antreprenori) — probabil intenționat, dar merită un rând explicit de tranziție („Pe lângă proiectele pentru clienți, construiesc și...") ca să nu pară un site separat.
