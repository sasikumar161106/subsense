/**
 * @file subsense_wifi_mesh.cpp
 * @brief Implementation of the SubSense WiFi Mesh Transport using ESP-NOW.
 * @note Requires the Arduino ESP32 core (WiFi.h + esp_now.h).
 *       Build this file alongside your existing .c firmware files -- the
 *       header uses extern "C" so subsense_app.c can call these functions
 *       directly even though this file is compiled as C++.
 */

#include "subsense_wifi_mesh.h"

#include <WiFi.h>
#include <esp_now.h>
#include <string.h>

// ---------------------------------------------------------------------------
// Internal constants
// ---------------------------------------------------------------------------

// ESP-NOW's practical single-packet payload limit is 250 bytes. We reserve a
// small header per fragment and stay well under that for safety margin.
// Header grew from 8 to 15 bytes (added hop_count + origin_mac for relaying).
// Chunk length stays at 200 -- 200 + 15 = 215 bytes, still comfortably under
// ESP-NOW's ~250-byte single-packet limit.
#define SUBSENSE_MESH_FRAG_HEADER_LEN   15
#define SUBSENSE_MESH_FRAG_CHUNK_LEN    200
#define SUBSENSE_MESH_FRAGMENT_TIMEOUT_MS 5000

static const uint8_t SUBSENSE_MESH_MAGIC = 0xA5;
static const uint8_t SUBSENSE_BROADCAST_MAC[6] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };

// Wire format for each ESP-NOW packet (fits within the 250-byte ESP-NOW cap).
typedef struct __attribute__((packed)) {
    uint8_t  magic;         // SUBSENSE_MESH_MAGIC marker, sanity check
    uint8_t  msg_id;        // increments per full logical message from this sender
    uint8_t  chunk_index;   // 0-based index of this fragment
    uint8_t  total_chunks;  // total number of fragments in this message
    uint16_t total_len;     // total length of the full reassembled payload
    uint16_t chunk_len;     // length of the payload bytes in this fragment
    uint8_t  hop_count;     // incremented by each relay; dropped past SUBSENSE_MESH_MAX_HOPS
    uint8_t  origin_mac[6]; // MAC of the ORIGINAL sending node (survives relaying)
    uint8_t  payload[SUBSENSE_MESH_FRAG_CHUNK_LEN];
} SubSenseMeshPacket;

// Small ring of recently-seen (origin_mac, msg_id, chunk_index) tuples so a
// relay never forwards the same fragment twice -- prevents broadcast storms.
#define SUBSENSE_MESH_DEDUP_CACHE_SIZE 16
#define SUBSENSE_MESH_DEDUP_TIMEOUT_MS 8000

typedef struct {
    bool     in_use;
    uint8_t  origin_mac[6];
    uint8_t  msg_id;
    uint8_t  chunk_index;
    uint32_t seen_at_ms;
} SubSenseMeshDedupEntry;

static SubSenseMeshDedupEntry s_dedup_cache[SUBSENSE_MESH_DEDUP_CACHE_SIZE];
static int s_dedup_next_slot = 0;

// Static per-sender reassembly slot (no heap allocation).
typedef struct {
    bool     in_use;
    uint8_t  sender_mac[6];
    uint8_t  msg_id;
    uint8_t  chunks_received;
    uint8_t  total_chunks;
    uint32_t received_chunk_mask;
    uint16_t total_len;
    uint32_t last_update_ms;
    char     buffer[SUBSENSE_MESH_MAX_PAYLOAD_LEN];
} SubSenseMeshReassemblySlot;

// ---------------------------------------------------------------------------
// Module state (static, no heap)
// ---------------------------------------------------------------------------

static SubSenseMeshRole              s_role        = SUBSENSE_MESH_ROLE_NODE;
static subsense_mesh_rx_callback_t   s_rx_callback = NULL;
static SubSenseMeshReassemblySlot    s_slots[SUBSENSE_MESH_MAX_CONCURRENT_MSGS];
static uint8_t                       s_next_msg_id = 0;
static bool                          s_ready       = false;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

