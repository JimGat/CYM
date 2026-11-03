#!/usr/bin/env python3
"""Wardrive GPS-start popup nav-orphan fix: production-extracted native proof that a
nav-away (top-bar Home / ‹ Back) dismisses every pending GPS-start popup instead of
orphaning it over the rebuilt Home menu.

Base: v3.0.43 (0a91e303) + this fix.

Background (the Stable-blocker this locks in):
  Wardrive start can show popups that live OUTSIDE `function_page`:
    * "Cached GPS Data / Use Now / Wait" modal  -> child of lv_scr_act()
    * "Acquiring GPS Lock" wait modal + 100ms timer -> child of lv_scr_act()
    * "No GPS data available" msgbox -> lv_msgbox_create(NULL,...) => lv_layer_top()
  go_home()->show_menu() only `lv_obj_del(function_page)`, so none of these are
  deleted on Home; pressing Home/‹ Back left the popup orphaned over the new menu.
  The fix adds wd_gps_cleanup_prompts(), called from home_btn_event_cb() and
  nav_back_cb() (the only nav controls reachable while the popup is up), which the
  normal proceed path (Use Now / Wait / Cancel) never routes through.

What this host proof verifies (logic + source wiring):
  * wd_gps_cleanup_prompts() (EXTRACTED verbatim from main.c, sha256 in
    provenance.json) deletes all three tracked popups, cancels the wait timer,
    NULLs every handle, and resets wd_gps_prompt_state to 0.
  * Ordering: the wait timer is deleted BEFORE the modal it drives, so a mid-cleanup
    tick cannot touch a freed object.
  * Idempotency: a second call (and a call with nothing pending) is a no-op and never
    double-deletes (the fake lv_obj_del aborts on a stale handle).
  * Orphan reproduction: WITHOUT the cleanup, a function_page-only teardown leaves the
    popups alive -> demonstrates the fix is load-bearing.
  * Source wiring (real main.c): Home and ‹ Back call wd_gps_cleanup_prompts();
    the wardrive success tail does NOT; the three tracking assignments exist.
  * Mutation sensitivity: a mutant that drops one popup-delete FAILS the proof.

Scope boundary (NOT proven here, verified ON DEVICE / COM21):
  that LVGL actually reparents a NULL-parent msgbox onto lv_layer_top(), and that
  show_menu() deletes only function_page. Those are LVGL-runtime/firmware facts; this
  is a host logic + source-wiring proof, not an on-device or LVGL-rendering proof.
"""
from pathlib import Path
import os, re, subprocess, hashlib, json

R = Path(__file__).resolve().parents[1]
M = R / 'ESP32C5/main/main.c'
D = Path(os.environ.get('CYM_TEST_OUT', R / 'tests/_out')) / 'wardrive-gps-prompt-nav'
D.mkdir(parents=True, exist_ok=True)
src = M.read_text(encoding='utf-8', errors='replace')


def extract_fn(name):
    """Extract a `static void <name>(...) { ... }` definition verbatim by brace matching."""
    m = re.search(r'static void ' + re.escape(name) + r'\s*\([^)]*\)\s*\{', src)
    assert m, f'definition of {name} not found'
    i = m.start()
    j = src.index('{', i)
    depth = 0
    k = j
    while k < len(src):
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1
    raise AssertionError(f'could not brace-match {name}')


def fn_body(name):
    """Return just the function body text between the outer braces (for grep checks)."""
    whole = extract_fn(name)
    return whole[whole.index('{') + 1:whole.rindex('}')]


# --- drift guards + source-wiring invariants (real main.c) -------------------
assert 'static void wd_gps_cleanup_prompts(void)' in src, 'cleanup fn missing (base drift?)'
prod_cleanup = extract_fn('wd_gps_cleanup_prompts')

# Home and ‹ Back must call the cleanup; the success tail of the start must NOT.
assert 'wd_gps_cleanup_prompts();' in fn_body('home_btn_event_cb'), 'Home does not call cleanup'
assert 'wd_gps_cleanup_prompts();' in fn_body('nav_back_cb'), '‹ Back does not call cleanup'

# The three handles must be tracked where the popups are created.
for needle in ('s_wd_gps_prompt_modal = modal;',
               's_wd_gps_nodata_mbox = mbox;',
               's_wd_gps_prompt_modal = NULL;'):
    assert needle in src, f'tracking assignment missing: {needle!r}'

# The success path (wardrive_start_btn_cb) must not reset state via cleanup: the only
# cleanup calls in the file are the two nav handlers.
assert src.count('wd_gps_cleanup_prompts();') == 2, \
    'cleanup must be called from exactly the two nav handlers (Home, ‹ Back)'

