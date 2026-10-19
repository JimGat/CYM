# Installed C5 slot selection for the RTA timing harness (not hardware emulation).
from pathlib import Path
import hashlib, json, re

def prepare(out, sdk):
    root=Path(sdk)/'components'
    hal=(root/'esp_hal_i2s/i2s_hal.c').read_text()
    ll=(root/'esp_hal_i2s/esp32c5/include/hal/i2s_ll.h').read_text()
    header=(root/'esp_driver_i2s/include/driver/i2s_std.h').read_text()
    def body(text, signature):
        a=text.index(signature); start=text.index('{',a); depth=1; b=start+1
        while depth:
            depth+=(text[b]=='{')-(text[b]=='}');b+=1
        return text[a:b]
    selected=[body(ll,'static inline void i2s_ll_'+d+'_select_std_slot(') for d in ('tx','rx')]
    selected += [body(hal,'void i2s_hal_std_set_'+d+'_slot(') for d in ('tx','rx')]
    implemented={'i2s_ll_tx_select_std_slot','i2s_ll_rx_select_std_slot','i2s_ll_tx_set_active_chan_mask','i2s_ll_rx_set_active_chan_mask'}
    calls=set(re.findall(r'\b(i2s_ll_\w+)\(', '\n'.join(selected)))-implemented
    # Actual channel masks determine the modeled DMA producer rate.
    # Unrelated register writes are inert, not hardware qualification.
    pre='#define SOC_I2S_HW_VERSION_1 0\n#define SOC_I2S_HW_VERSION_2 1\ntypedef int i2s_std_slot_mask_t;\ntypedef struct { struct {unsigned tx_tdm_tot_chan_num;}tx_tdm_ctrl; struct {unsigned rx_tdm_tot_chan_num;}rx_tdm_ctrl; unsigned tx_mask,rx_mask;} i2s_dev_t;\ntypedef struct {i2s_dev_t *dev;} i2s_hal_context_t;\ntypedef struct {int data_bit_width,slot_bit_width,slot_mode;struct {int slot_mask,ws_width;bool ws_pol,bit_shift,msb_right,left_align,big_endian,bit_order_lsb;}std;}i2s_hal_slot_config_t;\nstatic void i2s_ll_tx_set_active_chan_mask(i2s_dev_t*d,unsigned mask){d->tx_mask=mask;}\nstatic void i2s_ll_rx_set_active_chan_mask(i2s_dev_t*d,unsigned mask){d->rx_mask=mask;}\n'
    pre+='\n'.join('#define '+n+'(...) ((void)0)' for n in sorted(calls))+'\n'
    (out/'sdk-slots.c').write_text(pre+'\n'.join(selected))
    a=header.rindex('#define I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(');b=header.index('\n}',a)+2
    macro=header[a:b]
    (out/'sdk-slot-provenance.json').write_text(json.dumps(dict(hal_sha256=hashlib.sha256(hal.encode()).hexdigest(),ll_sha256=hashlib.sha256(ll.encode()).hexdigest(),header_sha256=hashlib.sha256(header.encode()).hexdigest(),function_sha256=[hashlib.sha256(f.encode()).hexdigest() for f in selected],model='C5 TRM 35.10.1.1: each enabled RX TDM channel enters FIFO; driver allocates mono-size DMA from slot_mode. Actual HAL/LL selection bodies; other register writes inert.'),indent=2))
    return macro
