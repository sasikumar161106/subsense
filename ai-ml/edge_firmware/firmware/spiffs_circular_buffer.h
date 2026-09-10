/**
 * SubSense Layer 4 - Circular SPIFFS Flash Event Buffer
 * Zero-connectivity offline event buffering on ESP32-S3 SPI flash.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPIFFS_BUFFER_CAPACITY 256

typedef struct {
    uint32_t record_id;
    uint32_t timestamp_sec;
    char node_id[16];
    float anomaly_score;
    float reconstruction_error;
    bool corroborated;
    bool is_synced;
} SPIFFSEventRecord;

/**
 * Initializes the circular SPIFFS flash buffer.
 */
void spiffs_buffer_init(void);

/**
 * Appends an incident record to the circular buffer.
 * If buffer is full, automatically rolls over and overwrites oldest record.
 */
bool spiffs_buffer_write(const SPIFFSEventRecord* record);

/**
 * Returns number of unacknowledged/unsynced records waiting in buffer.
 */
size_t spiffs_buffer_get_unsynced_count(void);

/**
 * Reads up to max_records unsynced records without removing them.
 */
size_t spiffs_buffer_peek_unsynced(SPIFFSEventRecord* out_records, size_t max_records);

/**
 * Acknowledges receipt of records up to record_id, marking them as synced.
 */
void spiffs_buffer_mark_synced_up_to(uint32_t record_id);

/**
 * Returns total records ever written to the buffer.
 */
uint32_t spiffs_buffer_get_total_written(void);

/**
 * Returns true if buffer has experienced rollover overwrite.
 */
bool spiffs_buffer_has_overflowed(void);

#ifdef __cplusplus
}
#endif
