#pragma once
#include <stdbool.h>
#include <stdint.h>
// Runtime-only four-HAT policy. Boot allows TX; never controls Wi-Fi/BLE/AP/NVS.
typedef enum { HAT_TX_CC1101, HAT_TX_NRF24, HAT_TX_IR, HAT_TX_RF433, HAT_TX_COUNT } hat_tx_id_t;
typedef enum { HAT_TX_READY, HAT_TX_ACTIVE, HAT_TX_QUIESCING, HAT_TX_ERROR, HAT_TX_STOPPED } hat_tx_state_t;
typedef struct { hat_tx_id_t id; uint32_t generation; } hat_tx_ticket_t;
typedef struct { bool inhibit; hat_tx_state_t state[HAT_TX_COUNT]; } hat_tx_snapshot_t;
bool hat_tx_begin(hat_tx_id_t id, hat_tx_ticket_t *ticket);
bool hat_tx_valid(hat_tx_ticket_t ticket);
// Enter/leave brackets hardware requests. Registered requests prevent premature ACK.
bool hat_tx_enter(hat_tx_ticket_t ticket);
void hat_tx_leave(hat_tx_ticket_t ticket);
void hat_tx_cancel(hat_tx_id_t id);
void hat_tx_inhibit(bool requested);
void hat_tx_finish(hat_tx_ticket_t ticket, bool checked_stopped);
bool hat_tx_claim_stop(hat_tx_id_t id, hat_tx_ticket_t *ticket);
bool hat_tx_owned(hat_tx_id_t id);
hat_tx_snapshot_t hat_tx_snapshot(void);
