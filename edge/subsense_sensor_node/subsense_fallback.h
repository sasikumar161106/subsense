/**
 * @file subsense_fallback.h
 * @brief SubSense Hard-Coded Safety Fallback for Runtime Failure & Corruption.
 * @note Implements failsafe detection on raw sensor readings when ML pipeline is degraded.
 */

#ifndef SUBSENSE_FALLBACK_H
#define SUBSENSE_FALLBACK_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    float max_tilt_deg;          // e.g. 4.0 degrees
    float max_tilt_rate_deg;     // e.g. 1.5 degrees / window
    float max_vibration_g;       // e.g. 1.2 g
    float max_displacement_mm;   // e.g. 12.0 mm
    float max_crack_state;       // e.g. 0.8 (graded 0 to 1)
} SubSenseFallbackThresholds;

/**
 * @brief Default conservative safety thresholds permanently compiled into firmware.
 */
extern const SubSenseFallbackThresholds G_SUBSENSE_DEFAULT_FALLBACK;

/**
 * @brief Evaluate raw sensor values against hard-coded physical limits.
 * @param tilt_cur Current raw tilt in degrees.
 * @param tilt_rate Angular change over window in degrees.
 * @param vib_peak Peak raw vibration in g.
 * @param disp_delta Relative displacement stretch in mm.
 * @param crack_state Graded crack aperture (0.0 to 1.0).
 * @param out_reason Buffer of at least 64 bytes to receive triggering reason.
 * @param out_siren_trigger Set to true if hazard demands immediate local siren.
 * @return True if hazard threshold breached, false if nominal.
 */
bool subsense_fallback_evaluate(
    float tilt_cur,
    float tilt_rate,
    float vib_peak,
    float disp_delta,
    float crack_state,
    char* out_reason,
    size_t reason_max_len,
    bool* out_siren_trigger
);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_FALLBACK_H
