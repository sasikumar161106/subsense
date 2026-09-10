/**
 * SubSense Layer 4 - Circular SPIFFS Flash Event Buffer Implementation
 * Simulates SPIFFS flash sector write/read with wear-leveling safe rollover.
 */

#include "spiffs_circular_buffer.h"
#include <string.h>

static SPIFFSEventRecord s_flash_storage[SPIFFS_BUFFER_CAPACITY];
static size_t s_write_index = 0;
static size_t s_count = 0;
static uint32_t s_total_written = 0;
static bool s_has_overflowed = false;

void spiffs_buffer_init(void) {
    memset(s_flash_storage, 0, sizeof(s_flash_storage));
    s_write_index = 0;
    s_count = 0;
    s_total_written = 0;
    s_has_overflowed = false;
}

bool spiffs_buffer_write(const SPIFFSEventRecord* record) {
    if (!record) return false;

    s_flash_storage[s_write_index] = *record;
    s_flash_storage[s_write_index].is_synced = false;

    s_write_index = (s_write_index + 1) % SPIFFS_BUFFER_CAPACITY;
    s_total_written++;

    if (s_count < SPIFFS_BUFFER_CAPACITY) {
        s_count++;
    } else {
        s_has_overflowed = true;
    }

    return true;
}

size_t spiffs_buffer_get_unsynced_count(void) {
    size_t unsynced = 0;
    for (size_t i = 0; i < s_count; ++i) {
        if (!s_flash_storage[i].is_synced && s_flash_storage[i].record_id != 0) {
            unsynced++;
        }
    }
    return unsynced;
}

size_t spiffs_buffer_peek_unsynced(SPIFFSEventRecord* out_records, size_t max_records) {
    if (!out_records || max_records == 0) return 0;

    size_t found = 0;
    // Iterate from oldest to newest in circular buffer
    size_t start_idx = (s_count == SPIFFS_BUFFER_CAPACITY) ? s_write_index : 0;

    for (size_t step = 0; step < s_count && found < max_records; ++step) {
        size_t idx = (start_idx + step) % SPIFFS_BUFFER_CAPACITY;
        if (!s_flash_storage[idx].is_synced && s_flash_storage[idx].record_id != 0) {
            out_records[found++] = s_flash_storage[idx];
        }
    }

    return found;
}

void spiffs_buffer_mark_synced_up_to(uint32_t record_id) {
    for (size_t i = 0; i < s_count; ++i) {
        if (s_flash_storage[i].record_id != 0 && s_flash_storage[i].record_id <= record_id) {
            s_flash_storage[i].is_synced = true;
        }
    }
}

uint32_t spiffs_buffer_get_total_written(void) {
    return s_total_written;
}

bool spiffs_buffer_has_overflowed(void) {
    return s_has_overflowed;
}