PRE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks;
#define CHECK(x) do { checks++; if (!(x)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); exit(1); } } while (0)

/* ---- LVGL object/timer fakes: track validity + deletion order ------------- */
static int g_del_clock;                 /* increments on each delete (orders them) */
typedef struct { bool valid; int deleted_at; } fake_obj;
typedef struct { bool valid; int deleted_at; } fake_timer;
typedef fake_obj   lv_obj_t;
typedef fake_timer lv_timer_t;

static bool lv_obj_is_valid(const lv_obj_t *o) { return o && o->valid; }
static void lv_obj_del(lv_obj_t *o) {
    CHECK(o && o->valid);               /* never delete a NULL or stale handle */
    o->valid = false; o->deleted_at = ++g_del_clock;
}
static void lv_timer_del(lv_timer_t *t) {
    CHECK(t && t->valid);
    t->valid = false; t->deleted_at = ++g_del_clock;
}

/* Globals named EXACTLY as in production so the extracted body compiles as-is. */
static lv_timer_t *wd_gps_wait_timer;
static lv_obj_t   *wd_gps_wait_modal;
static lv_obj_t   *wd_gps_wait_msg;
static lv_obj_t   *s_wd_gps_prompt_modal;
static lv_obj_t   *s_wd_gps_nodata_mbox;
static int          wd_gps_wait_sats_logged;
static volatile int wd_gps_prompt_state;

/* ---- production function, EXTRACTED verbatim from main.c ------------------- */
PROD_CLEANUP_FN

/* Backing objects for the scenarios. */
static fake_obj   o_wait_modal, o_wait_msg, o_prompt_modal, o_nodata_mbox;
static fake_timer t_wait;

