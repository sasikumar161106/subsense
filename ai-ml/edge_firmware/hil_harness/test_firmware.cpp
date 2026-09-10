/**
 * SubSense Layer 4 - Embedded Firmware Native Verification Runner
 * Validates TinyML memory constraints (<38KB SRAM), latency benchmark,
 * local neighbor radio corroboration, SPIFFS circular buffer rollover, and sync protocol.
 */

#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>

#include "../firmware/subsense_edge_tinyml.h"
#include "../firmware/mesh_corroboration.h"
#include "../firmware/spiffs_circular_buffer.h"
#include "../firmware/reconnection_sync.h"

static int s_tests_passed = 0;
static int s_tests_failed = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            fprintf(stderr, "FAIL: %s (line %d)\n", msg, __LINE__); \
            s_tests_failed++; \
        } else { \
            s_tests_passed++; \
        } \
    } while(0)

void test_tinyml_constraints(void) {
    printf("[TEST] Verifying TinyML SRAM footprint & latency benchmark...\n");
    bool init_ok = tinyml_init();
    TEST_ASSERT(init_ok, "TinyML init should succeed");

    size_t sram = tinyml_get_sram_footprint();
    printf("       Measured SRAM Footprint: %zu bytes (Constraint: < 38,912 bytes)\n", sram);
    TEST_ASSERT(sram < 38912, "SRAM footprint must be strictly < 38KB");

    // Nominal baseline input vector (12-D)
    float baseline_input[12] = {0.05f, 0.01f, 0.0f, 0.2f, 0.0f, 0.5f, 0.02f, 1.1f, 45.0f, 50.0f, 0.2f, 0.02f};
    TinyMLEdgeResult res1 = tinyml_infer(baseline_input);

    TEST_ASSERT(res1.anomaly_score >= 0.0f && res1.anomaly_score <= 1.0f, "Anomaly score must be in [0, 1]");
    TEST_ASSERT(res1.reconstruction_error >= 0.0f, "MSE must be non-negative");
    printf("       Simulated Xtensa LX7 Latency: %.2f ms (Reference: ~4.8 ms)\n", res1.estimated_latency_ms);
    TEST_ASSERT(res1.estimated_latency_ms >= 4.0f && res1.estimated_latency_ms <= 6.0f, "Latency matches ~4.8ms reference");
}

void test_mesh_corroboration_logic(void) {
    printf("[TEST] Verifying Edge Mesh Corroboration & Zero-Cloud Siren Actuation...\n");
    mesh_corroboration_init(4, 5);

    // Case A: High anomaly score, but single-channel spike (local_concordant_channels = 1)
    EdgeCorroborationDecision decA = mesh_corroboration_evaluate(0.88f, 1, 1000);
    TEST_ASSERT(!decA.siren_triggered, "Siren must NOT trigger on single-channel spike");
    TEST_ASSERT(!edge_get_siren_gpio_state(), "GPIO siren pin must remain LOW");

    // Case B: High anomaly, multi-channel concordant (2 channels), but isolated (no neighbors)
    EdgeCorroborationDecision decB = mesh_corroboration_evaluate(0.85f, 2, 1000);
    TEST_ASSERT(!decB.siren_triggered, "Siren must NOT trigger for isolated uncorroborated node");
    TEST_ASSERT(decB.local_corroborated_score < 0.30f, "Isolated score must be down-weighted by 0.25");

    // Case C: Receive neighbor packet within 80m (< 120m) and 5 minutes ago (< 45 min)
    MeshNeighborPacket neighbor;
    memset(&neighbor, 0, sizeof(neighbor));
    strncpy(neighbor.node_id, "SS-PANEL7-N041", 15);
    neighbor.rel_x_m = 50.0f;
    neighbor.rel_y_m = 40.0f; // sqrt(50^2 + 40^2) = 64m <= 120m
    neighbor.anomaly_score = 0.82f;
    neighbor.is_anomaly = true;
    neighbor.timestamp_sec = 800; // 200s ago
    neighbor.concordant_channels = 2;
    mesh_corroboration_receive_packet(&neighbor);

    // Now evaluate local node with concordant channels
    EdgeCorroborationDecision decC = mesh_corroboration_evaluate(0.85f, 2, 1000);
    TEST_ASSERT(decC.siren_triggered, "Siren MUST trigger when corroborated by active neighbor!");
    TEST_ASSERT(decC.strobe_triggered, "Strobe MUST trigger when corroborated!");
    TEST_ASSERT(edge_get_siren_gpio_state(), "GPIO siren pin must be HIGH");
    TEST_ASSERT(decC.corroborating_neighbors_count == 1, "Corroborating neighbor count must be 1");
    TEST_ASSERT(strcmp(decC.primary_corroborator, "SS-PANEL7-N041") == 0, "Primary corroborator matches");
}

