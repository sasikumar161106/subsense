/**
 * @file subsense_lora_mesh.cpp
 * @brief Implementation of SubSense LoRa SX126x Multi-Hop Mesh Transport.
 */

#include "subsense_lora_mesh.h"
#include "subsense_lora_sx126x.h"

#include <Arduino.h>
#include <esp_system.h>
#include <string.h>

#define SUBSENSE_MESH_MAGIC               0xA5
#define SUBSENSE_MESH_FRAGMENT_TIMEOUT_MS 6000
#define SUBSENSE_MESH_DEDUP_CACHE_SIZE    16
#define SUBSENSE_MESH_DEDUP_TIMEOUT_MS    8000

typedef struct __attribute__((packed)) {
    uint8_t  magic;
    uint8_t  msg_id;
    uint8_t  chunk_index;
    uint8_t  total_chunks;
    uint16_t total_len;
    uint16_t chunk_len;
    uint8_t  hop_count;
    uint8_t  origin_mac[6];
    uint8_t  payload[SUBSENSE_LORA_FRAG_CHUNK_LEN];
} SubSenseLoraMeshPacket;

typedef struct {
    bool     in_use;
    uint8_t  origin_mac[6];
    uint8_t  msg_id;
    uint8_t  chunk_index;
    uint32_t seen_at_ms;
} SubSenseLoraDedupEntry;

typedef struct {
    bool     in_use;
    uint8_t  sender_mac[6];
    uint8_t  msg_id;
    uint8_t  chunks_received;
    uint8_t  total_chunks;
    uint16_t total_len;
    uint32_t last_update_ms;
    int16_t  last_rssi_dbm;
    uint8_t  max_hop_seen;
    char     buffer[SUBSENSE_MESH_MAX_PAYLOAD_LEN];
} SubSenseLoraReassemblySlot;

static SubSenseMeshRole             s_role = SUBSENSE_MESH_ROLE_NODE;
static subsense_lora_rx_callback_t  s_rx_callback = NULL;
static bool                         s_ready = false;
static uint8_t                      s_next_msg_id = 0;
static uint8_t                      s_my_mac[6] = {0};

static SubSenseLoraDedupEntry       s_dedup[SUBSENSE_MESH_DEDUP_CACHE_SIZE];
static int                          s_dedup_idx = 0;

static SubSenseLoraReassemblySlot   s_slots[SUBSENSE_MESH_MAX_CONCURRENT_MSGS];

#define PIN_STATUS_LED 2

const uint8_t* subsense_lora_mesh_get_mac(void) {
    return s_my_mac;
}

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
    int chosen = -1;
    uint32_t oldest = UINT32_MAX;

    for (int i = 0; i < SUBSENSE_MESH_MAX_CONCURRENT_MSGS; i++) {
        if (!s_slots[i].in_use) {
            chosen = i;
            break;
        }
        if (s_slots[i].last_update_ms < oldest) {
            oldest = s_slots[i].last_update_ms;
            chosen = i;
        }
    }

    if (chosen >= 0) {
        SubSenseLoraReassemblySlot* s = &s_slots[chosen];
        s->in_use = true;
        memcpy(s->sender_mac, mac, 6);
        s->msg_id = msg_id;
        s->chunks_received = 0;
        s->total_chunks = total_chunks;
        s->total_len = (total_len < SUBSENSE_MESH_MAX_PAYLOAD_LEN) ? total_len : (SUBSENSE_MESH_MAX_PAYLOAD_LEN - 1);
        s->last_update_ms = millis();
        s->last_rssi_dbm = -70;
        s->max_hop_seen = 0;
        memset(s->buffer, 0, sizeof(s->buffer));
    }
    return chosen;
}

static void handle_relay_packet(const SubSenseLoraMeshPacket* pkt, size_t wire_len) {
    if (pkt->hop_count >= SUBSENSE_MESH_MAX_HOPS) return;

    uint32_t now = millis();
    for (int i = 0; i < SUBSENSE_MESH_DEDUP_CACHE_SIZE; i++) {
        if (s_dedup[i].in_use) {
            if ((now - s_dedup[i].seen_at_ms) > SUBSENSE_MESH_DEDUP_TIMEOUT_MS) {
                s_dedup[i].in_use = false;
            } else if (s_dedup[i].msg_id == pkt->msg_id &&
                       s_dedup[i].chunk_index == pkt->chunk_index &&
                       memcmp(s_dedup[i].origin_mac, pkt->origin_mac, 6) == 0) {
                return;
            }
        }
    }

    s_dedup[s_dedup_idx].in_use = true;
    memcpy(s_dedup[s_dedup_idx].origin_mac, pkt->origin_mac, 6);
    s_dedup[s_dedup_idx].msg_id = pkt->msg_id;
    s_dedup[s_dedup_idx].chunk_index = pkt->chunk_index;
    s_dedup[s_dedup_idx].seen_at_ms = now;
    s_dedup_idx = (s_dedup_idx + 1) % SUBSENSE_MESH_DEDUP_CACHE_SIZE;

    SubSenseLoraMeshPacket fwd = *pkt;
    fwd.hop_count = pkt->hop_count + 1;

    size_t fwd_len = SUBSENSE_LORA_FRAG_HEADER_LEN + pkt->chunk_len;
    subsense_lora_sx126x_send((const uint8_t*)&fwd, fwd_len, LORA_BROADCAST_ADDR, LORA_DEFAULT_CHANNEL_OFFSET);

    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, HIGH);
    delay(15);
    digitalWrite(PIN_STATUS_LED, LOW);
}

