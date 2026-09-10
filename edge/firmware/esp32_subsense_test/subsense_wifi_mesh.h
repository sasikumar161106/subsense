/**
 * @file subsense_wifi_mesh.h
 * @brief SubSense WiFi Mesh Transport (ESP-NOW based) for Node -> Gateway relay.
 * @note Replaces the LoRa mesh backbone for prototype/demo hardware.
 *       Uses ESP32's built-in WiFi radio via ESP-NOW (no router/AP required,
 *       no pairing needed since broadcast mode is used).
 *       Zero dynamic heap allocation, static reassembly buffers only,
 *       consistent with the rest of the SubSense firmware.
 *
 * Usage:
 *   NODE role   : subsense_wifi_mesh_init(SUBSENSE_MESH_ROLE_NODE, NULL);
 *                 subsense_wifi_mesh_send(json_buf, json_len);
 *
 *   GATEWAY role: subsense_wifi_mesh_init(SUBSENSE_MESH_ROLE_GATEWAY, my_rx_handler);
 *                 // my_rx_handler(const char* json, size_t len, const uint8_t mac[6])
 *                 // is invoked automatically whenever a full JSON event/health
 *                 // payload has been received and reassembled from a node.
 */

#ifndef SUBSENSE_WIFI_MESH_H
#define SUBSENSE_WIFI_MESH_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Maximum JSON payload this transport can carry per message (matches
 *  SUBSENSE_JSON_EVENT_MAX_LEN in subsense_inference_engine.h). */
#define SUBSENSE_MESH_MAX_PAYLOAD_LEN     512

/** Max number of concurrent in-flight senders the gateway can reassemble
 *  fragments from at once. Increase if you deploy more than 4 nodes. */
#define SUBSENSE_MESH_MAX_CONCURRENT_MSGS 4

/** Maximum number of hops a message may be relayed before being dropped.
 *  Prevents forwarding loops and bounds propagation delay. */
#define SUBSENSE_MESH_MAX_HOPS 3

/** Device role for this ESP32's radio. */
typedef enum {
    SUBSENSE_MESH_ROLE_NODE = 0,     /**< Sensor node: sends only, no sensor attached to relay. */
    SUBSENSE_MESH_ROLE_GATEWAY = 1,  /**< Gateway: receives and reassembles full messages. */
    SUBSENSE_MESH_ROLE_RELAY = 2     /**< Relay: no sensor, just forwards packets it overhears
                                          one hop further, extending range between Node and
                                          Gateway. This is what makes the network a real
                                          multi-hop mesh instead of a star. */
} SubSenseMeshRole;

/**
 * @brief Callback invoked on the GATEWAY when a full JSON message has been
 *        received and reassembled from a node.
 * @param json_payload Null-terminated JSON string (event or health telemetry).
 * @param len           Length of json_payload in bytes (excluding null terminator).
 * @param sender_mac    6-byte MAC address of the sending node.
 */
typedef void (*subsense_mesh_rx_callback_t)(
    const char* json_payload,
    size_t len,
    const uint8_t sender_mac[6]
);

/**
 * @brief Initialize the WiFi mesh transport.
 * @param role        NODE, GATEWAY, or RELAY.
 * @param rx_callback Required for GATEWAY role. Ignored (pass NULL) for
 *                    NODE and RELAY roles -- a relay forwards packets
 *                    automatically and does not need application-level
 *                    reassembly.
 * @return true on success, false if WiFi/ESP-NOW init failed.
 */
bool subsense_wifi_mesh_init(SubSenseMeshRole role, subsense_mesh_rx_callback_t rx_callback);

/**
 * @brief Send a JSON payload (event or health telemetry) over the mesh.
 *        Only valid when initialized with SUBSENSE_MESH_ROLE_NODE.
 *        Automatically fragments payloads larger than one ESP-NOW packet
 *        (~240 usable bytes) and reassembles transparently on the gateway.
 * @param json_payload Null-terminated JSON string to send.
 * @param len           Length of json_payload in bytes (excluding null terminator).
 * @return true if the payload was queued/sent successfully, false otherwise
 *         (e.g. len exceeds SUBSENSE_MESH_MAX_PAYLOAD_LEN).
 */
bool subsense_wifi_mesh_send(const char* json_payload, size_t len);

/**
 * @brief Optional housekeeping call. Safe to call every loop() iteration
 *        on any role. On GATEWAY, expires stale partial reassembly slots.
 *        On RELAY, ages out old dedup-cache entries. No-op on NODE.
 */
void subsense_wifi_mesh_loop(void);

/**
 * @brief Returns true if the mesh transport initialized successfully.
 */
bool subsense_wifi_mesh_is_ready(void);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_WIFI_MESH_H