static int find_slot_for_sender(const uint8_t mac[6], uint8_t msg_id) {
    for (int i = 0; i < SUBSENSE_MESH_MAX_CONCURRENT_MSGS; i++) {
        if (s_slots[i].in_use &&
            s_slots[i].msg_id == msg_id &&
            memcmp(s_slots[i].sender_mac, mac, 6) == 0) {
            return i;
        }
    }
    return -1;
}

static int allocate_slot(const uint8_t mac[6], uint8_t msg_id, uint16_t total_len, uint8_t total_chunks) {
    // Prefer an empty slot; otherwise evict the oldest (simple round-robin safety net).
    int chosen = -1;
    uint32_t oldest_ts = UINT32_MAX;
    for (int i = 0; i < SUBSENSE_MESH_MAX_CONCURRENT_MSGS; i++) {
        if (!s_slots[i].in_use) {
            chosen = i;
            break;
        }
        if (s_slots[i].last_update_ms < oldest_ts) {
            oldest_ts = s_slots[i].last_update_ms;
            chosen = i;
        }
    }
    if (chosen < 0) return -1;

    SubSenseMeshReassemblySlot* slot = &s_slots[chosen];
    slot->in_use = true;
    memcpy(slot->sender_mac, mac, 6);
    slot->msg_id = msg_id;
    slot->chunks_received = 0;
    slot->total_chunks = total_chunks;
    slot->received_chunk_mask = 0;
    slot->total_len = total_len;
    slot->last_update_ms = millis();
    memset(slot->buffer, 0, sizeof(slot->buffer));
    return chosen;
}

// Returns true if we've already seen (and presumably already forwarded)
// this exact fragment recently -- prevents relay broadcast storms.
static bool dedup_seen_before(const uint8_t origin_mac[6], uint8_t msg_id, uint8_t chunk_index) {
    uint32_t now = millis();
    for (int i = 0; i < SUBSENSE_MESH_DEDUP_CACHE_SIZE; i++) {
        if (!s_dedup_cache[i].in_use) continue;
        if ((now - s_dedup_cache[i].seen_at_ms) > SUBSENSE_MESH_DEDUP_TIMEOUT_MS) {
            s_dedup_cache[i].in_use = false; // expired, treat as free
            continue;
        }
        if (s_dedup_cache[i].msg_id == msg_id &&
            s_dedup_cache[i].chunk_index == chunk_index &&
            memcmp(s_dedup_cache[i].origin_mac, origin_mac, 6) == 0) {
            return true;
        }
    }
    return false;
}

static void dedup_remember(const uint8_t origin_mac[6], uint8_t msg_id, uint8_t chunk_index) {
    SubSenseMeshDedupEntry* e = &s_dedup_cache[s_dedup_next_slot];
    e->in_use = true;
    memcpy(e->origin_mac, origin_mac, 6);
    e->msg_id = msg_id;
    e->chunk_index = chunk_index;
    e->seen_at_ms = millis();
    s_dedup_next_slot = (s_dedup_next_slot + 1) % SUBSENSE_MESH_DEDUP_CACHE_SIZE;
}

