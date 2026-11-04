Fonts used only to draw the share cards of the project pages (website/share_card.py).

  Fraunces         titles      SIL Open Font License 1.1
  Hanken Grotesk   text        SIL Open Font License 1.1
  DM Mono          labels      SIL Open Font License 1.1

These are the same woff2 files the site serves from static/website/fonts/
(latin and latin-ext subsets, from Google Fonts), converted to plain TrueType
(.ttf) without changing any glyph, because Pillow cannot read woff2.
The conversion was done once with fontTools: TTFont(woff2).flavor = None, then save().
The OFL allows this, as long as the fonts are not sold on their own and keep
their names (see static/website/fonts/README.txt for the licence note).
