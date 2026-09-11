/**
 * @file subsense_lora_sx126x.cpp
 * @brief Native ESP32 C++ Driver implementation for LoRa SX126x (EBYTE E22).
 * @note Ported directly from loramain project sx126x.py.
 */

#include "subsense_lora_sx126x.h"

// Dedicated HardwareSerial 2 on ESP32
static HardwareSerial s_lora_serial(2);
static bool s_initialized = false;
static uint8_t s_channel_offset = LORA_DEFAULT_CHANNEL_OFFSET;
static bool s_rssi_enabled = true;

// Helper to set hardware mode pins
static void set_mode(uint8_t m0_val, uint8_t m1_val) {
    digitalWrite(LORA_PIN_M0, m0_val);
    digitalWrite(LORA_PIN_M1, m1_val);
    delay(100); // Allow hardware PLL & mode switch to settle (from sx126x.py)
}

static void wait_aux_ready(uint32_t timeout_ms = 1000) {
    uint32_t start = millis();
    while (digitalRead(LORA_PIN_AUX) == LOW && (millis() - start) < timeout_ms) {
        delay(5);
    }
}

bool subsense_lora_sx126x_init(uint16_t freq_mhz, uint16_t node_addr, bool enable_rssi) {
    s_rssi_enabled = enable_rssi;

    // Configure GPIO mode pins
    pinMode(LORA_PIN_M0, OUTPUT);
    pinMode(LORA_PIN_M1, OUTPUT);
    pinMode(LORA_PIN_AUX, INPUT_PULLUP);

    // Enter Configuration Mode (M0 = LOW, M1 = HIGH)
    set_mode(LOW, HIGH);

    // Initialize UART2 at 9600 baud, 8 data bits, no parity, 1 stop bit
    s_lora_serial.begin(LORA_UART_BAUDRATE, SERIAL_8N1, LORA_PIN_RX, LORA_PIN_TX);
    delay(200);

    // Clear serial buffers
    while (s_lora_serial.available()) {
        s_lora_serial.read();
    }

    // Calculate frequency offset (850MHz base for E22-900T22S)
    if (freq_mhz >= 850) {
        s_channel_offset = (uint8_t)(freq_mhz - 850);
    } else if (freq_mhz >= 410) {
        s_channel_offset = (uint8_t)(freq_mhz - 410);
    } else {
        s_channel_offset = LORA_DEFAULT_CHANNEL_OFFSET; // 15
    }

    uint8_t high_addr = (node_addr >> 8) & 0xFF;
    uint8_t low_addr  = node_addr & 0xFF;
    uint8_t rssi_flag = enable_rssi ? 0x80 : 0x00;

    // Build 12-byte configuration packet identical to loramain sx126x.py
    // cfg_reg: [0xC0, 0x00, 0x09, H_ADDR, L_ADDR, NETID, REG0, REG1, REG2, REG3, CRYPT_H, CRYPT_L]
    uint8_t cfg_reg[12];
    cfg_reg[0]  = 0xC0;                          // 0xC0 = Save settings in EEPROM across power cycles
    cfg_reg[1]  = 0x00;                          // Start address 00H
    cfg_reg[2]  = 0x09;                          // 9 configuration bytes to follow
    cfg_reg[3]  = high_addr;                     // High address
    cfg_reg[4]  = low_addr;                      // Low address
    cfg_reg[5]  = 0x00;                          // Net ID 0
    cfg_reg[6]  = 0x60 | 0x02;                   // 9600 UART (0x60) + 2400 air speed (0x02) = 0x62
    cfg_reg[7]  = 0x00 | 0x00 | 0x20;            // 240B packet (0x00) + 22dBm (0x00) + noise RSSI (0x20)
    cfg_reg[8]  = s_channel_offset;              // Channel offset (15 for 865 MHz)
    cfg_reg[9]  = 0x40 | 0x03 | rssi_flag;       // Fixed mode (0x40) + WOR 2000ms (0x03) + packet RSSI (0x80)
    cfg_reg[10] = 0x00;                          // Crypt high
    cfg_reg[11] = 0x00;                          // Crypt low

    bool ack_ok = false;
    for (int attempt = 0; attempt < 2; attempt++) {
        s_lora_serial.write(cfg_reg, 12);
        s_lora_serial.flush();
        delay(250);

        if (s_lora_serial.available()) {
            uint8_t resp = s_lora_serial.read();
            if (resp == 0xC1) {
                ack_ok = true;
                // Drain any remaining status response bytes
                while (s_lora_serial.available()) {
                    s_lora_serial.read();
                }
                break;
            }
        }
        delay(150);
    }

    // Switch to Normal Mode (M0 = LOW, M1 = LOW)
    set_mode(LOW, LOW);
    wait_aux_ready(500);

    s_initialized = true;
    return ack_ok;
}

