/**
 * @file subsense_relay_node.ino
 * @brief Minimal firmware for the RELAY board in the SubSense WiFi mesh.
 * @note This board has NO sensor and does NOT run the TinyML pipeline.
 *       Its only job is to sit physically between the Sensor Node and the
 *       Gateway and forward messages one hop further, so the two don't need
 *       to be in direct WiFi range of each other. This is what makes the
 *       network a real multi-hop mesh instead of a simple star.
 *
 * Setup:
 *   1. Copy subsense_wifi_mesh.h and subsense_wifi_mesh.cpp into this
 *      sketch's folder (same folder as this .ino file).
 *   2. Flash this sketch to your third (empty) ESP32 board.
 *   3. Open Serial Monitor at 115200 baud to watch it forward packets.
 */

#include <Arduino.h>
#include "subsense_wifi_mesh.h"

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("================================================================================");
    Serial.println(" SubSense Relay Node -- forwarding Sensor Node traffic to Gateway");
    Serial.println("================================================================================");

    bool ok = subsense_wifi_mesh_init(SUBSENSE_MESH_ROLE_RELAY, NULL);

    if (ok) {
        Serial.println("[RELAY] WiFi mesh relay initialized successfully.");
        Serial.print("[RELAY] My MAC address: ");
        Serial.println(WiFi.macAddress());
        Serial.println("[RELAY] Listening for packets to forward...");
    } else {
        Serial.println("[RELAY] ERROR: Failed to initialize ESP-NOW. Check WiFi hardware.");
    }
}

void loop() {
    // Housekeeping only -- ages out the dedup cache so old entries don't
    // pile up forever. All the actual forwarding happens automatically
    // inside the ESP-NOW receive callback registered during init.
    subsense_wifi_mesh_loop();
    delay(100);
}
