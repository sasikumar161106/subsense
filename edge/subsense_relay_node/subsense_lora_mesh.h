/**
 * @file subsense_lora_mesh.h
 * @brief SubSense LoRa SX126x Multi-Hop Mesh Transport for Node -> Relay -> Gateway.
 */

#ifndef SUBSENSE_LORA_MESH_H
#define SUBSENSE_LORA_MESH_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUBSENSE_MESH_MAX_PAYLOAD_LEN       512
#define SUBSENSE_MESH_MAX_CONCURRENT_MSGS   4
#define SUBSENSE_MESH_MAX_HOPS              3
#define SUBSENSE_LORA_FRAG_CHUNK_LEN        190
#define SUBSENSE_LORA_FRAG_HEADER_LEN       15

typedef enum {
    SUBSENSE_MESH_ROLE_NODE = 0,
    SUBSENSE_MESH_ROLE_GATEWAY = 1,
    SUBSENSE_MESH_ROLE_RELAY = 2
} SubSenseMeshRole;

typedef void (*subsense_lora_rx_callback_t)(
    const char* json_payload,
    size_t len,
    const uint8_t sender_mac[6],
    int16_t rssi_dbm,
    uint8_t hop_count
);

bool subsense_lora_mesh_init(SubSenseMeshRole role, subsense_lora_rx_callback_t rx_callback);
bool subsense_lora_mesh_send(const char* json_payload, size_t len);
void subsense_lora_mesh_loop(void);
bool subsense_lora_mesh_is_ready(void);
const uint8_t* subsense_lora_mesh_get_mac(void);

#ifdef __cplusplus
}
#endif

#endif
