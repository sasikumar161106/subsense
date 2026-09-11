/**
 * @file subsense_lora_mesh.h
 * @brief SubSense LoRa SX126x Multi-Hop Mesh Transport for Node -> Relay -> Gateway.
 * @note Replaces the WiFi ESP-NOW mesh with long-range Sub-GHz LoRa (865 MHz)
 *       using the SX126x driver and configs from the loramain project.
 *       Zero dynamic heap allocation, static reassembly buffers, hardware RSSI tracking.
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

/** Device role for this ESP32's LoRa radio. */
typedef enum {
    SUBSENSE_MESH_ROLE_NODE = 0,     /**< Sensor node: samples MPU6050, runs TinyML, transmits. */
    SUBSENSE_MESH_ROLE_GATEWAY = 1,  /**< Gateway: receives, reassembles, streams to Serial. */
    SUBSENSE_MESH_ROLE_RELAY = 2     /**< Relay: forwards packets with dedup & hop increment. */
} SubSenseMeshRole;

/**
 * @brief Callback invoked on GATEWAY when a complete JSON message is reassembled.
 * @param json_payload Null-terminated JSON string.
 * @param len           Length of json_payload in bytes.
 * @param sender_mac    6-byte MAC address of original sensor node.
 * @param rssi_dbm      Authentic hardware RSSI in dBm from SX126x.
 * @param hop_count     Number of wireless hops traversed.
 */
typedef void (*subsense_lora_rx_callback_t)(
    const char* json_payload,
    size_t len,
    const uint8_t sender_mac[6],
    int16_t rssi_dbm,
    uint8_t hop_count
);

/**
 * @brief Initialize the LoRa SX126x mesh transport.
 * @param role NODE, GATEWAY, or RELAY.
 * @param rx_callback Required for GATEWAY role (NULL for NODE and RELAY).
 * @return true on success, false if SX126x init failed.
 */
bool subsense_lora_mesh_init(SubSenseMeshRole role, subsense_lora_rx_callback_t rx_callback);

/**
 * @brief Send a JSON payload over LoRa mesh.
 *        Automatically fragments if payload exceeds 190 bytes.
 * @param json_payload Null-terminated JSON string to send.
 * @param len           Length of json_payload in bytes.
 * @return true if queued/transmitted successfully.
 */
bool subsense_lora_mesh_send(const char* json_payload, size_t len);

/**
 * @brief Housekeeping loop. Must be called in loop() on all roles.
 *        Polls incoming LoRa packets, manages relay forwarding,
 *        and expires stale reassembly slots.
 */
void subsense_lora_mesh_loop(void);

/**
 * @brief Returns true if LoRa mesh transport is initialized and ready.
 */
bool subsense_lora_mesh_is_ready(void);

/**
 * @brief Get local node's MAC address (6 bytes).
 */
const uint8_t* subsense_lora_mesh_get_mac(void);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_LORA_MESH_H
