/**
 * @file subsense_ota_manager.h
 * @brief SubSense Semantic-Versioned Dual-Slot (A/B) OTA Model Manager.
 * @note Supports chunked mesh transfer, checksum validation, smoke-test inference,
 *       and automated rollback to last known-good slot.
 */

#ifndef SUBSENSE_OTA_MANAGER_H
#define SUBSENSE_OTA_MANAGER_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUBSENSE_OTA_SLOT_MAX_SIZE   (32 * 1024)  // 32 KB flash partition per slot
#define SUBSENSE_OTA_CHUNK_SIZE      256          // Mesh payload chunk size
#define SUBSENSE_OTA_VERSION_LEN     32

typedef enum {
    OTA_SLOT_EMPTY = 0,
    OTA_SLOT_STAGING,
    OTA_SLOT_VALIDATED,
    OTA_SLOT_ACTIVE,
    OTA_SLOT_ROLLBACK
} SubSenseOTASlotState;

typedef struct {
    char semantic_version[SUBSENSE_OTA_VERSION_LEN];
    uint32_t payload_size;
    uint32_t crc32_checksum;
    uint32_t bytes_received;
    SubSenseOTASlotState state;
    int8_t smoke_test_input[8];
    int32_t expected_smoke_result;
} SubSenseOTASlotMeta;

typedef struct {
    uint8_t active_slot_idx;     // 0 for Slot A, 1 for Slot B
    uint8_t backup_slot_idx;     // Rollback target
    SubSenseOTASlotMeta slot_meta[2];
    uint8_t slot_data[2][SUBSENSE_OTA_SLOT_MAX_SIZE];
    uint32_t consecutive_runtime_faults;
} SubSenseOTAManager;

/**
 * @brief Initialize the dual-slot OTA manager with default baked-in model in Slot A.
 */
void subsense_ota_init(SubSenseOTAManager* ota, const char* default_version);

/**
 * @brief Start receiving a new semantic-versioned model into the staging slot.
 */
bool subsense_ota_start_transfer(
    SubSenseOTAManager* ota,
    const char* new_version,
    uint32_t total_payload_size,
    uint32_t expected_crc32,
    const int8_t smoke_input[8],
    int32_t expected_smoke_result
);

/**
 * @brief Receive a chunk from mesh relay or Wi-Fi/4G.
 */
bool subsense_ota_receive_chunk(
    SubSenseOTAManager* ota,
    uint32_t offset,
    const uint8_t* chunk_data,
    size_t chunk_len
);

/**
 * @brief Validate staging slot: verify CRC32 and execute smoke-test inference.
 * @return True if model is valid and safe to promote.
 */
bool subsense_ota_validate_staging(SubSenseOTAManager* ota);

/**
 * @brief Promote validated staging slot to active slot.
 */
bool subsense_ota_promote_staging(SubSenseOTAManager* ota);

/**
 * @brief Automated rollback to the last known-good backup slot.
 */
bool subsense_ota_rollback(SubSenseOTAManager* ota);

/**
 * @brief Report a runtime crash or inference failure. Triggers auto-rollback if threshold exceeded.
 */
void subsense_ota_report_runtime_fault(SubSenseOTAManager* ota);

/**
 * @brief Calculate CRC32 checksum over a byte buffer.
 */
uint32_t subsense_crc32(const uint8_t* data, size_t len);

#ifdef __cplusplus
}
#endif

#endif // SUBSENSE_OTA_MANAGER_H
