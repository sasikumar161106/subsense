/**
 * @file subsense_display.cpp
 * @brief SubSense Sensor Node Health Status Display Implementation (I2C SSD1306 OLED 128x64).
 * @note EXCLUSIVE TO SENSOR NODE (Board 1) ONLY.
 *       Relay Node (Board 2) and Gateway Node (Board 3) DO NOT use this module.
 */

#include <Arduino.h>
#include <Wire.h>
#include <string.h>
#include <stdio.h>
#include "subsense_display.h"

#define SSD1306_WIDTH   128
#define SSD1306_HEIGHT  64
#define SSD1306_BUFFER_SIZE ((SSD1306_WIDTH * SSD1306_HEIGHT) / 8)

static bool     s_display_present = false;
static uint8_t  s_i2c_addr = SUBSENSE_OLED_DEFAULT_ADDR;
static uint8_t  s_buffer[SSD1306_BUFFER_SIZE];

// ==============================================================================
// 1. Built-in 5x7 ASCII Font Table (Chars 32 ' ' to 126 '~')
// ==============================================================================
static const uint8_t FONT_5X7[][5] = {
    {0x00, 0x00, 0x00, 0x00, 0x00}, // 32 ' '
    {0x00, 0x00, 0x5F, 0x00, 0x00}, // 33 '!'
    {0x00, 0x07, 0x00, 0x07, 0x00}, // 34 '"'
    {0x14, 0x7F, 0x14, 0x7F, 0x14}, // 35 '#'
    {0x24, 0x2A, 0x7F, 0x2A, 0x12}, // 36 '$'
    {0x23, 0x13, 0x08, 0x64, 0x62}, // 37 '%'
    {0x36, 0x49, 0x55, 0x22, 0x50}, // 38 '&'
    {0x00, 0x05, 0x03, 0x00, 0x00}, // 39 '''
    {0x00, 0x1C, 0x22, 0x41, 0x00}, // 40 '('
    {0x00, 0x41, 0x22, 0x1C, 0x00}, // 41 ')'
    {0x08, 0x2A, 0x1C, 0x2A, 0x08}, // 42 '*'
    {0x08, 0x08, 0x3E, 0x08, 0x08}, // 43 '+'
    {0x00, 0x50, 0x30, 0x00, 0x00}, // 44 ','
    {0x08, 0x08, 0x08, 0x08, 0x08}, // 45 '-'
    {0x00, 0x60, 0x60, 0x00, 0x00}, // 46 '.'
    {0x20, 0x10, 0x08, 0x04, 0x02}, // 47 '/'
    {0x3E, 0x51, 0x49, 0x45, 0x3E}, // 48 '0'
    {0x00, 0x42, 0x7F, 0x40, 0x00}, // 49 '1'
    {0x42, 0x61, 0x51, 0x49, 0x46}, // 50 '2'
    {0x21, 0x41, 0x45, 0x4B, 0x31}, // 51 '3'
    {0x18, 0x14, 0x12, 0x7F, 0x10}, // 52 '4'
    {0x27, 0x45, 0x45, 0x45, 0x39}, // 53 '5'
    {0x3C, 0x4A, 0x49, 0x49, 0x30}, // 54 '6'
    {0x01, 0x71, 0x09, 0x05, 0x03}, // 55 '7'
    {0x36, 0x49, 0x49, 0x49, 0x36}, // 56 '8'
    {0x06, 0x49, 0x49, 0x29, 0x1E}, // 57 '9'
    {0x00, 0x36, 0x36, 0x00, 0x00}, // 58 ':'
    {0x00, 0x56, 0x36, 0x00, 0x00}, // 59 ';'
    {0x08, 0x14, 0x22, 0x41, 0x00}, // 60 '<'
    {0x14, 0x14, 0x14, 0x14, 0x14}, // 61 '='
    {0x00, 0x41, 0x22, 0x14, 0x08}, // 62 '>'
    {0x02, 0x01, 0x51, 0x09, 0x06}, // 63 '?'
    {0x32, 0x49, 0x79, 0x41, 0x3E}, // 64 '@'
    {0x7E, 0x11, 0x11, 0x11, 0x7E}, // 65 'A'
    {0x7F, 0x49, 0x49, 0x49, 0x36}, // 66 'B'
    {0x3E, 0x41, 0x41, 0x41, 0x22}, // 67 'C'
    {0x7F, 0x41, 0x41, 0x22, 0x1C}, // 68 'D'
    {0x7F, 0x49, 0x49, 0x49, 0x41}, // 69 'E'
    {0x7F, 0x09, 0x09, 0x09, 0x01}, // 70 'F'
    {0x3E, 0x41, 0x49, 0x49, 0x7A}, // 71 'G'
    {0x7F, 0x08, 0x08, 0x08, 0x7F}, // 72 'H'
    {0x00, 0x41, 0x7F, 0x41, 0x00}, // 73 'I'
    {0x20, 0x40, 0x41, 0x3F, 0x01}, // 74 'J'
    {0x7F, 0x08, 0x14, 0x22, 0x41}, // 75 'K'
    {0x7F, 0x40, 0x40, 0x40, 0x40}, // 76 'L'
    {0x7F, 0x02, 0x0C, 0x02, 0x7F}, // 77 'M'
    {0x7F, 0x04, 0x08, 0x10, 0x7F}, // 78 'N'
    {0x3E, 0x41, 0x41, 0x41, 0x3E}, // 79 'O'
    {0x7F, 0x09, 0x09, 0x09, 0x06}, // 80 'P'
    {0x3E, 0x41, 0x51, 0x21, 0x5E}, // 81 'Q'
    {0x7F, 0x09, 0x19, 0x29, 0x46}, // 82 'R'
    {0x46, 0x49, 0x49, 0x49, 0x31}, // 83 'S'
    {0x01, 0x01, 0x7F, 0x01, 0x01}, // 84 'T'
    {0x3F, 0x40, 0x40, 0x40, 0x3F}, // 85 'U'
    {0x1F, 0x20, 0x40, 0x20, 0x1F}, // 86 'V'
    {0x3F, 0x40, 0x38, 0x40, 0x3F}, // 87 'W'
    {0x63, 0x14, 0x08, 0x14, 0x63}, // 88 'X'
    {0x07, 0x08, 0x70, 0x08, 0x07}, // 89 'Y'
    {0x61, 0x51, 0x49, 0x45, 0x43}, // 90 'Z'
    {0x00, 0x7F, 0x41, 0x41, 0x00}, // 91 '['
    {0x02, 0x04, 0x08, 0x10, 0x20}, // 92 '\'
    {0x00, 0x41, 0x41, 0x7F, 0x00}, // 93 ']'
    {0x04, 0x02, 0x01, 0x02, 0x04}, // 94 '^'
    {0x40, 0x40, 0x40, 0x40, 0x40}, // 95 '_'
    {0x00, 0x01, 0x02, 0x04, 0x00}, // 96 '`'
    {0x20, 0x54, 0x54, 0x54, 0x78}, // 97 'a'
    {0x7F, 0x48, 0x44, 0x44, 0x38}, // 98 'b'
    {0x38, 0x44, 0x44, 0x44, 0x20}, // 99 'c'
    {0x38, 0x44, 0x44, 0x48, 0x7F}, // 100 'd'
    {0x38, 0x54, 0x54, 0x54, 0x18}, // 101 'e'
    {0x08, 0x7E, 0x09, 0x01, 0x02}, // 102 'f'
    {0x0C, 0x52, 0x52, 0x52, 0x3E}, // 103 'g'
    {0x7F, 0x08, 0x04, 0x04, 0x78}, // 104 'h'
    {0x00, 0x44, 0x7D, 0x40, 0x00}, // 105 'i'
    {0x20, 0x40, 0x44, 0x3D, 0x00}, // 106 'j'
    {0x7F, 0x10, 0x28, 0x44, 0x00}, // 107 'k'
    {0x00, 0x41, 0x7F, 0x40, 0x00}, // 108 'l'
    {0x7C, 0x04, 0x18, 0x04, 0x78}, // 109 'm'
    {0x7C, 0x08, 0x04, 0x04, 0x78}, // 110 'n'
    {0x38, 0x44, 0x44, 0x44, 0x38}, // 111 'o'
    {0x7C, 0x14, 0x14, 0x14, 0x08}, // 112 'p'
    {0x08, 0x14, 0x14, 0x18, 0x7C}, // 113 'q'
    {0x7C, 0x08, 0x04, 0x04, 0x08}, // 114 'r'
    {0x48, 0x54, 0x54, 0x54, 0x20}, // 115 's'
    {0x04, 0x3F, 0x44, 0x40, 0x20}, // 116 't'
    {0x3C, 0x40, 0x40, 0x20, 0x7C}, // 117 'u'
    {0x1C, 0x20, 0x40, 0x20, 0x1C}, // 118 'v'
    {0x3C, 0x40, 0x30, 0x40, 0x3C}, // 119 'w'
    {0x44, 0x28, 0x10, 0x28, 0x44}, // 120 'x'
    {0x0C, 0x50, 0x50, 0x50, 0x3C}, // 121 'y'
    {0x44, 0x64, 0x54, 0x4C, 0x44}, // 122 'z'
    {0x00, 0x08, 0x36, 0x41, 0x00}, // 123 '{'
    {0x00, 0x00, 0x7F, 0x00, 0x00}, // 124 '|'
    {0x00, 0x41, 0x36, 0x08, 0x00}, // 125 '}'
    {0x08, 0x08, 0x2A, 0x1C, 0x08}, // 126 '~'
};

