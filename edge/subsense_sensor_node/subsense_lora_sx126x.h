/**
 * @file subsense_lora_sx126x.h
 * @brief Native ESP32 C++ Driver for LoRa SX126x (EBYTE E22-900T22S / SX1262).
 * @note Ported directly from the loramain project (sx126x.py).
 *       Configured for 865 MHz (India ISM band), 22 dBm TX power, 2400 bps air speed,
 *       Fixed Transmission Mode with automatic packet RSSI output enabled.
 */

#ifndef SUBSENSE_LORA_SX126X_H
#define SUBSENSE_LORA_SX126X_H

#include <Arduino.h>
#include <HardwareSerial.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Default Hardware Pin Mapping for ESP32 DevKit
#ifndef LORA_PIN_RX
#define LORA_PIN_RX     16  // ESP32 RX2 <- SX126x TXD
#endif

#ifndef LORA_PIN_TX
#define LORA_PIN_TX     17  // ESP32 TX2 -> SX126x RXD
#endif

#ifndef LORA_PIN_M0
#define LORA_PIN_M0     25  // ESP32 GPIO 25 -> SX126x M0
#endif

#ifndef LORA_PIN_M1
#define LORA_PIN_M1     26  // ESP32 GPIO 26 -> SX126x M1
#endif

#ifndef LORA_PIN_AUX
#define LORA_PIN_AUX    27  // ESP32 GPIO 27 <- SX126x AUX (Input/Busy)
#endif

// Default Radio Configuration (Matching loramain settings.py)
#define LORA_DEFAULT_FREQ_MHZ       865
#define LORA_DEFAULT_CHANNEL_OFFSET 15   // 865 MHz - 850 MHz = 15
#define LORA_DEFAULT_TX_POWER_DBM   22
#define LORA_DEFAULT_AIR_SPEED_BPS  2400
#define LORA_UART_BAUDRATE          9600
#define LORA_BROADCAST_ADDR         0xFFFF

bool subsense_lora_sx126x_init(uint16_t freq_mhz, uint16_t node_addr, bool enable_rssi);
bool subsense_lora_sx126x_send(const uint8_t* data, size_t len, uint16_t target_addr, uint8_t channel);
size_t subsense_lora_sx126x_receive(uint8_t* out_buf, size_t max_len, int16_t* out_rssi_dbm);
void subsense_lora_sx126x_sleep(void);
void subsense_lora_sx126x_wakeup(void);
bool subsense_lora_sx126x_is_ready(void);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_LORA_SX126X_H
