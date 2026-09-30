#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CHAM_CMD_EM410X_SCAN             3000U
#define CHAM_CMD_EM410X_WRITE_TO_T55XX   3001U
#define CHAM_CMD_HIDPROX_SCAN             3002U
#define CHAM_CMD_HIDPROX_WRITE_TO_T55XX   3003U

#define CHAM_T55XX_EM_ID_LEN       5U
#define CHAM_T55XX_HID_DATA_LEN   13U
#define CHAM_T55XX_EM_PAYLOAD_LEN 17U
#define CHAM_T55XX_HID_PAYLOAD_LEN 25U

typedef enum {
    CHAM_T55XX_CRED_EM410X = 0,
    CHAM_T55XX_CRED_HIDPROX,
} cham_t55xx_credential_type_t;

bool cham_t55xx_build_em_payload(const uint8_t *credential, size_t credential_len,
                                 uint8_t *payload, size_t payload_capacity,
                                 size_t *payload_len);

bool cham_t55xx_build_hid_payload(const uint8_t *credential, size_t credential_len,
                                  uint8_t *payload, size_t payload_capacity,
                                  size_t *payload_len);

bool cham_t55xx_credential_matches(cham_t55xx_credential_type_t type,
                                   const uint8_t *expected, size_t expected_len,
                                   const uint8_t *actual, size_t actual_len);

#ifdef __cplusplus
}
#endif