// ==============================================================================
// 2. I2C SSD1306 Low-Level Commands
// ==============================================================================
static void send_command(uint8_t cmd) {
    if (!s_display_present) return;
    Wire.beginTransmission(s_i2c_addr);
    Wire.write(0x00); // Command byte indicator
    Wire.write(cmd);
    Wire.endTransmission();
}

static void send_commands(const uint8_t* cmds, size_t count) {
    if (!s_display_present) return;
    Wire.beginTransmission(s_i2c_addr);
    Wire.write(0x00);
    for (size_t i = 0; i < count; i++) {
        Wire.write(cmds[i]);
    }
    Wire.endTransmission();
}

static void render_buffer(void) {
    if (!s_display_present) return;

    // Set column address (0 to 127)
    uint8_t col_cmd[] = { 0x21, 0, SSD1306_WIDTH - 1 };
    send_commands(col_cmd, sizeof(col_cmd));

    // Set page address (0 to 7 for 64 lines)
    uint8_t page_cmd[] = { 0x22, 0, (SSD1306_HEIGHT / 8) - 1 };
    send_commands(page_cmd, sizeof(page_cmd));

    // Stream 1024-byte framebuffer in chunks of 16 bytes (ESP32 Wire buffer limit is 32 bytes)
    for (size_t i = 0; i < SSD1306_BUFFER_SIZE; i += 16) {
        Wire.beginTransmission(s_i2c_addr);
        Wire.write(0x40); // Data byte indicator
        for (size_t j = 0; j < 16; j++) {
            Wire.write(s_buffer[i + j]);
        }
        Wire.endTransmission();
    }
}