// ESP-NOW receive callback. Behavior branches by role:
//   GATEWAY -> reassemble fragments into a full JSON message, fire callback.
//   RELAY   -> forward the packet one more hop (with dedup + hop-count guard).
//   NODE    -> no callback registered, nodes only send.
// Signature matches the modern esp_now.h API (IDF/Arduino core >= 2.0, which
// includes core 3.3.11). If you're on an older core (<2.0), drop the
// esp_now_recv_info_t* parameter and use the mac_addr argument directly.
static void on_esp_now_recv(const esp_now_recv_info_t* info, const uint8_t* data, int data_len) {
    if (data_len < SUBSENSE_MESH_FRAG_HEADER_LEN) return; // malformed, ignore

    const SubSenseMeshPacket* pkt = reinterpret_cast<const SubSenseMeshPacket*>(data);
    if (pkt->magic != SUBSENSE_MESH_MAGIC) return; // not one of ours, ignore

    if (s_role == SUBSENSE_MESH_ROLE_RELAY) {
        // Don't forward our own echoes or anything beyond the hop limit.
        if (pkt->hop_count >= SUBSENSE_MESH_MAX_HOPS) return;
        if (dedup_seen_before(pkt->origin_mac, pkt->msg_id, pkt->chunk_index)) return;

        dedup_remember(pkt->origin_mac, pkt->msg_id, pkt->chunk_index);

        // Re-broadcast the SAME packet, only incrementing hop_count.
        // origin_mac is preserved so the gateway/next relay still knows
        // which physical node this data originally came from.
        SubSenseMeshPacket fwd = *pkt;
        fwd.hop_count = pkt->hop_count + 1;

        size_t wire_len = SUBSENSE_MESH_FRAG_HEADER_LEN + pkt->chunk_len;
        esp_now_send(SUBSENSE_BROADCAST_MAC, reinterpret_cast<uint8_t*>(&fwd), wire_len);
        return; // relay does not reassemble or call an application callback
    }

    if (s_role != SUBSENSE_MESH_ROLE_GATEWAY) return; // NODE role ignores incoming data

    // --- GATEWAY reassembly path ---
    const uint8_t* origin_mac = pkt->origin_mac; // survives relaying, unlike info->src_addr

    int idx = find_slot_for_sender(origin_mac, pkt->msg_id);
    if (idx < 0) {
        idx = allocate_slot(origin_mac, pkt->msg_id, pkt->total_len, pkt->total_chunks);
        if (idx < 0) return; // no free slots, drop
    }

    SubSenseMeshReassemblySlot* slot = &s_slots[idx];

    // Bounds check before copying into the static buffer.
    size_t offset = (size_t)pkt->chunk_index * SUBSENSE_MESH_FRAG_CHUNK_LEN;
    if (offset + pkt->chunk_len > sizeof(slot->buffer)) return; // guard against corruption

    uint32_t chunk_bit = (1U << pkt->chunk_index);
    if (!(slot->received_chunk_mask & chunk_bit)) {
        slot->received_chunk_mask |= chunk_bit;
        slot->chunks_received++;
        memcpy(slot->buffer + offset, pkt->payload, pkt->chunk_len);
    }
    slot->last_update_ms = millis();

    uint32_t expected_mask = (slot->total_chunks >= 32) ? 0xFFFFFFFFU : ((1U << slot->total_chunks) - 1U);
    if (slot->received_chunk_mask == expected_mask) {
        // Full message reassembled -- ensure null termination and hand off.
        size_t final_len = slot->total_len < sizeof(slot->buffer) ? slot->total_len : sizeof(slot->buffer) - 1;
        slot->buffer[final_len] = '\0';

        if (s_rx_callback != NULL) {
            s_rx_callback(slot->buffer, final_len, slot->sender_mac);
        }

        slot->in_use = false; // free the slot for reuse
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

bool subsense_wifi_mesh_init(SubSenseMeshRole role, subsense_mesh_rx_callback_t rx_callback) {
    s_role = role;
    s_rx_callback = rx_callback;
    memset(s_slots, 0, sizeof(s_slots));
    s_next_msg_id = 0;

    WiFi.mode(WIFI_STA);
    WiFi.disconnect(); // ensure not associated to any AP; ESP-NOW works standalone

    if (esp_now_init() != ESP_OK) {
        s_ready = false;
        return false;
    }

    // NODE and RELAY both need to be able to broadcast (relay forwards by
    // re-broadcasting), so register the broadcast peer for both roles.
    if (role == SUBSENSE_MESH_ROLE_NODE || role == SUBSENSE_MESH_ROLE_RELAY) {
        esp_now_peer_info_t peer_info = {};
        memcpy(peer_info.peer_addr, SUBSENSE_BROADCAST_MAC, 6);
        peer_info.channel = 0;   // use current WiFi channel
        peer_info.encrypt = false;

        if (!esp_now_is_peer_exist(SUBSENSE_BROADCAST_MAC)) {
            if (esp_now_add_peer(&peer_info) != ESP_OK) {
                s_ready = false;
                return false;
            }
        }
    }

    // GATEWAY and RELAY both need to listen for incoming packets
    // (gateway reassembles; relay forwards). NODE only sends.
    if (role == SUBSENSE_MESH_ROLE_GATEWAY || role == SUBSENSE_MESH_ROLE_RELAY) {
        if (esp_now_register_recv_cb(on_esp_now_recv) != ESP_OK) {
            s_ready = false;
            return false;
        }
    }

    s_ready = true;
    return true;
}

bool subsense_wifi_mesh_send(const char* json_payload, size_t len) {
    if (!s_ready || s_role != SUBSENSE_MESH_ROLE_NODE) return false;
    if (len == 0 || len > SUBSENSE_MESH_MAX_PAYLOAD_LEN) return false;

    uint8_t msg_id = s_next_msg_id++;
    uint8_t total_chunks = (uint8_t)((len + SUBSENSE_MESH_FRAG_CHUNK_LEN - 1) / SUBSENSE_MESH_FRAG_CHUNK_LEN);
    if (total_chunks == 0) total_chunks = 1;

    uint8_t my_mac[6];
    WiFi.macAddress(my_mac);

    for (uint8_t i = 0; i < total_chunks; i++) {
        if (i > 0) {
            delay(5); // Throttle burst transmission to prevent TX buffer overflow
        }
        SubSenseMeshPacket pkt;
        pkt.magic = SUBSENSE_MESH_MAGIC;
        pkt.msg_id = msg_id;
        pkt.chunk_index = i;
        pkt.total_chunks = total_chunks;
        pkt.total_len = (uint16_t)len;
        pkt.hop_count = 0; // originating node always starts at hop 0
        memcpy(pkt.origin_mac, my_mac, 6);

        size_t offset = (size_t)i * SUBSENSE_MESH_FRAG_CHUNK_LEN;
        size_t remaining = len - offset;
        size_t this_chunk_len = remaining < SUBSENSE_MESH_FRAG_CHUNK_LEN ? remaining : SUBSENSE_MESH_FRAG_CHUNK_LEN;

        pkt.chunk_len = (uint16_t)this_chunk_len;
        memcpy(pkt.payload, json_payload + offset, this_chunk_len);

        size_t wire_len = SUBSENSE_MESH_FRAG_HEADER_LEN + this_chunk_len;
        esp_err_t result = esp_now_send(SUBSENSE_BROADCAST_MAC, reinterpret_cast<uint8_t*>(&pkt), wire_len);

        if (result != ESP_OK) {
            return false; // caller can retry the whole send; keeps logic simple
        }
    }

    return true;
}

void subsense_wifi_mesh_loop(void) {
    uint32_t now = millis();

    if (s_role == SUBSENSE_MESH_ROLE_GATEWAY) {
        for (int i = 0; i < SUBSENSE_MESH_MAX_CONCURRENT_MSGS; i++) {
            if (s_slots[i].in_use && (now - s_slots[i].last_update_ms) > SUBSENSE_MESH_FRAGMENT_TIMEOUT_MS) {
                s_slots[i].in_use = false; // drop stale partial message
            }
        }
    } else if (s_role == SUBSENSE_MESH_ROLE_RELAY) {
        for (int i = 0; i < SUBSENSE_MESH_DEDUP_CACHE_SIZE; i++) {
            if (s_dedup_cache[i].in_use && (now - s_dedup_cache[i].seen_at_ms) > SUBSENSE_MESH_DEDUP_TIMEOUT_MS) {
                s_dedup_cache[i].in_use = false;
            }
        }
    }
    // NODE role: nothing to do.
}

bool subsense_wifi_mesh_is_ready(void) {
    return s_ready;
}