static void handle_gateway_packet(const SubSenseLoraMeshPacket* pkt, int16_t rssi_dbm) {
    int slot_idx = find_slot_for_sender(pkt->origin_mac, pkt->msg_id);
    if (slot_idx < 0) {
        slot_idx = allocate_slot(pkt->origin_mac, pkt->msg_id, pkt->total_len, pkt->total_chunks);
        if (slot_idx < 0) return;
    }

    SubSenseLoraReassemblySlot* s = &s_slots[slot_idx];
    s->last_update_ms = millis();
    s->last_rssi_dbm = rssi_dbm;
    if (pkt->hop_count > s->max_hop_seen) {
        s->max_hop_seen = pkt->hop_count;
    }

    size_t offset = (size_t)pkt->chunk_index * SUBSENSE_LORA_FRAG_CHUNK_LEN;
    if (offset + pkt->chunk_len <= sizeof(s->buffer) - 1) {
        memcpy(&s->buffer[offset], pkt->payload, pkt->chunk_len);
        s->chunks_received++;
    }

    if (s->chunks_received >= s->total_chunks) {
        size_t final_len = (s->total_len < sizeof(s->buffer)) ? s->total_len : (sizeof(s->buffer) - 1);
        s->buffer[final_len] = '\0';

        if (s_rx_callback != NULL) {
            s_rx_callback(s->buffer, final_len, s->sender_mac, s->last_rssi_dbm, s->max_hop_seen);
        }

        s->in_use = false;
    }
}

bool subsense_lora_mesh_init(SubSenseMeshRole role, subsense_lora_rx_callback_t rx_callback) {
    s_role = role;
    s_rx_callback = rx_callback;

    esp_efuse_mac_get_default(s_my_mac);

    bool lora_ok = subsense_lora_sx126x_init(LORA_DEFAULT_FREQ_MHZ, 0, true);

    memset(s_dedup, 0, sizeof(s_dedup));
    memset(s_slots, 0, sizeof(s_slots));

    s_ready = lora_ok;
    return s_ready;
}

bool subsense_lora_mesh_send(const char* json_payload, size_t len) {
    if (!s_ready || s_role != SUBSENSE_MESH_ROLE_NODE || json_payload == NULL || len == 0) return false;
    if (len >= SUBSENSE_MESH_MAX_PAYLOAD_LEN) return false;

    uint8_t total_chunks = (uint8_t)((len + SUBSENSE_LORA_FRAG_CHUNK_LEN - 1) / SUBSENSE_LORA_FRAG_CHUNK_LEN);
    uint8_t msg_id = s_next_msg_id++;

    SubSenseLoraMeshPacket pkt;
    pkt.magic = SUBSENSE_MESH_MAGIC;
    pkt.msg_id = msg_id;
    pkt.total_chunks = total_chunks;
    pkt.total_len = (uint16_t)len;
    pkt.hop_count = 0;
    memcpy(pkt.origin_mac, s_my_mac, 6);

    for (uint8_t i = 0; i < total_chunks; i++) {
        pkt.chunk_index = i;
        size_t offset = (size_t)i * SUBSENSE_LORA_FRAG_CHUNK_LEN;
        size_t chunk_bytes = len - offset;
        if (chunk_bytes > SUBSENSE_LORA_FRAG_CHUNK_LEN) {
            chunk_bytes = SUBSENSE_LORA_FRAG_CHUNK_LEN;
        }

        pkt.chunk_len = (uint16_t)chunk_bytes;
        memcpy(pkt.payload, &json_payload[offset], chunk_bytes);

        size_t wire_len = SUBSENSE_LORA_FRAG_HEADER_LEN + chunk_bytes;
        subsense_lora_sx126x_send((const uint8_t*)&pkt, wire_len, LORA_BROADCAST_ADDR, LORA_DEFAULT_CHANNEL_OFFSET);

        if (total_chunks > 1) {
            delay(35);
        }
    }

    return true;
}

void subsense_lora_mesh_loop(void) {
    if (!s_ready) return;

    uint8_t rx_raw[256];
    int16_t rssi_dbm = -70;
    size_t rx_len = subsense_lora_sx126x_receive(rx_raw, sizeof(rx_raw), &rssi_dbm);

    if (rx_len >= SUBSENSE_LORA_FRAG_HEADER_LEN) {
        const SubSenseLoraMeshPacket* pkt = (const SubSenseLoraMeshPacket*)rx_raw;
        if (pkt->magic == SUBSENSE_MESH_MAGIC) {
            if (s_role == SUBSENSE_MESH_ROLE_RELAY) {
                handle_relay_packet(pkt, rx_len);
            } else if (s_role == SUBSENSE_MESH_ROLE_GATEWAY) {
                handle_gateway_packet(pkt, rssi_dbm);
            }
        }
    }

    if (s_role == SUBSENSE_MESH_ROLE_GATEWAY) {
        uint32_t now = millis();
        for (int i = 0; i < SUBSENSE_MESH_MAX_CONCURRENT_MSGS; i++) {
            if (s_slots[i].in_use && (now - s_slots[i].last_update_ms > SUBSENSE_MESH_FRAGMENT_TIMEOUT_MS)) {
                s_slots[i].in_use = false;
            }
        }
    }
}

bool subsense_lora_mesh_is_ready(void) {
    return s_ready;
}