// ==============================================================================
// 3. Framebuffer Graphic Primitives
// ==============================================================================
void subsense_display_clear(void) {
    memset(s_buffer, 0, sizeof(s_buffer));
}

static void draw_pixel(int x, int y, bool color) {
    if (x < 0 || x >= SSD1306_WIDTH || y < 0 || y >= SSD1306_HEIGHT) return;
    int index = x + (y / 8) * SSD1306_WIDTH;
    int bit = y % 8;
    if (color) {
        s_buffer[index] |= (1 << bit);
    } else {
        s_buffer[index] &= ~(1 << bit);
    }
}

static void draw_hline(int x, int y, int w, bool color) {
    for (int i = 0; i < w; i++) {
        draw_pixel(x + i, y, color);
    }
}

static void draw_vline(int x, int y, int h, bool color) {
    for (int i = 0; i < h; i++) {
        draw_pixel(x, y + i, color);
    }
}

static void draw_rect(int x, int y, int w, int h, bool color) {
    draw_hline(x, y, w, color);
    draw_hline(x, y + h - 1, w, color);
    draw_vline(x, y, h, color);
    draw_vline(x + w - 1, y, h, color);
}

static void fill_rect(int x, int y, int w, int h, bool color) {
    for (int j = 0; j < h; j++) {
        draw_hline(x, y + j, w, color);
    }
}

static void draw_char(int x, int y, char c, bool color, bool invert) {
    if (c < 32 || c > 126) c = '?';
    const uint8_t* glyph = FONT_5X7[c - 32];
    for (int col = 0; col < 5; col++) {
        uint8_t line = glyph[col];
        for (int row = 0; row < 8; row++) {
            bool pixel_on = (line & (1 << row)) != 0;
            draw_pixel(x + col, y + row, invert ? !pixel_on : (pixel_on ? color : !color));
        }
    }
    // 1-pixel inter-character spacing
    for (int row = 0; row < 8; row++) {
        draw_pixel(x + 5, y + row, invert ? true : false);
    }
}

