#pragma once
/* Main-owner, copied labels only: no retained result pointer/timer/callback.
 * A bounded scrollable flex-column parent reflows these same rows on every
 * board and both home styles. Missing DIS fields are normal, not walk errors. */
static inline void gw_metadata_row(lv_obj_t *parent,const char *text,lv_color_t color)
{
    lv_obj_t *l=lv_label_create(parent);
    lv_label_set_text(l,text);
    lv_obj_set_style_text_color(l,color,0);
    lv_obj_set_style_text_font(l,&lv_font_montserrat_12,0);
    lv_label_set_long_mode(l,LV_LABEL_LONG_WRAP);
    lv_obj_set_width(l,lv_pct(100));
}
static inline void gw_metadata_rows(lv_obj_t *parent,const gw_result_t *r,lv_color_t color)
{
    char text[128];
    if(r->metadata_available)
        snprintf(text,sizeof(text),"Metadata FP: %.16s",r->metadata_fingerprint);
    else snprintf(text,sizeof(text),"Metadata FP: unavailable (no identifying bytes)");
    gw_metadata_row(parent,text,color);
    snprintf(text,sizeof(text),"Name: %s; manufacturer: %s; model: %s",
        r->metadata_name_source==1?"GATT":r->metadata_name_source==2?"advertised":"absent",
        r->metadata_fields&2?"observed":"absent/unreadable",
        r->metadata_fields&4?"observed":"absent/unreadable");
    gw_metadata_row(parent,text,color);
    gw_metadata_row(parent,"Correlation hint, not identity. Read completion unknown; capped reads may be partial. Full SHA256 in SD JSON.",color);
}
