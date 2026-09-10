/**
 * @file subsense_gateway_node.ino
 * @brief SubSense Gateway Node Firmware (Board 3 - Aggregator & Mesh Receiver).
 * @note Listens for multi-hop ESP-NOW packets from Sensor Nodes (direct or via Relays).
 *       Reassembles multi-packet JSON payloads and triggers an application callback
 *       to hand off to the Data Infrastructure layer (Cloud / Dashboard / Database).
 */

#include <Arduino.h>
#include <WiFi.h>
#include "subsense_wifi_mesh.h"

// Hardware Pin Configuration
// Most ESP32 DevKit boards have an onboard blue LED on GPIO 2.
#define PIN_STATUS_LED   2

/**
 * @brief Callback invoked whenever a full JSON event/health message
 *        has been received and reassembled from an underground sensor node.
 * @note  The relay preserves the ORIGINAL sensor node's MAC address, so
 *        sender_mac is the true origin of the telemetry even if relayed!
 */
static void on_mesh_data_received(const char* json_payload, size_t len, const uint8_t sender_mac[6]) {
    // Flash status LED on reception
    digitalWrite(PIN_STATUS_LED, HIGH);

    Serial.println();
    Serial.println("================================================================================");
    Serial.printf("[GATEWAY MESH RX] Received from Origin Node %02X:%02X:%02X:%02X:%02X:%02X (%u bytes):\n",
           sender_mac[0], sender_mac[1], sender_mac[2],
           sender_mac[3], sender_mac[4], sender_mac[5],
           (unsigned)len);
    Serial.println("--------------------------------------------------------------------------------");
    Serial.println(json_payload);
    Serial.println("================================================================================");

    /* DATA INFRASTRUCTURE HANDOFF:
     * This is where the Gateway hands the JSON off to the Data Infrastructure layer:
     * 1. Forward over Wi-Fi / 4G to Cloud API (HTTP POST / MQTT topic "subsense/telemetry")
     * 2. Push to local Time-Series Database (InfluxDB / TimescaleDB / SQLite)
     * 3. Send SMS / WebSocket alert to Shift Supervisor Dashboard if "siren_triggered": true
     */

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
    Serial.println(" SubSense Gateway Node (Board 3) -- Multi-Hop Mesh Receiver & Ingestion");
    Serial.println(" Hardware: ESP32 @ 240MHz | Transport: WiFi Mesh (ESP-NOW Broadcast)");
    Serial.println("================================================================================");

    // Initialize transport strictly in GATEWAY role with reception callback
    bool ok = subsense_wifi_mesh_init(SUBSENSE_MESH_ROLE_GATEWAY, on_mesh_data_received);

    if (ok) {
        Serial.println("[GATEWAY] WiFi Mesh initialized successfully.");
        Serial.print("[GATEWAY] My Radio MAC: ");
        Serial.println(WiFi.macAddress());
        Serial.println("[GATEWAY] Listening for incoming telemetry from Node & Relay...");
    } else {
        Serial.println("[GATEWAY] ERROR: Failed to initialize WiFi radio / ESP-NOW.");
    }

    Serial.println("--------------------------------------------------------------------------------");
}

void loop() {
    // Crucial: Keep WiFi mesh housekeeper running every iteration.
    // This ages out partial reassembly slots and drops stale incomplete fragments.
    subsense_wifi_mesh_loop();
    delay(10);
}
