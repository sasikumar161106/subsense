/**
 * @file subsense_lora_sx126x.h
 * @brief Native ESP32 C++ Driver for LoRa SX126x (EBYTE E22-900T22S / SX1262).
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

#ifndef LORA_PIN_RX
#define LORA_PIN_RX     16
#endif

#ifndef LORA_PIN_TX
#define LORA_PIN_TX     17
#endif

#ifndef LORA_PIN_M0
#define LORA_PIN_M0     25
#endif

#ifndef LORA_PIN_M1
#define LORA_PIN_M1     26
#endif

#ifndef LORA_PIN_AUX
#define LORA_PIN_AUX    27
#endif

#define LORA_DEFAULT_FREQ_MHZ       865
#define LORA_DEFAULT_CHANNEL_OFFSET 15
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

#endif