static void draw_string(int x, int y, const char* str, bool color = true, bool invert = false) {
    if (!str) return;
    int cur_x = x;
    while (*str && cur_x < SSD1306_WIDTH) {
        draw_char(cur_x, y, *str, color, invert);
        cur_x += 6; // 5 width + 1 spacing
        str++;
    }
}

static void draw_battery_icon(int x, int y, int8_t percent) {
    draw_rect(x, y, 16, 8, true);
    draw_vline(x + 16, y + 2, 4, true); // Terminal nib

    int fill_w = (percent * 12) / 100;
    if (fill_w < 0) fill_w = 0;
    if (fill_w > 12) fill_w = 12;

    fill_rect(x + 2, y + 2, fill_w, 4, true);
}

static void draw_rssi_bars(int x, int y, int8_t rssi_dbm) {
    // 4 vertical bars indicating signal strength
    int bars = 1;
    if (rssi_dbm >= -65) bars = 4;
    else if (rssi_dbm >= -75) bars = 3;
    else if (rssi_dbm >= -85) bars = 2;

    for (int i = 0; i < 4; i++) {
        int bar_h = 2 + (i * 2);
        int bar_y = y + (8 - bar_h);
        if (i < bars) {
            fill_rect(x + (i * 3), bar_y, 2, bar_h, true);
        } else {
            draw_pixel(x + (i * 3), y + 7, true);
        }
    }
}

// ==============================================================================
// 4. Public API Implementation
// ==============================================================================
bool subsense_display_init(int sda_pin, int scl_pin, uint8_t i2c_addr) {
    s_i2c_addr = i2c_addr;

    Wire.begin(sda_pin, scl_pin);
    Wire.setClock(400000); // 400kHz fast mode

    // 1. Probe I2C bus to check if SSD1306 OLED is physically connected
    Wire.beginTransmission(s_i2c_addr);
    uint8_t error = Wire.endTransmission();

    if (error != 0) {
        Serial.printf("[DISPLAY] OLED not detected on I2C (0x%02X). Sensor node running in headless mode.\n", s_i2c_addr);
        s_display_present = false;
        return false;
    }

    s_display_present = true;

    // 2. SSD1306 128x64 Initialization Sequence
    const uint8_t init_cmds[] = {
        0xAE,             // Display OFF
        0xD5, 0x80,       // Set Display Clock Divide / Oscillator Frequency
        0xA8, 0x3F,       // Set Multiplex Ratio (64 lines)
        0xD3, 0x00,       // Set Display Offset to 0
        0x40 | 0x00,      // Set Display Start Line 0
        0x8D, 0x14,       // Enable Internal Charge Pump Regulator
        0x20, 0x00,       // Set Memory Addressing Mode to Horizontal
        0xA1,             // Set Segment Re-Map (col 127 mapped to SEG0)
        0xC8,             // Set COM Output Scan Direction (re-mapped)
        0xDA, 0x12,       // Set COM Pins Hardware Configuration
        0x81, 0xCF,       // Set Contrast Control (0xCF = bright)
        0xD9, 0xF1,       // Set Pre-Charge Period
        0xDB, 0x40,       // Set VCOMH Deselect Level
        0xA4,             // Entire Display Resume to RAM Content
        0xA6,             // Set Normal Display (non-inverted)
        0xAF              // Display ON
    };

    send_commands(init_cmds, sizeof(init_cmds));
    subsense_display_clear();
    render_buffer();

    Serial.printf("[DISPLAY] I2C OLED (SSD1306 128x64 @ 0x%02X) initialized successfully on SDA=%d, SCL=%d.\n",
                  s_i2c_addr, sda_pin, scl_pin);
    return true;
}

bool subsense_display_is_available(void) {
    return s_display_present;
}

void subsense_display_boot_screen(const char* node_id, const char* version) {
    if (!s_display_present) return;

    subsense_display_clear();

    // Prominent SubSense Branding
    fill_rect(0, 0, SSD1306_WIDTH, 14, true);
    draw_string(8, 3, "SUBSENSE MINE IOT", false, true);

    draw_string(2, 20, "Role : SENSOR NODE");
    
    char node_line[32];
    snprintf(node_line, sizeof(node_line), "ID   : %s", node_id ? node_id : "N-01");
    draw_string(2, 32, node_line);

    char ver_line[32];
    snprintf(ver_line, sizeof(ver_line), "Ver  : %s", version ? version : "v1.3");
    draw_string(2, 44, ver_line);

    draw_string(2, 55, "Health Status: BOOT");
    draw_hline(0, 63, SSD1306_WIDTH, true);

    render_buffer();
}

