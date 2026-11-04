"""Content of the FAQ page.

Single source for the questions and answers: the page renders the visible
<details> from it, and the FAQPage structured data is generated from the same
list, so the two can never disagree.

Each group is (anchor id, title, [(question, answer), ...]).
"""

FAQ_GROUPS = [('colaborare',
  'Colaborare',
  [('De ce să te aleg pe tine și nu o agenție?',
    'Lucrezi direct cu mine, de la primul mesaj până la livrare, fără un account manager care transmite mai '
    'departe unei echipe. Eu construiesc, eu răspund la mesaje și eu știu în ce stadiu e proiectul tău în '
    'orice moment.'),
   ('Cum arată colaborarea, pas cu pas?',
    'Pornim cu un call inițial în care clarificăm exact ce ai nevoie. Pe parcursul proiectului comunicăm '
    'prin mesaje: îți arăt progresul și iau feedback fără să fie nevoie de call-uri programate. La final ai '
    '7 zile de ajustări gratuite după livrare.'),
   ('Ce se întâmplă dacă dispari după ce livrezi proiectul?',
    'Fiecare proiect are 7 zile de ajustări gratuite după livrare: orice bug găsești în perioada asta, îl '
    'repar fără cost suplimentar. Rămân contactabilă și după. Dacă apare o problemă mai târziu sau vrei '
    'mentenanță continuă, discutăm separat, dar nu dispar odată ce ai plătit.'),
   ('Nu știu exact de ce am nevoie. De unde pornim?',
    'Complet normal. Alege „Nu sunt sigur/ă, hai să discutăm” din formular și stabilim împreună, pe situația '
    'reală a afacerii tale, dacă ai nevoie de un site sau un sistem, de o automatizare sau de partea '
    'creativă, și cât de complex ar fi. Nu te împing spre varianta cea mai scumpă.'),
   ('Ce ai nevoie de la mine?',
    'Îmi dai contextul afacerii tale, fluxul de lucru actual, obiectivele și orice materiale existente. '
    'Transform asta într-un plan clar, cu termen de livrare stabilit.'),
   ('Oferi suport după lansare?',
    'Da. Ai 7 zile de ajustări gratuite după livrare: orice bug apare în perioada asta, îl repar fără '
    'cost suplimentar. Mentenanța continuă, dincolo de bug-uri, se poate stabili separat, atunci când e '
    'nevoie.')]),
 ('pret',
  'Preț și termene',
  [('Cât costă un proiect?',
    'Fiecare direcție are un preț de plecare: de la €150 pentru design creativ, de la €250 pentru '
    'automatizare AI și de la €850 pentru web și produse digitale. Prețul final depinde de cerințe și îl '
    'primești într-o ofertă personalizată, cu preț fix, nu tarif orar.'),
   ('Cât durează un proiect?',
    'Între 7 și 21 de zile, în funcție de direcție și de complexitate: de la 7 zile pentru design creativ, '
    'de la 14 pentru automatizare AI și de la 21 pentru web și produse digitale. Termenul exact îl stabilim '
    'în ofertă, înainte să începem.'),
   ('Poți integra plăți online?',
    'Da. Integrările de plăți securizate pot include Stripe, PayPal și alți furnizori potriviți pentru '
    'regiunea ta.')]),
 ('web',
  'Web și sisteme',
  [('Construiești sisteme de rezervări?',
    'Da. Fluxurile de rezervări pot fi construite în jurul serviciilor tale, al regulilor de disponibilitate '
    'și al modului în care lucrează echipa ta.'),
   ('De ce Django și nu un website builder (Wix, Shopify etc.)?',
    'Django e stabil și verificat pe proiecte mari: nu se blochează când ai mai mulți vizitatori sau mai '
    'multe cereri deodată. Îmi permite să construiesc exact fluxul afacerii tale, nu să te forțez într-un '
    'șablon generic, ca la un website builder.'),
   ('Pot cere funcționalități personalizate?',
    'Absolut. Fiecare proiect poate fi construit în jurul procesului real al afacerii tale, nu forțat '
    'într-un instrument generic.'),
   ('Care e diferența dintre Portofoliu și Produse?',
    'Proiectele din Portofoliu sunt exemple din ce pot construi, fiecare cu eticheta ei: demo funcțional, '
    'produs propriu, instrument propriu sau concept. Nu sunt produse de vânzare. Plannerul de echilibru '
    'personal și trackerul de buget, din Produse, sunt produsele mele proprii, oferite direct.')]),
 ('ai',
  'Automatizare AI',
  [('Ce face mai exact automatizarea AI?',
    'Un asistent AI poate prelua telefonul și WhatsApp-ul afacerii tale: răspunde la întrebări despre servicii, '
    'prețuri și program, preia rezervări sau programări și le confirmă automat, non-stop.'),
   ('Îmi înlocuiește complet telefonul?',
    'Nu. Preia partea repetitivă, ca să nu mai ridici tu telefonul între doi clienți. Tu rămâi disponibil(ă) doar pentru '
    'situațiile care chiar au nevoie de tine, iar sistemul se integrează cu calendarul din proiectul ales.'),
   ('De ce există un cost lunar separat?',
    'Configurarea e o singură dată: de la €15 pentru o automatizare simplă și de la €25 pentru un asistent AI '
    'care preia și sortează cererile, ca extra la un proiect. Pe lângă asta, mai există un cost separat de '
    'utilizare, de câțiva euro până la câteva zeci de euro lunar, în funcție de volum, plătit direct '
    'firmelor care oferă tehnologia din spate, nu mie. Mentenanța lunară e opțională și separată.'),
   ('Se adaugă peste orice proiect?',
    'Da. Poți adăuga o automatizare simplă sau un asistent AI peste un proiect web, sau o poți cere separat, ca '
    'direcție de sine stătătoare, de la €250.')]),
 ('creativ',
  'Design creativ',
  [('Care e diferența dintre partea tehnică și partea creativă?',
    'Partea tehnică înseamnă web development (Django, Python, aplicații web, sisteme de rezervări), '
    'automatizare AI (asistenți AI, automatizări, integrări API) și arhitectura produsului, adică felul în care '
    'funcționează în spate. Partea creativă înseamnă identitate vizuală și branding, design pentru social '
    'media, campanii și materiale vizuale, direcție creativă. Identitatea vizuală este un serviciu creativ '
    'separat, nu o componentă a dezvoltării tehnice, iar cele două se pot combina într-un singur proiect.'),
   ('Ce înseamnă direcție creativă?',
    'Direcția creativă stabilește cum arată și cum sună brandul tău în toate materialele: alegeri de stil, '
    'ton și imagine, ca postările, campaniile și materialele să pară făcute de aceeași mână.'),
   ('Ce include un proiect creativ?',
    'Identitate vizuală și branding, design pentru social media, campanii și materiale vizuale, direcție '
    'creativă. Le aleg împreună, în funcție de ce are nevoie brandul tău. Textele sunt incluse în proiect, '
    'nu se vând separat.'),
   ('Pot cere doar partea creativă, fără un site sau un sistem?',
    'Da. Design creativ este un serviciu separat de partea tehnică. Se poate combina cu un site sau un '
    'sistem într-un singur proiect, dar nu depinde de ele.'),
   ('Cât costă și cât durează un proiect creativ?',
    'Pornește de la €150 și durează de la 7 zile. Pentru proiecte mai mari, cu volum mare de materiale sau o '
    'identitate construită de la zero, discutăm exact ce ai nevoie la primul mesaj și stabilim un preț fix, '
    'nu tarif orar.'),
   ('Pot vedea un exemplu înainte să decid?',
    'Da. În Portofoliu găsești concepte creative marcate „Concept”, ca să vezi tipul de lucru înainte să '
    'decizi.')])]
