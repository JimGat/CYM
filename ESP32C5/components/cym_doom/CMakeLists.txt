# Requirements must be visible during IDF early dependency expansion, before
# generated CONFIG_BOARD_* exists. Only the two WS configs compile sources.
set(doom_sources)
set(doom_fragments)
if(CONFIG_BOARD_WS_C5_28 OR CONFIG_BOARD_WS_C5_35)
    set(doom_sources "doom_contracts.c" "doom_session.c" "doom_ui.c")
    set(doom_fragments "state.lf")
endif()
idf_component_register(SRCS ${doom_sources}
    INCLUDE_DIRS "include" PRIV_INCLUDE_DIRS "engine"
    LDFRAGMENTS ${doom_fragments}
    REQUIRES heap esp_timer freertos lvgl mbedtls)
if(NOT (CONFIG_BOARD_WS_C5_28 OR CONFIG_BOARD_WS_C5_35))
    return()
endif()
add_library(cym_doom_engine STATIC
    "engine/am_map.c"
    "engine/d_event.c"
    "engine/d_items.c"
    "engine/d_iwad.c"
    "engine/d_loop.c"
    "engine/d_main.c"
    "engine/d_mode.c"
    "engine/d_net.c"
    "engine/doomdef.c"
    "engine/doomgeneric.c"
    "engine/doomstat.c"
    "engine/dstrings.c"
    "engine/dummy.c"
    "engine/f_finale.c"
    "engine/f_wipe.c"
    "engine/g_game.c"
    "engine/hu_lib.c"
    "engine/hu_stuff.c"
    "engine/i_cdmus.c"
    "engine/i_endoom.c"
    "engine/i_input.c"
    "engine/i_joystick.c"
    "engine/i_scale.c"
    "engine/i_sound.c"
    "engine/i_system.c"
    "engine/i_timer.c"
    "engine/i_video.c"
    "engine/info.c"
    "engine/m_argv.c"
    "engine/m_bbox.c"
    "engine/m_cheat.c"
    "engine/m_config.c"
    "engine/m_controls.c"
    "engine/m_fixed.c"
    "engine/m_menu.c"
    "engine/m_misc.c"
    "engine/m_random.c"
    "engine/memio.c"
    "engine/mus2mid.c"
    "engine/p_ceilng.c"
    "engine/p_doors.c"
    "engine/p_enemy.c"
    "engine/p_floor.c"
    "engine/p_inter.c"
    "engine/p_lights.c"
    "engine/p_map.c"
    "engine/p_maputl.c"
    "engine/p_mobj.c"
    "engine/p_plats.c"
    "engine/p_pspr.c"
    "engine/p_saveg.c"
    "engine/p_setup.c"
    "engine/p_sight.c"
    "engine/p_spec.c"
    "engine/p_switch.c"
    "engine/p_telept.c"
    "engine/p_tick.c"
    "engine/p_user.c"
    "engine/r_bsp.c"
    "engine/r_data.c"
    "engine/r_draw.c"
    "engine/r_main.c"
    "engine/r_plane.c"
    "engine/r_segs.c"
    "engine/r_sky.c"
    "engine/r_things.c"
    "engine/s_sound.c"
    "engine/sha1.c"
    "engine/sounds.c"
    "engine/st_lib.c"
    "engine/st_stuff.c"
    "engine/statdump.c"
    "engine/tables.c"
    "engine/v_video.c"
    "engine/w_checksum.c"
    "engine/w_file.c"
    "engine/w_main.c"
    "engine/w_wad.c"
    "engine/wi_stuff.c"
    "engine/z_zone.c"
)
target_include_directories(cym_doom_engine PRIVATE "engine" "include")
target_link_libraries(cym_doom_engine PRIVATE idf::heap)
target_compile_options(cym_doom_engine PRIVATE
    -include "${CMAKE_CURRENT_LIST_DIR}/include/doom_runtime_shim.h"
    -msmall-data-limit=0 -fdata-sections -ffunction-sections -fno-common -fwrapv -fno-strict-aliasing
    -Werror=implicit-function-declaration)
target_link_libraries(${COMPONENT_LIB} PRIVATE cym_doom_engine)
# Native IDF state.lf records both engine reset ranges and lets IDF initialize
# external zero state before application startup. No supplemental INSERT script.
