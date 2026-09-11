/**
 * @file subsense_relay_node_standalone.ino
 * @brief SubSense Standalone LoRa Relay Node Firmware (Board 2 - Multi-Hop LoRa Forwarder).
 * @note Single self-contained sketch: paste directly into Arduino IDE on any laptop.
 *       Configured for LoRa SX126x (EBYTE E22-900T22S / SX1262) @ 865 MHz.
 *       No external libraries required.
 *
 * Hardware Pin Mapping (ESP32 DevKit):
 *   - SX126x TXD -> ESP32 RX2 (GPIO 16)
 *   - SX126x RXD -> ESP32 TX2 (GPIO 17)
 *   - SX126x M0  -> ESP32 GPIO 25
 *   - SX126x M1  -> ESP32 GPIO 26
 *   - SX126x AUX -> ESP32 GPIO 27
 *   - Status LED -> ESP32 GPIO 2 (Flashes on forward)
 */

#include <Arduino.h>
#include <HardwareSerial.h>
#include <esp_system.h>

#define SUBSENSE_MESH_MAGIC             0xA5
#define SUBSENSE_MESH_FRAG_HEADER_LEN   15
#define SUBSENSE_MESH_FRAG_CHUNK_LEN    190
#define SUBSENSE_MESH_MAX_HOPS          3
#define SUBSENSE_MESH_DEDUP_CACHE_SIZE  16
#define SUBSENSE_MESH_DEDUP_TIMEOUT_MS  8000

#define LORA_PIN_RX     16
#define LORA_PIN_TX     17
#define LORA_PIN_M0     25
#define LORA_PIN_M1     26
#define LORA_PIN_AUX    27
#define PIN_STATUS_LED  2

#define LORA_DEFAULT_CHANNEL_OFFSET 15 // 865 MHz (India ISM Band)
#define LORA_BROADCAST_ADDR         0xFFFF

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
} SubSenseLoraMeshPacket;

typedef struct {
    bool     in_use;
    uint8_t  origin_mac[6];
    uint8_t  msg_id;
    uint8_t  chunk_index;
    uint32_t seen_at_ms;
} SubSenseDedupEntry;

static HardwareSerial s_lora(2);
static SubSenseDedupEntry s_dedup[SUBSENSE_MESH_DEDUP_CACHE_SIZE];
static int s_dedup_next = 0;
static uint8_t s_my_mac[6] = {0};

static void set_lora_mode(uint8_t m0, uint8_t m1) {
    digitalWrite(LORA_PIN_M0, m0);
    digitalWrite(LORA_PIN_M1, m1);
    delay(100);
}

static bool init_sx126x(uint16_t freq_mhz = 865) {
    pinMode(LORA_PIN_M0, OUTPUT);
    pinMode(LORA_PIN_M1, OUTPUT);
    pinMode(LORA_PIN_AUX, INPUT_PULLUP);
    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    set_lora_mode(LOW, HIGH); // Config mode

    s_lora.begin(9600, SERIAL_8N1, LORA_PIN_RX, LORA_PIN_TX);
    delay(200);

    while (s_lora.available()) s_lora.read();

    uint8_t ch = (freq_mhz >= 850) ? (uint8_t)(freq_mhz - 850) : LORA_DEFAULT_CHANNEL_OFFSET;

    // 12-byte configuration matching loramain sx126x.py
    uint8_t cfg[12] = {
        0xC0, 0x00, 0x09, 0x00, 0x00, 0x00,
        0x62,                   // 9600 baud + 2400 air speed
        0x20,                   // 240B pkt + 22dBm + noise RSSI
        ch,                     // 865 MHz channel offset
        0xC3,                   // Fixed mode + WOR 2000ms + packet RSSI enabled
        0x00, 0x00
    };

    bool ok = false;
    for (int i = 0; i < 2; i++) {
        s_lora.write(cfg, 12);
        s_lora.flush();
        delay(250);
        if (s_lora.available() && s_lora.read() == 0xC1) {
            ok = true;
            while (s_lora.available()) s_lora.read();
            break;
        }
    }

    set_lora_mode(LOW, LOW); // Normal mode
    return ok;
}

