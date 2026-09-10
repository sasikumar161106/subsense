/**
 * SubSense Layer 4 - Edge Mesh Corroboration & Zero-Cloud Emergency Siren Trigger
 * Direct 802.15.4 / ESP-NOW radio packet evaluation.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_MESH_NEIGHBORS 16
#define NEIGHBOR_CORROBORATION_RADIUS_M 120.0f
#define NEIGHBOR_TEMPORAL_WINDOW_SEC 2700 // 45 minutes

typedef struct {
    char node_id[16];
    float rel_x_m;             // Relative X distance from local node in meters
    float rel_y_m;             // Relative Y distance from local node in meters
    float anomaly_score;       // Neighbor's anomaly score
    bool is_anomaly;           // True if neighbor triggered anomaly
    uint32_t timestamp_sec;    // Mesh epoch seconds
    uint8_t concordant_channels;
} MeshNeighborPacket;

typedef struct {
    bool siren_triggered;          // Immediate hardwired GPIO relay output
    bool strobe_triggered;         // High-intensity flashing strobe output
    float local_corroborated_score;
    uint8_t corroborating_neighbors_count;
    char primary_corroborator[16];
} EdgeCorroborationDecision;

/**
 * Initializes the edge mesh corroboration engine and sets GPIO pins.
 */
void mesh_corroboration_init(uint8_t siren_gpio_pin, uint8_t strobe_gpio_pin);

/**
 * Ingests an incoming direct radio packet from a neighboring mesh node.
 */
void mesh_corroboration_receive_packet(const MeshNeighborPacket* packet);

/**
 * Evaluates local anomaly against recent neighbor radio packets.
 * If corroborated within R <= 120m and tau <= 45 min, immediately actuates sirens.
 */
EdgeCorroborationDecision mesh_corroboration_evaluate(
    float local_anomaly_score,
    uint8_t local_concordant_channels,
    uint32_t current_time_sec
);

/**
 * Directly queries hardware GPIO pin states.
 */
bool edge_get_siren_gpio_state(void);
bool edge_get_strobe_gpio_state(void);

#ifdef __cplusplus
}
#endif
