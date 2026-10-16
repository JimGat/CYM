# Custom menu symbol font

`ESP32C5/main/lv_extra_symbols.c` uses the existing owner-supplied Font Awesome
Free solid/brands TTFs. Their name tables identify Font Awesome 6.7.2; this
change does not update the TTF version or refresh any existing glyph. Font
Awesome fonts are licensed under SIL OFL 1.1 (https://fontawesome.com/license/free).
Retain the upstream font copyright/license when obtaining or redistributing
TTFs. The TTFs are not duplicated into this repository.

`extra_symbols_recipe.json` pins both source TTF SHA-256 hashes, the complete
codepoint lists, 20px/4bpp/no-compress settings, and lv_font_conv 1.5.3 (MIT).
U+F030 camera comes from the solid font, not brands. Both QR menu layouts use
MY_SYMBOL_CAMERA with the existing lv_extra_symbols font and fallback setup.

Reproduce on the development host using the installed converter:

    python3 tools/generate_extra_symbols.py --converter /home/dev/.npm/_npx/b62fd1a864044392/node_modules/lv_font_conv/lv_font_conv.js --fonts /home/dev/projects/fonts

Alternatively obtain lv_font_conv@1.5.3 and pass its lv_font_conv.js path. The
script rejects changed source hashes or converter version and verifies every
requested codepoint has a nonempty production cmap/bitmap entry. It does not
hand-edit generated bitmap bytes. --output allows generation into scratch.

    python3 -m unittest discover -s tests -p test_qr_font309.py

The test resolves the generated sparse cmap and hashes each glyph's actual
4bpp pixels and metrics. It protects the 92 preexisting glyphs byte-for-byte,
requires the additional camera glyph (93 total), and checks both tile macros.
Physical rendering/orientation still requires owner screen verification.
