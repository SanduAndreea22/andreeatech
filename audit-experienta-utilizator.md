# Audit experiență utilizator — Andreea Tech

**Site:** https://andreeastech.pythonanywhere.com/
**Persona testată:** antreprenor ajuns pe site din LinkedIn/recomandare, fără context anterior, evaluează dacă acest freelancer îi rezolvă problema.
**Flux testat:** Home → Servicii → o pagină verticală de serviciu → Portofoliu → Contact

---

## Parcursul pas cu pas

**1. Aterizare pe Home** — Primul lucru văzut e titlul mare „Digital Products & Experiences". Fiind un nume de poziționare/brand, nu o propoziție de beneficiu, îi ia vizitatorului o clipă în plus să înțeleagă „produse ȘI experiențe — a ce anume?" — abia subtitlul de sub el („De la o interacțiune obișnuită, la o experiență...") clarifică. Funcționează, dar nu e claritate „din prima secundă", ci „din a doua". Restul hero-ului (subtitlu + CTA) e clar.

**2. Scroll pe Home** — Secțiunea de problemă ("Nu poți construi o experiență bună dacă ești ocupată...") e relatabilă imediat. La „De ce eu" apar nume proprii — Emotional Planner, Al Noir, Bookora — fără nicio propoziție de context înainte de a fi menționate; vizitatorul care nu a mai auzit de ele are un mic moment de „ce-s astea?" până dă click. Restul (Înainte/După, Ce câștigi, Pachete) curge logic, cu CTA la final de fiecare bloc.

**3. Home → Servicii** — Aici apare prima frecare reală. Titlul „Sisteme web care lucrează pentru tine" are o voce mai tehnică/funcțională față de tonul emoțional de pe Home — o mică disonanță de „am ajuns pe altă pagină a altcuiva?". Mai important: pagina arată exact **2 carduri** — Restaurant și Programări. Dacă vizitatorul nu se încadrează în niciuna din cele două nișe, singura reasigurare („Nu știi exact ce ți se potrivește? Hai să vorbim") e o linie mică, la finalul paginii — ușor de ratat dacă cineva scanează rapid și pleacă crezând că site-ul nu e pentru el.

**4. Servicii → o pagină verticală (ex. Restaurant)** — Pagina e bine construită (poveste, „De ce eu", pachete, add-on AI), cu link direct către Al Noir ca dovadă — bun. Dar prețurile de aici (€92/€184/€460) sunt mult mai mici decât aceleași nume de pachet de pe Home (€150/€380/€850) — dacă vizitatorul a văzut deja prețurile de pe Home, aici are un moment de „stai, de ce-i mai ieftin acum?" chiar în mijlocul parcursului de decizie.

**5. → Portofoliu** — Proiectul recomandat (Al Noir) e prezentat vizual, convingător. Dar imediat sub el, cardul „Bookora" are textul de descriere duplicat, lipit fără spațiu — exact în secțiunea menită să demonstreze atenție la detaliu. Și, odată ajuns la finalul grilei de proiecte, **nu există niciun CTA de închidere** — pagina se termină brusc după ultimul card. E punctul unde vizitatorul e cel mai convins („arată profesionist") și exact acolo nu i se oferă un pas următor — trebuie să urce singur la navigare și să caute Contact.

**6. → Contact** — Aici funcționează bine: două căi clare, formular rapid sau brief complet, în funcție de cât de decis e vizitatorul. Zero frecare pe acest ultim pas, odată ajuns aici.

**Notă laterală de navigare:** între „Servicii" și „Portofoliu" stă „Produse" — care duce la aplicații personale (planner, tracker de buget), nu la produse de business. Un vizitator B2B care dă click aici așteptând studii de caz/produse pentru afaceri găsește altceva și trebuie să-și recalibreze așteptarea.

---

## De reparat urgent

1. **[REZOLVAT]** **`/portofoliu/` nu are niciun CTA la final** — exact în punctul de vârf al interesului (după ce a văzut dovada), vizitatorul rămâne fără un pas următor pe pagină; trebuie să caute singur Contact în navigare.
2. **[REZOLVAT]** **Textul duplicat pe cardul Bookora** apare chiar în secțiunea „dovadă" a site-ului — subminează încrederea exact acolo unde ar trebui construită.
3. **[REZOLVAT — prin eliminarea paginilor de nișă]** **Prețurile diferă între Home și paginile de servicii verticale pentru aceleași nume de pachet** — vizitatorul care parcurge Home → Servicii → o verticală vede o scădere bruscă de preț pentru „același" pachet, în mijlocul deciziei.
4. **[REZOLVAT — prin eliminarea paginilor de nișă]** **Reasigurarea pentru cine nu se regăsește în cele 2 verticale de pe `/servicii/`** e o linie mică, la finalul paginii — mută-o mai sus sau repet-o, ca vizitatorii din alte nișe (clinici, consultanță etc.) să nu plece crezând că site-ul nu-i pentru ei.

## Îmbunătățiri opționale

- Testează cu useri reali dacă „Digital Products & Experiences" ca titlu principal se înțelege instant, sau dacă are nevoie de o secundă în plus (subtitlul deja ajută, dar merită validat).
- Adaugă o propoziție scurtă de context înainte de a numi Emotional Planner/Al Noir/Bookora în „De ce eu", ca să nu fie nume proprii „aruncate" fără ancorare.
- Adaugă un CTA individual pe fiecare card de pachet („Alege acest pachet →"), nu doar unul general la finalul secțiunii de prețuri.
- Reconsideră poziția/denumirea „Produse" în navigare, ca să nu întrerupă fluxul B2B dintre Servicii și Portofoliu cu conținut B2C.
