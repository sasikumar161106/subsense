/**
 * @file subsense_relay_node.ino
 * @brief Firmware for the RELAY board in the SubSense LoRa SX126x P2P mesh.
 * @note This board has NO sensor and does NOT run the TinyML pipeline.
 *       Its only job is to sit physically between the Sensor Node and the
 *       Gateway in mine galleries, receiving LoRa packets at 865 MHz,
 *       filtering duplicates, incrementing the hop counter, and retransmitting.
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
#include "subsense_lora_mesh.h"
#include "subsense_lora_sx126x.h"

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("================================================================================");
    Serial.println(" SubSense Relay Node -- Forwarding Sensor Node LoRa Traffic to Gateway");
    Serial.println(" Frequency: 865 MHz (Channel 15) | Power: 22 dBm | Protocol: P2P Multi-Hop");
    Serial.println("================================================================================");

    bool ok = subsense_lora_mesh_init(SUBSENSE_MESH_ROLE_RELAY, NULL);

    if (ok) {
        const uint8_t* mac = subsense_lora_mesh_get_mac();
        Serial.println("[RELAY] LoRa SX126x mesh relay initialized successfully.");
        Serial.printf("[RELAY] My Radio MAC: %02X:%02X:%02X:%02X:%02X:%02X\n",
                      mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        Serial.println("[RELAY] Listening for LoRa packets to forward...");
    } else {
        Serial.println("[RELAY] ERROR: Failed to initialize LoRa SX126x. Check wiring!");
    }
}

void loop() {
    // LoRa reception, deduplication, and forwarding occur inside loop()
    subsense_lora_mesh_loop();
    delay(20);
}

