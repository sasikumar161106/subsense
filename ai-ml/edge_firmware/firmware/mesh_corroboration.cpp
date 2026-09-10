/**
 * SubSense Layer 4 - Edge Mesh Corroboration Implementation
 * Hardware-autonomous siren and strobe actuation.
 */

#include "mesh_corroboration.h"
#include <math.h>
#include <string.h>

static MeshNeighborPacket s_neighbor_table[MAX_MESH_NEIGHBORS];
static size_t s_neighbor_count = 0;
static uint8_t s_siren_pin = 4;
static uint8_t s_strobe_pin = 5;
static bool s_siren_active = false;
static bool s_strobe_active = false;

void mesh_corroboration_init(uint8_t siren_gpio_pin, uint8_t strobe_gpio_pin) {
    s_siren_pin = siren_gpio_pin;
    s_strobe_pin = strobe_gpio_pin;
    s_siren_active = false;
    s_strobe_active = false;
    s_neighbor_count = 0;
    memset(s_neighbor_table, 0, sizeof(s_neighbor_table));
}

void mesh_corroboration_receive_packet(const MeshNeighborPacket* packet) {
    if (!packet) return;

    // Search for existing entry for this neighbor
    for (size_t i = 0; i < s_neighbor_count; ++i) {
        if (strncmp(s_neighbor_table[i].node_id, packet->node_id, 16) == 0) {
            s_neighbor_table[i] = *packet;
            return;
        }
    }

    // Add new neighbor if capacity remains or replace oldest
    if (s_neighbor_count < MAX_MESH_NEIGHBORS) {
        s_neighbor_table[s_neighbor_count++] = *packet;
    } else {
        // Evict first slot (FIFO)
        for (size_t i = 0; i < MAX_MESH_NEIGHBORS - 1; ++i) {
            s_neighbor_table[i] = s_neighbor_table[i + 1];
        }
        s_neighbor_table[MAX_MESH_NEIGHBORS - 1] = *packet;
    }
}

EdgeCorroborationDecision mesh_corroboration_evaluate(
    float local_anomaly_score,
    uint8_t local_concordant_channels,
    uint32_t current_time_sec
) {
    EdgeCorroborationDecision decision;
    memset(&decision, 0, sizeof(decision));

    // Rule 1: Within-node check: require concordant drift across >= 2 modalities
    if (local_concordant_channels < 2) {
        // Isolated single-channel spike -> Predictive Maintenance, no siren!
        decision.siren_triggered = false;
        decision.strobe_triggered = false;
        decision.local_corroborated_score = local_anomaly_score * 0.25f;
        s_siren_active = false;
        s_strobe_active = false;
        return decision;
    }

    // Rule 2: Across-node check: check neighbors within R <= 120m and tau <= 45 min (2700s)
    uint8_t corroborators = 0;
    char primary_node[16] = {0};

    for (size_t i = 0; i < s_neighbor_count; ++i) {
        const MeshNeighborPacket* n = &s_neighbor_table[i];
        float dist_m = sqrtf(n->rel_x_m * n->rel_x_m + n->rel_y_m * n->rel_y_m);

        if (dist_m <= NEIGHBOR_CORROBORATION_RADIUS_M) {
            uint32_t dt = (current_time_sec >= n->timestamp_sec) ?
                          (current_time_sec - n->timestamp_sec) :
                          (n->timestamp_sec - current_time_sec);

            if (dt <= NEIGHBOR_TEMPORAL_WINDOW_SEC && n->is_anomaly) {
                corroborators++;
                if (primary_node[0] == '\0') {
                    strncpy(primary_node, n->node_id, 15);
                }
            }
        }
    }

    decision.corroborating_neighbors_count = corroborators;
    strncpy(decision.primary_corroborator, primary_node, 15);

    if (corroborators == 0) {
        // Isolated single-node anomaly -> Down-weighted by 0.25, sirens suppressed
        decision.local_corroborated_score = local_anomaly_score * 0.25f;
        decision.siren_triggered = false;
        decision.strobe_triggered = false;
        s_siren_active = false;
        s_strobe_active = false;
    } else {
        // Confirmed regional subsidence!
        decision.local_corroborated_score = local_anomaly_score;
        if (local_anomaly_score >= 0.65f) {
            // ACTUATE HARDWIRED SIREN AND HIGH-DECIBEL HORN IMMEDIATELY
            decision.siren_triggered = true;
            decision.strobe_triggered = true;
            s_siren_active = true;
            s_strobe_active = true;
        }
    }

    return decision;
}

bool edge_get_siren_gpio_state(void) {
    return s_siren_active;
}

bool edge_get_strobe_gpio_state(void) {
    return s_strobe_active;
}
