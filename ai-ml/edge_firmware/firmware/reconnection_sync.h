/**
 * SubSense Layer 4 - Reconnection Synchronization Protocol
 * Cloud backhaul restoration handshake and chunked flash backfill.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include "spiffs_circular_buffer.h"

#ifdef __cplusplus
extern "C" {
#endif

#define SYNC_CHUNK_BATCH_SIZE 8

typedef enum {
    SYNC_STATE_OFFLINE_DISCONNECTED = 0,
    SYNC_STATE_HANDSHAKE_REQUESTED,
    SYNC_STATE_STREAMING_CHUNKS,
    SYNC_STATE_WAITING_ACK,
    SYNC_STATE_SYNCHRONIZED_STEADY
} SyncProtocolState;

typedef struct {
    uint32_t chunk_sequence;
    size_t record_count;
    SPIFFSEventRecord records[SYNC_CHUNK_BATCH_SIZE];
    uint32_t highest_record_id;
} SyncBatchChunk;

/**
 * Initializes the reconnection synchronization protocol handler.
 */
void reconnection_sync_init(const char* node_id, const char* gateway_id);

/**
 * Updates connectivity status (cellular / satellite / Ethernet backhaul link).
 */
void reconnection_sync_set_backhaul_online(bool is_online);

/**
 * Advances protocol state machine. Returns true if a chunk is ready to transmit.
 */
bool reconnection_sync_process(SyncBatchChunk* out_chunk);

/**
 * Processes cloud ACK received from the analytical platform.
 */
void reconnection_sync_handle_ack(uint32_t acknowledged_record_id);

/**
 * Returns current protocol state.
 */
SyncProtocolState reconnection_sync_get_state(void);

#ifdef __cplusplus
}
#endif
