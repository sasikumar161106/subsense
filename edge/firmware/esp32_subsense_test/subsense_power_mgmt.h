/**
 * @file subsense_power_mgmt.h
 * @brief SubSense ESP32 Power Management and Duty-Cycling Subsystem.
 * @note Implements deep-sleep timer wakeup to achieve multi-year operating life.
 */

#ifndef SUBSENSE_POWER_MGMT_H
#define SUBSENSE_POWER_MGMT_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    POWER_MODE_MAINS_CONTINUOUS = 0, // Gateway: always awake, mains/solar backed
    POWER_MODE_BATTERY_DUTY_CYCLE    // Node: deep-sleep duty-cycled
} SubSensePowerMode;

typedef struct {
    SubSensePowerMode mode;
    uint32_t sampling_interval_ms;  // e.g. 1000ms or 5000ms
    uint32_t active_duration_us;     // Measured active inference + sensor duration
    float active_current_ma;         // e.g. 50 mA during compute
    float deep_sleep_current_ua;     // e.g. 10 uA during RTC deep-sleep
    float battery_capacity_mah;      // e.g. 2600 mAh 18650 cell
} SubSensePowerConfig;

/**
 * @brief Initialize power management profile.
 */
void subsense_power_init(const SubSensePowerConfig* config);

/**
 * @brief Calculate average current draw in milliamperes.
 */
float subsense_power_calc_avg_current_ma(const SubSensePowerConfig* config);

/**
 * @brief Estimate projected battery life in months.
 */
float subsense_power_calc_battery_life_months(const SubSensePowerConfig* config);

/**
 * @brief Enter low-power sleep until the next inference epoch.
 * @param sleep_duration_ms Sleep duration in milliseconds.
 */
void subsense_power_enter_sleep(uint32_t sleep_duration_ms);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_POWER_MGMT_H