static void send_lora_packet(const uint8_t* data, size_t len) {
    uint8_t header[3] = { 0xFF, 0xFF, LORA_DEFAULT_CHANNEL_OFFSET }; // Fixed broadcast
    s_lora.write(header, 3);
    s_lora.write(data, len);
    s_lora.flush();
}

static void handle_forward(const SubSenseLoraMeshPacket* pkt) {
    if (pkt->magic != SUBSENSE_MESH_MAGIC) return;
    if (pkt->hop_count >= SUBSENSE_MESH_MAX_HOPS) return;

    uint32_t now = millis();
    for (int i = 0; i < SUBSENSE_MESH_DEDUP_CACHE_SIZE; i++) {
        if (s_dedup[i].in_use) {
            if ((now - s_dedup[i].seen_at_ms) > SUBSENSE_MESH_DEDUP_TIMEOUT_MS) {
                s_dedup[i].in_use = false;
            } else if (s_dedup[i].msg_id == pkt->msg_id &&
                       s_dedup[i].chunk_index == pkt->chunk_index &&
                       memcmp(s_dedup[i].origin_mac, pkt->origin_mac, 6) == 0) {
                return; // Dedup hit
            }
        }
    }

    s_dedup[s_dedup_next].in_use = true;
    memcpy(s_dedup[s_dedup_next].origin_mac, pkt->origin_mac, 6);
    s_dedup[s_dedup_next].msg_id = pkt->msg_id;
    s_dedup[s_dedup_next].chunk_index = pkt->chunk_index;
    s_dedup[s_dedup_next].seen_at_ms = now;
    s_dedup_next = (s_dedup_next + 1) % SUBSENSE_MESH_DEDUP_CACHE_SIZE;

    SubSenseLoraMeshPacket fwd = *pkt;
    fwd.hop_count = pkt->hop_count + 1;

    size_t wire_len = SUBSENSE_MESH_FRAG_HEADER_LEN + pkt->chunk_len;
    send_lora_packet((const uint8_t*)&fwd, wire_len);

    digitalWrite(PIN_STATUS_LED, HIGH);
    Serial.printf("[RELAY FWD] LoRa Msg ID %u (chunk %u/%u) Origin %02X:%02X:%02X:%02X:%02X:%02X | Hop %u -> %u\n",
                  pkt->msg_id, pkt->chunk_index + 1, pkt->total_chunks,
                  pkt->origin_mac[0], pkt->origin_mac[1], pkt->origin_mac[2],
                  pkt->origin_mac[3], pkt->origin_mac[4], pkt->origin_mac[5],
                  pkt->hop_count, fwd.hop_count);
    delay(20);
    digitalWrite(PIN_STATUS_LED, LOW);
}

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("================================================================================");
    Serial.println(" SubSense Standalone Relay Node (Board 2) -- LoRa SX126x Multi-Hop Repeater");
    Serial.println(" Hardware: ESP32 @ 240MHz | Radio: EBYTE E22-900T22S @ 865 MHz (22 dBm)");
    Serial.println("================================================================================");

    esp_efuse_mac_get_default(s_my_mac);

    bool ok = init_sx126x(865);
    if (ok) {
        Serial.printf("[RELAY] LoRa SX126x initialized successfully. MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                      s_my_mac[0], s_my_mac[1], s_my_mac[2], s_my_mac[3], s_my_mac[4], s_my_mac[5]);
        Serial.println("[RELAY] Listening for LoRa packets on 865 MHz...");
    } else {
        Serial.println("[RELAY] ERROR: LoRa SX126x init failed! Check connections (RX=16, TX=17, M0=25, M1=26).");
    }
}

void loop() {
    if (s_lora.available() >= SUBSENSE_MESH_FRAG_HEADER_LEN) {
        delay(35); // Wait for packet to finish landing in UART buffer
        uint8_t buf[256];
        size_t n = s_lora.readBytes(buf, sizeof(buf));
        if (n >= SUBSENSE_MESH_FRAG_HEADER_LEN + 1) { // includes trailing RSSI byte
            const SubSenseLoraMeshPacket* pkt = (const SubSenseLoraMeshPacket*)buf;
            int16_t rssi = -(int16_t)(256 - buf[n - 1]);
            Serial.printf("[RELAY RX] Received %u bytes (RSSI: %d dBm)\n", (unsigned)n, rssi);
            handle_forward(pkt);
        }
    }
    delay(10);
}
