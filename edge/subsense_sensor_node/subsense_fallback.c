/**
 * @file subsense_fallback.c
 * @brief SubSense Safety Fallback Implementation.
 */

#include "subsense_fallback.h"
#include <stdio.h>
#include <math.h>

const SubSenseFallbackThresholds G_SUBSENSE_DEFAULT_FALLBACK = {
    .max_tilt_deg = 4.0f,
    .max_tilt_rate_deg = 1.5f,
    .max_vibration_g = 1.2f,
    .max_displacement_mm = 12.0f,
    .max_crack_state = 0.8f,
};

bool subsense_fallback_evaluate(
    float tilt_cur,
    float tilt_rate,
    float vib_peak,
    float disp_delta,
    float crack_state,
    char* out_reason,
    size_t reason_max_len,
    bool* out_siren_trigger
) {
    if (out_siren_trigger) *out_siren_trigger = false;

    // Check catastrophic sudden displacement (roof collapse precursor)
    if (fabsf(disp_delta) >= G_SUBSENSE_DEFAULT_FALLBACK.max_displacement_mm) {
        if (out_reason && reason_max_len > 0) {
            snprintf(out_reason, reason_max_len, "RAW_DISP_EXCEEDED (%.2fmm >= %.1fmm)", 
                     fabsf(disp_delta), G_SUBSENSE_DEFAULT_FALLBACK.max_displacement_mm);
        }
        if (out_siren_trigger) *out_siren_trigger = true;
        return true;
    }

    // Check severe tilt rate of change (strata shear/fault slip)
    if (fabsf(tilt_rate) >= G_SUBSENSE_DEFAULT_FALLBACK.max_tilt_rate_deg) {
        if (out_reason && reason_max_len > 0) {
            snprintf(out_reason, reason_max_len, "RAW_TILT_RATE_EXCEEDED (%.2fdeg >= %.1fdeg)", 
                     fabsf(tilt_rate), G_SUBSENSE_DEFAULT_FALLBACK.max_tilt_rate_deg);
        }
        if (out_siren_trigger) *out_siren_trigger = true;
        return true;
    }

    // Check violent seismic shockwave (rockburst)
    if (fabsf(vib_peak) >= G_SUBSENSE_DEFAULT_FALLBACK.max_vibration_g) {
        if (out_reason && reason_max_len > 0) {
            snprintf(out_reason, reason_max_len, "RAW_VIB_PEAK_EXCEEDED (%.2fg >= %.1fg)", 
                     fabsf(vib_peak), G_SUBSENSE_DEFAULT_FALLBACK.max_vibration_g);
        }
        if (out_siren_trigger) *out_siren_trigger = true;
        return true;
    }

    // Check fissure opening latch
    if (crack_state >= G_SUBSENSE_DEFAULT_FALLBACK.max_crack_state) {
        if (out_reason && reason_max_len > 0) {
            snprintf(out_reason, reason_max_len, "RAW_CRACK_LATCHED (%.2f >= %.1f)", 
                     crack_state, G_SUBSENSE_DEFAULT_FALLBACK.max_crack_state);
        }
        if (out_siren_trigger) *out_siren_trigger = true;
        return true;
    }

    // Check gross absolute tilt
    if (fabsf(tilt_cur) >= G_SUBSENSE_DEFAULT_FALLBACK.max_tilt_deg) {
        if (out_reason && reason_max_len > 0) {
            snprintf(out_reason, reason_max_len, "RAW_ABSOLUTE_TILT (%.2fdeg >= %.1fdeg)", 
                     fabsf(tilt_cur), G_SUBSENSE_DEFAULT_FALLBACK.max_tilt_deg);
        }
        if (out_siren_trigger) *out_siren_trigger = true;
        return true;
    }

    if (out_reason && reason_max_len > 0) {
        snprintf(out_reason, reason_max_len, "NOMINAL");
    }
    return false;
}
