/**
 * @file subsense_gateway_node.ino
 * @brief SubSense Gateway Node Firmware (Board 3 - Aggregator & LoRa SX126x Receiver).
 * @note Listens for multi-hop LoRa packets from Sensor Nodes (direct or via Relays).
 *       Reassembles multi-packet JSON payloads and emits canonical JSON over USB Serial
 *       (115200 baud) to the Surface Gateway Bridge.
 *
 * Hardware Pin Mapping (ESP32 DevKit):
 *   - SX126x TXD -> ESP32 RX2 (GPIO 16)
 *   - SX126x RXD -> ESP32 TX2 (GPIO 17)
 *   - SX126x M0  -> ESP32 GPIO 25
 *   - SX126x M1  -> ESP32 GPIO 26
 *   - SX126x AUX -> ESP32 GPIO 27
 *   - Status LED -> ESP32 GPIO 2 (Blinks on reception)
 */

#include <Arduino.h>
#include "subsense_lora_mesh.h"
#include "subsense_lora_sx126x.h"

// Hardware Pin Configuration
#define PIN_STATUS_LED   2
static volatile uint32_t s_led_off_ms = 0;

/**
 * @brief Callback invoked whenever a full JSON event/health message
 *        has been received and reassembled from an underground sensor node.
 */
static void on_lora_data_received(
    const char* json_payload,
    size_t len,
    const uint8_t sender_mac[6],
    int16_t rssi_dbm,
    uint8_t hop_count
) {
    digitalWrite(PIN_STATUS_LED, HIGH);
    s_led_off_ms = millis() + 30;

    Serial.println();
    Serial.println("================================================================================");
    Serial.printf("[GATEWAY LORA RX] Received from Origin Node %02X:%02X:%02X:%02X:%02X:%02X (%u bytes) | RSSI: %d dBm | Hops: %u\n",
                  sender_mac[0], sender_mac[1], sender_mac[2],
                  sender_mac[3], sender_mac[4], sender_mac[5],
                  (unsigned)len, (int)rssi_dbm, (unsigned)hop_count);
    Serial.println("--------------------------------------------------------------------------------");
    Serial.println(json_payload);
    Serial.println("================================================================================");

    delay(30);
    digitalWrite(PIN_STATUS_LED, LOW);
}

void setup() {
    Serial.begin(115200);
    delay(500);

    pinMode(PIN_STATUS_LED, OUTPUT);
    digitalWrite(PIN_STATUS_LED, LOW);

    // Boot blink
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_STATUS_LED, HIGH);
        delay(80);
        digitalWrite(PIN_STATUS_LED, LOW);
        delay(80);
    }

    Serial.println();
    Serial.println("================================================================================");
    Serial.println(" SubSense Gateway Node (Board 3) -- Multi-Hop LoRa SX126x Receiver & Ingestion");
    Serial.println(" Hardware: ESP32 @ 240MHz | Radio: LoRa SX126x @ 865 MHz (Fixed Mode P2P)");
    Serial.println("================================================================================");

    // Initialize transport strictly in GATEWAY role with reception callback
    bool ok = subsense_lora_mesh_init(SUBSENSE_MESH_ROLE_GATEWAY, on_lora_data_received);

    if (ok) {
        const uint8_t* mac = subsense_lora_mesh_get_mac();
        Serial.println("[GATEWAY] LoRa SX126x Mesh initialized successfully.");
        Serial.printf("[GATEWAY] My Radio MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                      mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        Serial.println("[GATEWAY] Listening for incoming telemetry from Node & Relay over 865 MHz...");
    } else {
        Serial.println("[GATEWAY] ERROR: Failed to initialize LoRa SX126x module. Check wiring!");
    }

    Serial.println("--------------------------------------------------------------------------------");
}

void loop() {
    // Keep LoRa mesh housekeeper running every iteration.
    // Handles packet reception, reassembly, and ages out stale partial frames.
    subsense_lora_mesh_loop();
    delay(10);
}
