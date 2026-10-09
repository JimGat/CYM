# Source and licensing notice

The actual C engine is derived from rear16/ESP-DOOM commit
92bd5c3968197683041e7917e5f9e709164ba1fd, itself carrying id Software,
Simon Howard / Chocolate Doom, doomgeneric and other original contributor
copyright notices. Original file notices are retained. LICENSE.engine is
GPL version 2; the engine notices allow version 2 or later. New native CYM
adapter files in this component are distributed under GPL-2.0-or-later.
No warranty, including merchantability or fitness, is provided.

PROVENANCE.json gives exact upstream and current source hashes. The actual
complete imported-file changes from that pinned upstream are distributed as
patches/native-cym.patch (not a stale private checkpoint or probe-only patch).
All imported source, native adapters, linker scripts and CMake build instructions
are present here. The matching full firmware source and build scripts are in
the same JimGat/CYM commit as the binaries. Recipients must receive corresponding
source at that exact commit, not merely a pointer to moving main. Publish the
source commit before exposing its beta binary URLs. A GitHub source archive at
https://github.com/JimGat/CYM/archive/<firmware-commit>.tar.gz provides the matching
tracked source; scripts/build.sh and the checked-in SDK defaults govern builds
with ESP-IDF v6.0.2 and managed dependency specifications. Dependencies retain
their original licenses; this notice does not erase or relicense third-party
copyright. The combined GPL-linked distribution must preserve GPL obligations.

No WAD or commercial game assets are embedded in or committed to this firmware
repository. Official Freedoom Phase 1 v0.13.0 is separately supplied on the
CYM-SD-Assets feature/doom-sd-assets branch, with its permissive license and
credits. The runtime accepts only that exact SHA256, not arbitrary commercial
IWADs or mods. No audio, shell, networking or external controller is added by
the game engine.