bool subsense_lora_sx126x_send(const uint8_t* data, size_t len, uint16_t target_addr, uint8_t channel) {
    if (!s_initialized || data == NULL || len == 0) {
        return false;
    }

    // Ensure normal transmission mode (M0=LOW, M1=LOW)
    digitalWrite(LORA_PIN_M0, LOW);
    digitalWrite(LORA_PIN_M1, LOW);

    // Fixed transmission format: [ADDR_H, ADDR_L, CHANNEL, PAYLOAD...]
    uint8_t header[3];
    header[0] = (uint8_t)((target_addr >> 8) & 0xFF);
    header[1] = (uint8_t)(target_addr & 0xFF);
    header[2] = channel;

    s_lora_serial.write(header, 3);
    s_lora_serial.write(data, len);
    s_lora_serial.flush();

    wait_aux_ready(500);
    return true;
}

size_t subsense_lora_sx126x_receive(uint8_t* out_buf, size_t max_len, int16_t* out_rssi_dbm) {
    if (!s_initialized || out_buf == NULL || max_len == 0) {
        return 0;
    }

    size_t avail = s_lora_serial.available();
    if (avail == 0) {
        return 0;
    }

    // Wait slightly for complete LoRa packet buffer to land in UART FIFO
    delay(40);
    avail = s_lora_serial.available();

    // With RSSI enabled, packet has at least 1 payload byte + 1 RSSI byte = 2 bytes
    if (s_rssi_enabled && avail < 2) {
        return 0;
    }

    size_t bytes_to_read = avail > (max_len + (s_rssi_enabled ? 1 : 0))
                           ? (max_len + (s_rssi_enabled ? 1 : 0))
                           : avail;

    uint8_t temp_buf[256];
    size_t actual_read = s_lora_serial.readBytes(temp_buf, bytes_to_read);

    if (actual_read == 0) {
        return 0;
    }

    if (s_rssi_enabled && actual_read >= 2) {
        // Last byte is raw RSSI appended by E22 hardware
        uint8_t raw_rssi = temp_buf[actual_read - 1];
        if (out_rssi_dbm != NULL) {
            *out_rssi_dbm = -(int16_t)(256 - raw_rssi); // Convert to dBm, identical to loramain sx126x.py
        }
        size_t payload_len = actual_read - 1;
        memcpy(out_buf, temp_buf, payload_len);
        return payload_len;
    } else {
        if (out_rssi_dbm != NULL) {
            *out_rssi_dbm = -70; // Nominal fallback if RSSI disabled
        }
        memcpy(out_buf, temp_buf, actual_read);
        return actual_read;
    }
}

void subsense_lora_sx126x_sleep(void) {
    // Mode 3: Sleep Mode (M0 = HIGH, M1 = HIGH)
    set_mode(HIGH, HIGH);
}

void subsense_lora_sx126x_wakeup(void) {
    // Mode 0: Normal Mode (M0 = LOW, M1 = LOW)
    set_mode(LOW, LOW);
    wait_aux_ready(200);
}

bool subsense_lora_sx126x_is_ready(void) {
    return s_initialized && (digitalRead(LORA_PIN_AUX) == HIGH);
}
