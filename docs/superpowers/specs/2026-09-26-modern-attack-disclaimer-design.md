# Modern Attack Tile Disclaimer Design

## Purpose

Require an explicit legal and authorization acknowledgement before the Modern home layout opens its Attack category.

## Scope

- Change only the Modern home layout's `CAT:Attack` entry path.
- Reuse the existing `show_attack_warning()` popup rather than creating a second implementation.
- Keep Classic menu navigation unchanged.
- Keep the existing warning shown before individual active attacks; entering the category does not count as session-wide authorization.

## Interaction

When the user taps the Modern home screen's Attack tile:

1. Display the existing active-attack warning popup.
2. `Cancel` dismisses the popup and leaves the user on the Modern home screen.
3. `I Understand` dismisses the popup and opens `show_cat_attack()`.

The entry path is `show_attack_warning(show_cat_attack)`.

## Copy

Title:

`ACTIVE ATTACKS`

Message:

`These tools perform active attacks. Use them only with explicit authorization on networks or devices you own. Research and follow the laws that apply in your country.`

The message may use explicit line breaks for reliable portrait and landscape wrapping without changing its meaning.

## Layout

Retain the existing warning card, colors, warning symbols, Cancel button, and I Understand button. Adjust the card or message layout only if required to keep all copy and controls visible at supported portrait and landscape resolutions.

## Verification

A source contract must prove that:

- `CAT:Attack` invokes `show_attack_warning(show_cat_attack)` rather than opening the category directly.
- The popup title is `ACTIVE ATTACKS`.
- The message includes explicit authorization and applicable-country law guidance.
- The other Modern category routes remain direct and unchanged.

Because the callback and popup are compiled from canonical `ESP32C5/main/main.c`, all four release boards must pass the shared build gate before the firmware cycle is pushed. Hardware confirmation remains distinct from compilation.