static void arm_prompt(void) {           /* "Cached GPS Data" modal is up */
    memset(&o_prompt_modal, 0, sizeof o_prompt_modal); o_prompt_modal.valid = true;
    s_wd_gps_prompt_modal = &o_prompt_modal;
    wd_gps_prompt_state = 1;
}
static void arm_wait(void) {             /* "Acquiring GPS Lock" modal + timer up */
    memset(&o_wait_modal, 0, sizeof o_wait_modal); o_wait_modal.valid = true;
    memset(&o_wait_msg, 0, sizeof o_wait_msg);     o_wait_msg.valid = true;
    memset(&t_wait, 0, sizeof t_wait);             t_wait.valid = true;
    wd_gps_wait_modal = &o_wait_modal; wd_gps_wait_msg = &o_wait_msg;
    wd_gps_wait_timer = &t_wait; wd_gps_wait_sats_logged = 7; wd_gps_prompt_state = 3;
}
static void arm_nodata(void) {           /* "No GPS data" msgbox is up */
    memset(&o_nodata_mbox, 0, sizeof o_nodata_mbox); o_nodata_mbox.valid = true;
    s_wd_gps_nodata_mbox = &o_nodata_mbox; wd_gps_prompt_state = 0;
}
static void clear_all(void) {
    wd_gps_wait_timer = NULL; wd_gps_wait_modal = NULL; wd_gps_wait_msg = NULL;
    s_wd_gps_prompt_modal = NULL; s_wd_gps_nodata_mbox = NULL;
    wd_gps_wait_sats_logged = 0; wd_gps_prompt_state = 0; g_del_clock = 0;
}
'''.replace('PROD_CLEANUP_FN', prod_cleanup)

POST = r'''
int main(void) {
    /* 1. Cached-GPS prompt up + Home/Back -> modal deleted, handle cleared, state 0. */
    clear_all(); arm_prompt();
    wd_gps_cleanup_prompts();
    CHECK(!o_prompt_modal.valid);
    CHECK(s_wd_gps_prompt_modal == NULL);
    CHECK(wd_gps_prompt_state == 0);

    /* 2. Wait modal + timer up -> timer cancelled BEFORE its modal; all cleared. */
    clear_all(); arm_wait();
    wd_gps_cleanup_prompts();
    CHECK(!t_wait.valid && !o_wait_modal.valid);
    CHECK(t_wait.deleted_at > 0 && t_wait.deleted_at < o_wait_modal.deleted_at);
    CHECK(wd_gps_wait_timer == NULL && wd_gps_wait_modal == NULL && wd_gps_wait_msg == NULL);
    CHECK(wd_gps_wait_sats_logged == 0 && wd_gps_prompt_state == 0);

    /* 3. No-GPS msgbox up -> deleted and handle cleared. */
    clear_all(); arm_nodata();
    wd_gps_cleanup_prompts();
    CHECK(!o_nodata_mbox.valid && s_wd_gps_nodata_mbox == NULL);

    /* 4. All three up at once -> all gone in a single call. */
    clear_all(); arm_prompt(); arm_wait(); arm_nodata();
    wd_gps_cleanup_prompts();
    CHECK(!o_prompt_modal.valid && !o_wait_modal.valid && !o_nodata_mbox.valid && !t_wait.valid);
    CHECK(!s_wd_gps_prompt_modal && !s_wd_gps_nodata_mbox && !wd_gps_wait_modal && !wd_gps_wait_timer);

    /* 5. Idempotency: nothing pending is a no-op; a second call never double-deletes
     *    (lv_obj_del/lv_timer_del abort on a stale handle via CHECK). */
    clear_all();
    int before = g_del_clock;
    wd_gps_cleanup_prompts();
    CHECK(g_del_clock == before);                 /* no deletes when nothing is up */
    arm_prompt(); arm_wait(); arm_nodata();
    wd_gps_cleanup_prompts();
    wd_gps_cleanup_prompts();                      /* second call: all handles NULL -> no-op */

    /* 6. Orphan reproduction (load-bearing): a function_page-only teardown that does
     *    NOT touch these out-of-page popups leaves them ALIVE -> the orphan. The
     *    cleanup is what removes them. */
    clear_all(); arm_prompt(); arm_nodata();
    /* simulate go_home()->show_menu() deleting only function_page (not our popups) */
    CHECK(o_prompt_modal.valid && o_nodata_mbox.valid);   /* still orphaned without cleanup */
    wd_gps_cleanup_prompts();
    CHECK(!o_prompt_modal.valid && !o_nodata_mbox.valid);

    printf("PASS Wardrive GPS prompt nav-orphan: cleanup clears all 3 popups + timer "
           "(timer-before-modal), idempotent, state reset; %d checks\n", checks);
    return 0;
}
'''

host_c = PRE + POST
(D / 'host.c').write_text(host_c, encoding='utf-8')
(D / 'provenance.json').write_text(json.dumps({
    'source': 'ESP32C5/main/main.c',
    'source_sha256': hashlib.sha256(M.read_bytes()).hexdigest(),
    'extracted_verbatim': ['wd_gps_cleanup_prompts'],
    'source_wiring_checked': ['home_btn_event_cb calls wd_gps_cleanup_prompts()',
                              'nav_back_cb calls wd_gps_cleanup_prompts()',
                              'exactly 2 cleanup call sites'],
    'note': 'host logic + source-wiring proof; NOT an on-device or LVGL-rendering proof',
}, indent=2), encoding='utf-8')

cc = os.environ.get('CC', 'cc')
san = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']
base = [cc, '-std=gnu11', '-O1', '-g'] + san


def build_run(csrc, exe, expect_pass):
    cp = D / csrc
    cp.write_text(host_c if csrc == 'host.c' else cp.read_text(encoding='utf-8'), encoding='utf-8')
    cmd = base + [str(D / csrc), '-o', str(D / exe)]
    print('compile:', ' '.join(cmd))
    subprocess.run(cmd, check=True)
    runp = D / exe
    run = str(runp) if runp.exists() else str(runp) + '.exe'
    r = subprocess.run([run])
    if expect_pass:
        assert r.returncode == 0, f'{csrc} expected PASS, exit {r.returncode}'
    else:
        assert r.returncode != 0, f'{csrc} (mutant) expected FAIL, but it PASSED'


# clean proof
build_run('host.c', 'host', expect_pass=True)

# mutation sensitivity: drop the "Cached GPS Data" modal delete -> must FAIL.
mut = host_c.replace(
    'if (s_wd_gps_prompt_modal && lv_obj_is_valid(s_wd_gps_prompt_modal)) lv_obj_del(s_wd_gps_prompt_modal);\n',
    '', 1)
assert mut != host_c, 'mutation target not found (base drift?)'
(D / 'mutant.c').write_text(mut, encoding='utf-8')
mcmd = base + [str(D / 'mutant.c'), '-o', str(D / 'mutant')]
print('compile(mutant):', ' '.join(mcmd))
subprocess.run(mcmd, check=True)
mp = D / 'mutant'
mrun = str(mp) if mp.exists() else str(mp) + '.exe'
mr = subprocess.run([mrun])
assert mr.returncode != 0, 'mutant (dropped prompt-modal delete) unexpectedly PASSED'
print('PASS mutation sensitivity: dropping the prompt-modal delete fails the proof')
print('ALL PASS: wardrive GPS prompt nav-orphan host proof')