void test_spiffs_buffer_and_sync(void) {
    printf("[TEST] Verifying SPIFFS circular buffer rollover & reconnection sync...\n");
    spiffs_buffer_init();

    // Fill buffer beyond 256 capacity (write 270 records) to verify circular FIFO rollover
    for (uint32_t i = 1; i <= 270; ++i) {
        SPIFFSEventRecord rec;
        memset(&rec, 0, sizeof(rec));
        rec.record_id = i;
        rec.timestamp_sec = 1000 + i;
        strncpy(rec.node_id, "SS-PANEL7-N042", 15);
        rec.anomaly_score = 0.75f;
        rec.reconstruction_error = 0.035f;
        rec.corroborated = true;
        rec.is_synced = false;
        spiffs_buffer_write(&rec);
    }

    TEST_ASSERT(spiffs_buffer_has_overflowed(), "Buffer must report overflow after 270 writes");
    TEST_ASSERT(spiffs_buffer_get_unsynced_count() == SPIFFS_BUFFER_CAPACITY, "Unsynced count equals capacity");

    // Initialize reconnection sync protocol
    reconnection_sync_init("SS-PANEL7-N042", "GW-PANEL7-01");
    TEST_ASSERT(reconnection_sync_get_state() == SYNC_STATE_OFFLINE_DISCONNECTED, "Starts disconnected");

    // Backhaul restored!
    reconnection_sync_set_backhaul_online(true);
    TEST_ASSERT(reconnection_sync_get_state() == SYNC_STATE_HANDSHAKE_REQUESTED, "Moves to handshake");

    // Process first chunk
    SyncBatchChunk chunk;
    bool chunk_ready = reconnection_sync_process(&chunk);
    TEST_ASSERT(chunk_ready, "Sync chunk should be generated");
    TEST_ASSERT(chunk.record_count == SYNC_CHUNK_BATCH_SIZE, "Chunk contains full batch size");
    TEST_ASSERT(reconnection_sync_get_state() == SYNC_STATE_WAITING_ACK, "Awaiting ACK");

    // Send ACK from cloud
    reconnection_sync_handle_ack(chunk.highest_record_id);
    TEST_ASSERT(reconnection_sync_get_state() == SYNC_STATE_STREAMING_CHUNKS, "Returns to streaming after ACK");
}

int main(void) {
    printf("==============================================================\n");
    printf("SubSense Layer 4 - Edge TinyML Firmware Native Test Harness\n");
    printf("Target Architecture: ESP32-S3 (Xtensa dual-core LX7 @ 240MHz)\n");
    printf("==============================================================\n");

    test_tinyml_constraints();
    test_mesh_corroboration_logic();
    test_spiffs_buffer_and_sync();

    printf("\n--------------------------------------------------------------\n");
    printf("RESULTS: %d passed, %d failed\n", s_tests_passed, s_tests_failed);
    printf("--------------------------------------------------------------\n");

    if (s_tests_failed > 0) {
        return 1;
    }
    printf("ALL EMBEDDED FIRMWARE VERIFICATIONS PASSED!\n");
    return 0;
}
