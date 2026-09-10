/**
 * @file subsense_power_mgmt.c
 * @brief SubSense Power Management Implementation.
 */

#include "subsense_power_mgmt.h"

#ifdef ESP_PLATFORM
#include "esp_sleep.h"
#include "esp_log.h"
#else
#include <stdio.h>
#endif

void subsense_power_init(const SubSensePowerConfig* config) {
    if (!config) return;
    // On native ESP32 hardware:
#ifdef ESP_PLATFORM
    if (config->mode == POWER_MODE_BATTERY_DUTY_CYCLE) {
        // Disable unnecessary peripherals before sleep
        esp_sleep_enable_timer_wakeup((uint64_t)config->sampling_interval_ms * 1000ULL);
    }
#endif
}

float subsense_power_calc_avg_current_ma(const SubSensePowerConfig* config) {
    if (!config || config->sampling_interval_ms == 0) return 0.0f;

    if (config->mode == POWER_MODE_MAINS_CONTINUOUS) {
        return config->active_current_ma;
    }

    float active_ms = (float)config->active_duration_us / 1000.0f;
    float interval_ms = (float)config->sampling_interval_ms;
    if (active_ms > interval_ms) active_ms = interval_ms;
    float sleep_ms = interval_ms - active_ms;

    float sleep_current_ma = config->deep_sleep_current_ua / 1000.0f;

    float avg_ma = (config->active_current_ma * active_ms + sleep_current_ma * sleep_ms) / interval_ms;
    return avg_ma;
}

float subsense_power_calc_battery_life_months(const SubSensePowerConfig* config) {
    float avg_current_ma = subsense_power_calc_avg_current_ma(config);
    if (avg_current_ma <= 0.0f || !config) return 0.0f;

    // Standard usable capacity with 85% battery discharge derating
    float usable_capacity_mah = config->battery_capacity_mah * 0.85f;
    float operating_hours = usable_capacity_mah / avg_current_ma;
    float operating_months = operating_hours / (24.0f * 30.4375f);
    return operating_months;
}

void subsense_power_enter_sleep(uint32_t sleep_duration_ms) {
#ifdef ESP_PLATFORM
    esp_sleep_enable_timer_wakeup((uint64_t)sleep_duration_ms * 1000ULL);
    esp_deep_sleep_start();
#else
    // Host/Desktop simulation mode
    (void)sleep_duration_ms;
#endif
}
