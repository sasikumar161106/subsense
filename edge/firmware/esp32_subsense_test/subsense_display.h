/**
 * @file subsense_display.h
 * @brief SubSense Sensor Node Health Status Display Driver (I2C SSD1306 OLED 128x64).
 * @note EXCLUSIVE TO SENSOR NODE (Board 1) ONLY.
 *       Relay Node (Board 2) and Gateway Node (Board 3) DO NOT use this module.
 */

#ifndef SUBSENSE_DISPLAY_H
#define SUBSENSE_DISPLAY_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Default I2C Configuration for ESP32 DevKit
#define SUBSENSE_OLED_DEFAULT_SDA   21
#define SUBSENSE_OLED_DEFAULT_SCL   22
#define SUBSENSE_OLED_DEFAULT_ADDR  0x3C

/**
 * @brief Complete health and operational telemetry state for Sensor Node display.
 */
typedef struct {
    const char* node_id;          /**< Node identifier, e.g. "SS-PANEL7-N042" */
    float       tilt_deg;         /**< Current MPU6050 tilt angle in degrees */
    float       vibration_rms;    /**< Current MPU6050 vibration RMS in mm/s */
    float       anomaly_score;    /**< Current TinyML on-device anomaly score [0.0 - 1.0] */
    int8_t      battery_percent;  /**< State of charge (0 - 100%) */
    int8_t      rssi_dbm;         /**< ESP-NOW link margin in dBm (-30 to -95) */
    uint8_t     hop_count;        /**< Mesh hop count to gateway (0 for sensor node origin) */
    uint32_t    packets_sent;     /**< Cumulative telemetry packets dispatched */
    uint32_t    uptime_seconds;   /**< Node uptime in seconds */
    bool        sensor_ok;        /**< True if MPU6050 I2C communication is healthy */
    bool        mesh_ok;          /**< True if ESP-NOW transport initialized successfully */
    bool        siren_active;     /**< True if local evacuation siren / strobe is active */
    const char* status_text;      /**< "NOMINAL", "WARNING", "CRITICAL", or "CALIBRATING" */
} SubSenseNodeDisplayData;

/**
 * @brief Initialize the I2C OLED display on specified SDA/SCL pins.
 * @param sda_pin GPIO pin for I2C SDA (default 21).
 * @param scl_pin GPIO pin for I2C SCL (default 22).
 * @param i2c_addr I2C 7-bit slave address (default 0x3C).
 * @return True if display acknowledged I2C communication, false if not connected.
 */
bool subsense_display_init(int sda_pin, int scl_pin, uint8_t i2c_addr);

/**
 * @brief Check whether the OLED display hardware is present and responding.
 */
bool subsense_display_is_available(void);

/**
 * @brief Render a SubSense boot splash screen with node identifier and firmware version.
 */
void subsense_display_boot_screen(const char* node_id, const char* version);

/**
 * @brief Update the display with live node health metrics and sensor readings.
 * @param data Pointer to SubSenseNodeDisplayData snapshot.
 */
void subsense_display_update_health(const SubSenseNodeDisplayData* data);

/**
 * @brief Render high-visibility evacuation screen when critical subsidence is detected.
 * @param node_id Node identifier that detected the breach.
 * @param tilt_deg Measured tilt angle.
 * @param vib_rms Measured vibration velocity.
 * @param message Action directive (e.g. "EVACUATE PANEL NOW").
 */
void subsense_display_emergency_alert(
    const char* node_id,
    float tilt_deg,
    float vib_rms,
    const char* message
);

/**
 * @brief Put display into low-power sleep mode during deep sleep cycles.
 */
void subsense_display_power_save(bool enable_sleep);

/**
 * @brief Clear the display buffer and blank the screen.
 */
void subsense_display_clear(void);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_DISPLAY_H