void subsense_display_update_health(const SubSenseNodeDisplayData* data) {
    if (!s_display_present || !data) return;

    // Check for emergency breach condition
    if (data->siren_active || (data->status_text && strcmp(data->status_text, "CRITICAL") == 0)) {
        subsense_display_emergency_alert(
            data->node_id,
            data->tilt_deg,
            data->vibration_rms,
            "EVACUATE MINE PANEL!"
        );
        return;
    }

    subsense_display_clear();

    // -------------------------------------------------------------------------
    // Header Bar: Node ID | Battery % & Icon | RSSI Bars
    // -------------------------------------------------------------------------
    fill_rect(0, 0, SSD1306_WIDTH, 11, true);

    char header_str[24];
    snprintf(header_str, sizeof(header_str), "%s", data->node_id ? data->node_id : "NODE");
    draw_string(2, 2, header_str, false, true);

    // Battery %
    char bat_str[10];
    snprintf(bat_str, sizeof(bat_str), "%d%%", (int)data->battery_percent);
    draw_string(76, 2, bat_str, false, true);

    draw_battery_icon(96, 1, data->battery_percent);
    draw_rssi_bars(116, 1, data->rssi_dbm);

    // -------------------------------------------------------------------------
    // Line 1: Health Status Badge
    // -------------------------------------------------------------------------
    const char* status = data->status_text ? data->status_text : "NOMINAL";
    bool is_warning = (strcmp(status, "WARNING") == 0);

    if (is_warning) {
        fill_rect(0, 13, SSD1306_WIDTH, 10, true);
        draw_string(2, 14, "! HEALTH: WARNING", false, true);
    } else {
        char status_line[32];
        snprintf(status_line, sizeof(status_line), "HEALTH: %s", status);
        draw_string(2, 14, status_line, true, false);
    }

    // -------------------------------------------------------------------------
    // Line 2: Real Physical MPU6050 Readings
    // -------------------------------------------------------------------------
    char sensor_line[32];
    snprintf(sensor_line, sizeof(sensor_line), "Tilt:%5.2f*  Vib:%4.2f",
             data->tilt_deg, data->vibration_rms);
    draw_string(2, 26, sensor_line);

    // -------------------------------------------------------------------------
    // Line 3: TinyML Anomaly Score & MPU6050 Hardware Health
    // -------------------------------------------------------------------------
    char diag_line[32];
    snprintf(diag_line, sizeof(diag_line), "ML Score:%4.2f MPU:%s",
             data->anomaly_score, data->sensor_ok ? "OK" : "ERR");
    draw_string(2, 38, diag_line);

    // -------------------------------------------------------------------------
    // Line 4: Mesh Uplink Status (Hop count & Packets Sent)
    // -------------------------------------------------------------------------
    char mesh_line[32];
    snprintf(mesh_line, sizeof(mesh_line), "Mesh:Hop %d  Pkt:%-5u",
             (int)data->hop_count, (unsigned)data->packets_sent);
    draw_string(2, 50, mesh_line);

    // Bottom divider
    draw_hline(0, 63, SSD1306_WIDTH, true);

    render_buffer();
}

void subsense_display_emergency_alert(
    const char* node_id,
    float tilt_deg,
    float vib_rms,
    const char* message
) {
    if (!s_display_present) return;

    subsense_display_clear();

    // Flashing / Inverted Header
    fill_rect(0, 0, SSD1306_WIDTH, 13, true);
    draw_string(4, 3, "*** CRITICAL ALARM ***", false, true);

    // Evacuation Directive
    draw_string(2, 17, message ? message : "EVACUATE PANEL NOW!");

    // Measured Anomalous Values
    char val_buf[32];
    snprintf(val_buf, sizeof(val_buf), "TILT : %5.2f deg", tilt_deg);
    draw_string(2, 29, val_buf);

    snprintf(val_buf, sizeof(val_buf), "VIB  : %5.2f mm/s", vib_rms);
    draw_string(2, 39, val_buf);

    // Hardware Siren Action Status
    fill_rect(0, 51, SSD1306_WIDTH, 13, true);
    draw_string(4, 54, "SIREN ON (GPIO 2 HIGH)", false, true);

    render_buffer();
}

void subsense_display_power_save(bool enable_sleep) {
    if (!s_display_present) return;
    if (enable_sleep) {
        send_command(0xAE); // Display OFF (sleep mode, draws < 10 uA)
    } else {
        send_command(0xAF); // Display ON
    }
}
