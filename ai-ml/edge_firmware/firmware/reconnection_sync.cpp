/**
 * SubSense Layer 4 - Reconnection Synchronization Protocol Implementation
 */

#include "reconnection_sync.h"
#include <string.h>

static SyncProtocolState s_state = SYNC_STATE_OFFLINE_DISCONNECTED;
static char s_node_id[32] = {0};
static char s_gateway_id[32] = {0};
static uint32_t s_chunk_seq = 0;
static uint32_t s_last_sent_highest_id = 0;

void reconnection_sync_init(const char* node_id, const char* gateway_id) {
    s_state = SYNC_STATE_OFFLINE_DISCONNECTED;
    s_chunk_seq = 0;
    s_last_sent_highest_id = 0;
    if (node_id) strncpy(s_node_id, node_id, 31);
    if (gateway_id) strncpy(s_gateway_id, gateway_id, 31);
}

void reconnection_sync_set_backhaul_online(bool is_online) {
    if (is_online) {
        if (s_state == SYNC_STATE_OFFLINE_DISCONNECTED) {
            s_state = SYNC_STATE_HANDSHAKE_REQUESTED;
        }
    } else {
        s_state = SYNC_STATE_OFFLINE_DISCONNECTED;
    }
}

bool reconnection_sync_process(SyncBatchChunk* out_chunk) {
    if (!out_chunk) return false;

    if (s_state == SYNC_STATE_HANDSHAKE_REQUESTED) {
        // Handshake transition
        s_state = SYNC_STATE_STREAMING_CHUNKS;
    }

    if (s_state == SYNC_STATE_STREAMING_CHUNKS) {
        size_t unsynced = spiffs_buffer_get_unsynced_count();
        if (unsynced == 0) {
            s_state = SYNC_STATE_SYNCHRONIZED_STEADY;
            return false;
        }

        memset(out_chunk, 0, sizeof(SyncBatchChunk));
        out_chunk->chunk_sequence = ++s_chunk_seq;
        size_t fetched = spiffs_buffer_peek_unsynced(out_chunk->records, SYNC_CHUNK_BATCH_SIZE);
        out_chunk->record_count = fetched;

        uint32_t max_id = 0;
        for (size_t i = 0; i < fetched; ++i) {
            if (out_chunk->records[i].record_id > max_id) {
                max_id = out_chunk->records[i].record_id;
            }
        }
        out_chunk->highest_record_id = max_id;
        s_last_sent_highest_id = max_id;

        s_state = SYNC_STATE_WAITING_ACK;
        return true;
    }

    return false;
}

void reconnection_sync_handle_ack(uint32_t acknowledged_record_id) {
    if (s_state == SYNC_STATE_WAITING_ACK) {
        spiffs_buffer_mark_synced_up_to(acknowledged_record_id);

        if (spiffs_buffer_get_unsynced_count() > 0) {
            s_state = SYNC_STATE_STREAMING_CHUNKS;
        } else {
            s_state = SYNC_STATE_SYNCHRONIZED_STEADY;
        }
    }
}

SyncProtocolState reconnection_sync_get_state(void) {
    return s_state;
}
