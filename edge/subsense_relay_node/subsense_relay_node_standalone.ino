/**
 * @file subsense_relay_node_standalone.ino
 * @brief SubSense Standalone Relay Node Firmware (Board 2 - Multi-Hop Forwarder).
 * @note Single self-contained sketch: paste directly into Arduino IDE on any laptop.
 *       No external libraries or extra header files required.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_idf_version.h>

#define SUBSENSE_MESH_MAGIC             0xA5
#define SUBSENSE_MESH_FRAG_HEADER_LEN   15
#define SUBSENSE_MESH_FRAG_CHUNK_LEN    200
#define SUBSENSE_MESH_MAX_HOPS          3
#define SUBSENSE_MESH_DEDUP_CACHE_SIZE  16
#define SUBSENSE_MESH_DEDUP_TIMEOUT_MS  8000
#define PIN_STATUS_LED                  2

typedef struct __attribute__((packed)) {
    uint8_t  magic;
    uint8_t  msg_id;
    uint8_t  chunk_index;
    uint8_t  total_chunks;
    uint16_t total_len;
    uint16_t chunk_len;
    uint8_t  hop_count;
    uint8_t  origin_mac[6];
    uint8_t  payload[SUBSENSE_MESH_FRAG_CHUNK_LEN];
} SubSenseMeshPacket;

typedef struct {
    bool     in_use;
    uint8_t  origin_mac[6];
    uint8_t  msg_id;
    uint8_t  chunk_index;
    uint32_t seen_at_ms;
} SubSenseMeshDedupEntry;

static SubSenseMeshDedupEntry s_dedup_cache[SUBSENSE_MESH_DEDUP_CACHE_SIZE];
static int s_dedup_next_slot = 0;
static const uint8_t BROADCAST_ADDR[6] = { 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF };

static void handle_forward(const uint8_t* data, int data_len) {
    if (data_len < SUBSENSE_MESH_FRAG_HEADER_LEN) return;

    const SubSenseMeshPacket* pkt = reinterpret_cast<const SubSenseMeshPacket*>(data);
    if (pkt->magic != SUBSENSE_MESH_MAGIC) return;
    if (pkt->hop_count >= SUBSENSE_MESH_MAX_HOPS) return;

    // Dedup check: do not forward the same fragment twice
    uint32_t now = millis();
    for (int i = 0; i < SUBSENSE_MESH_DEDUP_CACHE_SIZE; i++) {
        if (s_dedup_cache[i].in_use) {
            if ((now - s_dedup_cache[i].seen_at_ms) > SUBSENSE_MESH_DEDUP_TIMEOUT_MS) {
                s_dedup_cache[i].in_use = false;
            } else if (s_dedup_cache[i].msg_id == pkt->msg_id &&
                       s_dedup_cache[i].chunk_index == pkt->chunk_index &&
                       memcmp(s_dedup_cache[i].origin_mac, pkt->origin_mac, 6) == 0) {
                return;
            }
        }
    }

    // Save in dedup ring
    s_dedup_cache[s_dedup_next_slot].in_use = true;
    memcpy(s_dedup_cache[s_dedup_next_slot].origin_mac, pkt->origin_mac, 6);
    s_dedup_cache[s_dedup_next_slot].msg_id = pkt->msg_id;
    s_dedup_cache[s_dedup_next_slot].chunk_index = pkt->chunk_index;
    s_dedup_cache[s_dedup_next_slot].seen_at_ms = now;
    s_dedup_next_slot = (s_dedup_next_slot + 1) % SUBSENSE_MESH_DEDUP_CACHE_SIZE;

    // Increment hop count and forward
    SubSenseMeshPacket fwd = *pkt;
    fwd.hop_count = pkt->hop_count + 1;

    size_t wire_len = SUBSENSE_MESH_FRAG_HEADER_LEN + pkt->chunk_len;
    esp_now_send(BROADCAST_ADDR, reinterpret_cast<uint8_t*>(&fwd), wire_len);

    // Blink status LED on forward
    digitalWrite(PIN_STATUS_LED, HIGH);

    Serial.printf("[RELAY FWD] Forwarded Msg ID %u (chunk %u/%u) from Origin %02X:%02X:%02X:%02X:%02X:%02X | Hop %u -> %u\n",
                  pkt->msg_id, pkt->chunk_index + 1, pkt->total_chunks,
                  pkt->origin_mac[0], pkt->origin_mac[1], pkt->origin_mac[2],
                  pkt->origin_mac[3], pkt->origin_mac[4], pkt->origin_mac[5],
                  pkt->hop_count, fwd.hop_count);

    delay(20);
    digitalWrite(PIN_STATUS_LED, LOW);
}

// Receive callback supporting both Arduino ESP32 Core v2.x and v3.x
#if defined(ESP_IDF_VERSION_MAJOR) && (ESP_IDF_VERSION_MAJOR >= 5)
static void on_esp_now_recv(const esp_now_recv_info_t* info, const uint8_t* data, int data_len) {
    handle_forward(data, data_len);
}
#else
static void on_esp_now_recv(const uint8_t* mac_addr, const uint8_t* data, int data_len) {
    handle_forward(data, data_len);
}
#endif

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    // Boot blink 3 times
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_STATUS_LED, HIGH);
        delay(80);
        digitalWrite(PIN_STATUS_LED, LOW);
        delay(80);
    }

    Serial.println();
    Serial.println("================================================================================");
    Serial.println(" SubSense Relay Node (Board 2) -- Multi-Hop WiFi Mesh Forwarder");
    Serial.println(" Hardware: ESP32 @ 240MHz | Transport: ESP-NOW Broadcast Relay");
    Serial.println("================================================================================");

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();

    if (esp_now_init() != ESP_OK) {
        Serial.println("[RELAY] ERROR: Failed to initialize ESP-NOW radio.");
        return;
    }

    esp_now_peer_info_t peer_info = {};
    memcpy(peer_info.peer_addr, BROADCAST_ADDR, 6);
    peer_info.channel = 0;
    peer_info.encrypt = false;

    if (!esp_now_is_peer_exist(BROADCAST_ADDR)) {
        if (esp_now_add_peer(&peer_info) != ESP_OK) {
            Serial.println("[RELAY] ERROR: Failed to add broadcast peer.");
            return;
        }
    }

    if (esp_now_register_recv_cb(on_esp_now_recv) != ESP_OK) {
        Serial.println("[RELAY] ERROR: Failed to register receive callback.");
        return;
    }

    Serial.println("[RELAY] WiFi Mesh Relay initialized successfully.");
    Serial.print("[RELAY] My Radio MAC: ");
    Serial.println(WiFi.macAddress());
    Serial.println("[RELAY] Listening for Sensor Node packets to forward to Gateway...");
    Serial.println("--------------------------------------------------------------------------------");
}

void loop() {
    // Age out stale dedup entries every loop
    uint32_t now = millis();
    for (int i = 0; i < SUBSENSE_MESH_DEDUP_CACHE_SIZE; i++) {
        if (s_dedup_cache[i].in_use && (now - s_dedup_cache[i].seen_at_ms) > SUBSENSE_MESH_DEDUP_TIMEOUT_MS) {
            s_dedup_cache[i].in_use = false;
        }
    }
    delay(100);
}
