/**
 * @file subsense_lora_sx126x.cpp
 * @brief Native ESP32 C++ Driver implementation for LoRa SX126x (EBYTE E22).
 */

#include "subsense_lora_sx126x.h"

static HardwareSerial s_lora_serial(2);
static bool s_initialized = false;
static uint8_t s_channel_offset = LORA_DEFAULT_CHANNEL_OFFSET;
static bool s_rssi_enabled = true;

static void set_mode(uint8_t m0_val, uint8_t m1_val) {
    digitalWrite(LORA_PIN_M0, m0_val);
    digitalWrite(LORA_PIN_M1, m1_val);
    delay(100);
}

static void wait_aux_ready(uint32_t timeout_ms = 1000) {
    uint32_t start = millis();
    while (digitalRead(LORA_PIN_AUX) == LOW && (millis() - start) < timeout_ms) {
        delay(5);
    }
}

bool subsense_lora_sx126x_init(uint16_t freq_mhz, uint16_t node_addr, bool enable_rssi) {
    s_rssi_enabled = enable_rssi;

    pinMode(LORA_PIN_M0, OUTPUT);
    pinMode(LORA_PIN_M1, OUTPUT);
    pinMode(LORA_PIN_AUX, INPUT_PULLUP);

    set_mode(LOW, HIGH);

    s_lora_serial.begin(LORA_UART_BAUDRATE, SERIAL_8N1, LORA_PIN_RX, LORA_PIN_TX);
    delay(200);

    while (s_lora_serial.available()) {
        s_lora_serial.read();
    }

    if (freq_mhz >= 850) {
        s_channel_offset = (uint8_t)(freq_mhz - 850);
    } else if (freq_mhz >= 410) {
        s_channel_offset = (uint8_t)(freq_mhz - 410);
    } else {
        s_channel_offset = LORA_DEFAULT_CHANNEL_OFFSET;
    }

    uint8_t high_addr = (node_addr >> 8) & 0xFF;
    uint8_t low_addr  = node_addr & 0xFF;
    uint8_t rssi_flag = enable_rssi ? 0x80 : 0x00;

    uint8_t cfg_reg[12];
    cfg_reg[0]  = 0xC0;
    cfg_reg[1]  = 0x00;
    cfg_reg[2]  = 0x09;
    cfg_reg[3]  = high_addr;
    cfg_reg[4]  = low_addr;
    cfg_reg[5]  = 0x00;
    cfg_reg[6]  = 0x60 | 0x02;
    cfg_reg[7]  = 0x00 | 0x00 | 0x20;
    cfg_reg[8]  = s_channel_offset;
    cfg_reg[9]  = 0x40 | 0x03 | rssi_flag;
    cfg_reg[10] = 0x00;
    cfg_reg[11] = 0x00;

    bool ack_ok = false;
    for (int attempt = 0; attempt < 2; attempt++) {
        s_lora_serial.write(cfg_reg, 12);
        s_lora_serial.flush();
        delay(250);

        if (s_lora_serial.available()) {
            uint8_t resp = s_lora_serial.read();
            if (resp == 0xC1) {
                ack_ok = true;
                while (s_lora_serial.available()) {
                    s_lora_serial.read();
                }
                break;
            }
        }
        delay(150);
    }

    set_mode(LOW, LOW);
    wait_aux_ready(500);

    s_initialized = true;
    return ack_ok;
}

bool subsense_lora_sx126x_send(const uint8_t* data, size_t len, uint16_t target_addr, uint8_t channel) {
    if (!s_initialized || data == NULL || len == 0) return false;

    digitalWrite(LORA_PIN_M0, LOW);
    digitalWrite(LORA_PIN_M1, LOW);

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
    if (!s_initialized || out_buf == NULL || max_len == 0) return 0;

    size_t avail = s_lora_serial.available();
    if (avail == 0) return 0;

    delay(40);
    avail = s_lora_serial.available();

    if (s_rssi_enabled && avail < 2) return 0;

    size_t bytes_to_read = avail > (max_len + (s_rssi_enabled ? 1 : 0))
                           ? (max_len + (s_rssi_enabled ? 1 : 0))
                           : avail;

    uint8_t temp_buf[256];
    size_t actual_read = s_lora_serial.readBytes(temp_buf, bytes_to_read);

    if (actual_read == 0) return 0;

    if (s_rssi_enabled && actual_read >= 2) {
        uint8_t raw_rssi = temp_buf[actual_read - 1];
        if (out_rssi_dbm != NULL) {
            *out_rssi_dbm = -(int16_t)(256 - raw_rssi);
        }
        size_t payload_len = actual_read - 1;
        memcpy(out_buf, temp_buf, payload_len);
        return payload_len;
    } else {
        if (out_rssi_dbm != NULL) *out_rssi_dbm = -70;
        memcpy(out_buf, temp_buf, actual_read);
        return actual_read;
    }
}

void subsense_lora_sx126x_sleep(void) {
    set_mode(HIGH, HIGH);
}

void subsense_lora_sx126x_wakeup(void) {
    set_mode(LOW, LOW);
    wait_aux_ready(200);
}

bool subsense_lora_sx126x_is_ready(void) {
    return s_initialized && (digitalRead(LORA_PIN_AUX) == HIGH);
}
