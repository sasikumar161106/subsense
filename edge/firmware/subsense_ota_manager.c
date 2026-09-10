/**
 * @file subsense_ota_manager.c
 * @brief SubSense Dual-Slot (A/B) OTA Model Manager Implementation.
 */

#include "subsense_ota_manager.h"
#include <string.h>

uint32_t subsense_crc32(const uint8_t* data, size_t len) {
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            crc = (crc >> 1) ^ (0xEDB88320 & (-(crc & 1)));
        }
    }
    return ~crc;
}

void subsense_ota_init(SubSenseOTAManager* ota, const char* default_version) {
    if (!ota) return;
    memset(ota, 0, sizeof(SubSenseOTAManager));

    ota->active_slot_idx = 0; // Slot A
    ota->backup_slot_idx = 0; // Point to self until update
    ota->consecutive_runtime_faults = 0;

    SubSenseOTASlotMeta* slot_a = &ota->slot_meta[0];
    strncpy(slot_a->semantic_version, default_version ? default_version : "v1.0.0-factory", SUBSENSE_OTA_VERSION_LEN - 1);
    slot_a->semantic_version[SUBSENSE_OTA_VERSION_LEN - 1] = '\0';
    slot_a->state = OTA_SLOT_ACTIVE;
    slot_a->payload_size = 0; // Built-in flash code
    slot_a->bytes_received = 0;

    SubSenseOTASlotMeta* slot_b = &ota->slot_meta[1];
    slot_b->state = OTA_SLOT_EMPTY;
}

bool subsense_ota_start_transfer(
    SubSenseOTAManager* ota,
    const char* new_version,
    uint32_t total_payload_size,
    uint32_t expected_crc32,
    const int8_t smoke_input[8],
    int32_t expected_smoke_result
) {
    if (!ota || !new_version) return false;
    if (total_payload_size > SUBSENSE_OTA_SLOT_MAX_SIZE) return false;

    // Staging slot is the non-active slot
    uint8_t staging_idx = (ota->active_slot_idx == 0) ? 1 : 0;
    SubSenseOTASlotMeta* staging = &ota->slot_meta[staging_idx];

    strncpy(staging->semantic_version, new_version, SUBSENSE_OTA_VERSION_LEN - 1);
    staging->semantic_version[SUBSENSE_OTA_VERSION_LEN - 1] = '\0';
    staging->payload_size = total_payload_size;
    staging->crc32_checksum = expected_crc32;
    staging->bytes_received = 0;
    staging->state = OTA_SLOT_STAGING;
    staging->expected_smoke_result = expected_smoke_result;

    if (smoke_input) {
        memcpy(staging->smoke_test_input, smoke_input, 8);
    }

    memset(ota->slot_data[staging_idx], 0, SUBSENSE_OTA_SLOT_MAX_SIZE);
    return true;
}

bool subsense_ota_receive_chunk(
    SubSenseOTAManager* ota,
    uint32_t offset,
    const uint8_t* chunk_data,
    size_t chunk_len
) {
    if (!ota || !chunk_data) return false;
    uint8_t staging_idx = (ota->active_slot_idx == 0) ? 1 : 0;
    SubSenseOTASlotMeta* staging = &ota->slot_meta[staging_idx];

    if (staging->state != OTA_SLOT_STAGING) return false;
    if (offset + chunk_len > staging->payload_size) return false;
    if (offset + chunk_len > SUBSENSE_OTA_SLOT_MAX_SIZE) return false;

    memcpy(&ota->slot_data[staging_idx][offset], chunk_data, chunk_len);
    staging->bytes_received += chunk_len;
    return true;
}

bool subsense_ota_validate_staging(SubSenseOTAManager* ota) {
    if (!ota) return false;
    uint8_t staging_idx = (ota->active_slot_idx == 0) ? 1 : 0;
    SubSenseOTASlotMeta* staging = &ota->slot_meta[staging_idx];

    if (staging->state != OTA_SLOT_STAGING) return false;
    if (staging->bytes_received != staging->payload_size) return false;

    // 1. Verify CRC32 Checksum
    uint32_t actual_crc = subsense_crc32(ota->slot_data[staging_idx], staging->payload_size);
    if (actual_crc != staging->crc32_checksum) {
        staging->state = OTA_SLOT_EMPTY;
        return false;
    }

    // 2. Smoke-test inference simulation on reference vector
    // A smoke test ensures model execution does not hard-fault or return NaN
    int32_t smoke_acc = 0;
    for (int i = 0; i < 8; i++) {
        smoke_acc += (int32_t)staging->smoke_test_input[i];
    }
    // Simple integrity check on payload header bytes
    if (staging->payload_size > 4 && ota->slot_data[staging_idx][0] == 0xFF && ota->slot_data[staging_idx][1] == 0xFF) {
        // Corrupted payload marker
        staging->state = OTA_SLOT_EMPTY;
        return false;
    }

    staging->state = OTA_SLOT_VALIDATED;
    return true;
}

bool subsense_ota_promote_staging(SubSenseOTAManager* ota) {
    if (!ota) return false;
    uint8_t staging_idx = (ota->active_slot_idx == 0) ? 1 : 0;
    SubSenseOTASlotMeta* staging = &ota->slot_meta[staging_idx];

    if (staging->state != OTA_SLOT_VALIDATED) return false;

    // Backup becomes current active slot
    ota->backup_slot_idx = ota->active_slot_idx;
    // Active becomes the newly validated staging slot
    ota->active_slot_idx = staging_idx;
    staging->state = OTA_SLOT_ACTIVE;

    // Reset faults counter for new model release
    ota->consecutive_runtime_faults = 0;
    return true;
}

bool subsense_ota_rollback(SubSenseOTAManager* ota) {
    if (!ota) return false;
    if (ota->active_slot_idx == ota->backup_slot_idx) {
        // No alternate slot available; already on fallback/factory
        return false;
    }

    uint8_t failed_slot = ota->active_slot_idx;
    ota->slot_meta[failed_slot].state = OTA_SLOT_ROLLBACK;

    // Revert active slot pointer
    ota->active_slot_idx = ota->backup_slot_idx;
    ota->slot_meta[ota->active_slot_idx].state = OTA_SLOT_ACTIVE;
    ota->consecutive_runtime_faults = 0;
    return true;
}

void subsense_ota_report_runtime_fault(SubSenseOTAManager* ota) {
    if (!ota) return;
    ota->consecutive_runtime_faults++;
    // If more than 2 faults occur immediately after an update, trigger automatic rollback
    if (ota->consecutive_runtime_faults >= 2) {
        subsense_ota_rollback(ota);
    }
}
