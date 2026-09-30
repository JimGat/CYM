#include "chameleon_t55xx.h"

#include <string.h>

/* These bytes intentionally match the current upstream ChameleonUltra client.
 * They are protocol-required write candidates, remain private to this codec,
 * and are never exposed to the UI or logging layer. */
static const uint8_t s_target_key[4] = {0x20, 0x20, 0x66, 0x66};
static const uint8_t s_candidate_keys[8] = {
    0x51, 0x24, 0x36, 0x48,
    0x19, 0x92, 0x04, 0x27,
};

static bool build_payload(const uint8_t *credential, size_t credential_len,
                          size_t required_credential_len,
                          uint8_t *payload, size_t payload_capacity,
                          size_t required_payload_len, size_t *payload_len)
{
    if (!credential || !payload || !payload_len ||
        credential_len != required_credential_len ||
        payload_capacity < required_payload_len) {
        return false;
    }

    memcpy(payload, credential, credential_len);
    memcpy(payload + credential_len, s_target_key, sizeof(s_target_key));
    memcpy(payload + credential_len + sizeof(s_target_key),
           s_candidate_keys, sizeof(s_candidate_keys));
    *payload_len = required_payload_len;
    return true;
}

bool cham_t55xx_build_em_payload(const uint8_t *credential, size_t credential_len,
                                 uint8_t *payload, size_t payload_capacity,
                                 size_t *payload_len)
{
    return build_payload(credential, credential_len, CHAM_T55XX_EM_ID_LEN,
                         payload, payload_capacity,
                         CHAM_T55XX_EM_PAYLOAD_LEN, payload_len);
}

bool cham_t55xx_build_hid_payload(const uint8_t *credential, size_t credential_len,
                                  uint8_t *payload, size_t payload_capacity,
                                  size_t *payload_len)
{
    return build_payload(credential, credential_len, CHAM_T55XX_HID_DATA_LEN,
                         payload, payload_capacity,
                         CHAM_T55XX_HID_PAYLOAD_LEN, payload_len);
}

bool cham_t55xx_credential_matches(cham_t55xx_credential_type_t type,
                                   const uint8_t *expected, size_t expected_len,
                                   const uint8_t *actual, size_t actual_len)
{
    size_t required_len;
    switch (type) {
    case CHAM_T55XX_CRED_EM410X:
        required_len = CHAM_T55XX_EM_ID_LEN;
        break;
    case CHAM_T55XX_CRED_HIDPROX:
        required_len = CHAM_T55XX_HID_DATA_LEN;
        break;
    default:
        return false;
    }

    return expected && actual && expected_len == required_len &&
           actual_len == required_len &&
           memcmp(expected, actual, required_len) == 0;
}
