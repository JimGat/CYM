/* Read-only boot sentinels shared by every canonical board. */
#ifndef CYM_SD_STARTUP_CHECK_H
#define CYM_SD_STARTUP_CHECK_H
static const char *const sd_startup_paths[] = {
    "/sdcard/lab/deauths", "/sdcard/lab/gattwalker", "/sdcard/lab/otsurvey"
};
static inline unsigned sd_startup_missing_dirs(void)
{
    unsigned missing = 0;
    for (unsigned i = 0; i < 3; i++) {
        struct stat st;
        if (stat(sd_startup_paths[i], &st) != 0 || !S_ISDIR(st.st_mode))
            missing |= 1u << i;
    }
    return missing;
}
#endif
