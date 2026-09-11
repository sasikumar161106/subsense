"""
LoRa SX126x Driver (EBYTE E22-900T22S / SX1262 / SX1268)
=========================================================
Ported from loramain project with cross-platform support (Windows & Linux / Raspberry Pi).
Controls UART transmission and M0/M1 mode switching for LoRa SX126x modules.
"""

import logging
import time
from typing import Optional, Tuple, Union

try:
    import serial
except ImportError:
    serial = None

try:
    import RPi.GPIO as GPIO
    HAS_RPI_GPIO = True
except (ImportError, RuntimeError):
    GPIO = None
    HAS_RPI_GPIO = False

logger = logging.getLogger("sx126x")


class sx126x:
    M0 = 22
    M1 = 27

    # cfg_reg structure (12 bytes):
    # 0: Command (0xC0 = save to EEPROM on power down, 0xC2 = temporary/lost on power off)
    # 1: Start register address (0x00)
    # 2: Length (0x09 bytes)
    # 3: High address
    # 4: Low address
    # 5: Net ID
    # 6: REG0 - UART baud rate & Air data rate
    # 7: REG1 - Packet size & Sub-packet power & Noise RSSI
    # 8: REG2 - Frequency channel offset
    # 9: REG3 - Transmission mode & WOR & Packet RSSI enable
    # 10: REG4 - Key high byte
    # 11: REG5 - Key low byte
    cfg_reg = [0xC2, 0x00, 0x09, 0x00, 0x00, 0x00, 0x62, 0x00, 0x12, 0x43, 0x00, 0x00]
    get_reg = bytes(12)
    rssi = False
    addr = 65535
    serial_n = ""
    addr_temp = 0

    # Start frequency and offset
    # E22-400T22S: 410~493MHz  |  E22-900T22S: 850~930MHz
    start_freq = 850
    offset_freq = 15  # Default for 865 MHz (865 - 850 = 15)

    SX126X_UART_BAUDRATE_1200 = 0x00
    SX126X_UART_BAUDRATE_2400 = 0x20
    SX126X_UART_BAUDRATE_4800 = 0x40
    SX126X_UART_BAUDRATE_9600 = 0x60
    SX126X_UART_BAUDRATE_19200 = 0x80
    SX126X_UART_BAUDRATE_38400 = 0xA0
    SX126X_UART_BAUDRATE_57600 = 0xC0
    SX126X_UART_BAUDRATE_115200 = 0xE0

    SX126X_PACKAGE_SIZE_240_BYTE = 0x00
    SX126X_PACKAGE_SIZE_128_BYTE = 0x40
    SX126X_PACKAGE_SIZE_64_BYTE = 0x80
    SX126X_PACKAGE_SIZE_32_BYTE = 0xC0

    SX126X_Power_22dBm = 0x00
    SX126X_Power_17dBm = 0x01
    SX126X_Power_13dBm = 0x02
    SX126X_Power_10dBm = 0x03

    lora_air_speed_dic = {
        1200: 0x01,
        2400: 0x02,
        4800: 0x03,
        9600: 0x04,
        19200: 0x05,
        38400: 0x06,
        62500: 0x07,
    }

    lora_power_dic = {
        22: 0x00,
        17: 0x01,
        13: 0x02,
        10: 0x03,
    }

    lora_buffer_size_dic = {
        240: SX126X_PACKAGE_SIZE_240_BYTE,
        128: SX126X_PACKAGE_SIZE_128_BYTE,
        64: SX126X_PACKAGE_SIZE_64_BYTE,
        32: SX126X_PACKAGE_SIZE_32_BYTE,
    }

    def __init__(
        self,
        serial_num: str,
        freq: int = 865,
        addr: int = 0,
        power: int = 22,
        rssi: bool = True,
        air_speed: int = 2400,
        net_id: int = 0,
        buffer_size: int = 240,
        crypt: int = 0,
        relay: bool = False,
        lbt: bool = False,
        wor: bool = False,
        m0_pin: int = 22,
        m1_pin: int = 27,
    ):
        if serial is None:
            raise ImportError("pyserial package is required. Install via: pip install pyserial")

        self.rssi = rssi
        self.addr = addr
        self.freq = freq
        self.serial_n = serial_num
        self.power = power
        self.M0 = m0_pin
        self.M1 = m1_pin

        # Initialize GPIO if running on Raspberry Pi / Linux hardware
        if HAS_RPI_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                GPIO.setup(self.M0, GPIO.OUT)
                GPIO.setup(self.M1, GPIO.OUT)
                GPIO.output(self.M0, GPIO.LOW)
                GPIO.output(self.M1, GPIO.HIGH)
            except Exception as e:
                logger.warning(f"Could not initialize RPi.GPIO pins: {e}")

        # Connect to serial port at 9600 baud (module default communication rate)
        self.ser = serial.Serial(serial_num, 9600, timeout=1.0)
        self.ser.flushInput()
        self.set(freq, addr, power, rssi, air_speed, net_id, buffer_size, crypt, relay, lbt, wor)

    def _set_mode_config(self):
        """Put module into configuration mode: M0=LOW, M1=HIGH"""
        if HAS_RPI_GPIO:
            try:
                GPIO.output(self.M0, GPIO.LOW)
                GPIO.output(self.M1, GPIO.HIGH)
                time.sleep(0.1)
            except Exception:
                pass

    def _set_mode_normal(self):
        """Put module into normal transmission mode: M0=LOW, M1=LOW"""
        if HAS_RPI_GPIO:
            try:
                GPIO.output(self.M0, GPIO.LOW)
                GPIO.output(self.M1, GPIO.LOW)
                time.sleep(0.1)
            except Exception:
                pass

    def set(
        self,
        freq: int,
        addr: int,
        power: int,
        rssi: bool,
        air_speed: int = 2400,
        net_id: int = 0,
        buffer_size: int = 240,
        crypt: int = 0,
        relay: bool = False,
        lbt: bool = False,
        wor: bool = False,
    ):
        self.send_to = addr
        self.addr = addr
        self._set_mode_config()

        low_addr = addr & 0xFF
        high_addr = (addr >> 8) & 0xFF
        net_id_temp = net_id & 0xFF

        if freq >= 850:
            freq_temp = freq - 850
            self.start_freq = 850
            self.offset_freq = freq_temp
        elif freq >= 410:
            freq_temp = freq - 410
            self.start_freq = 410
            self.offset_freq = freq_temp
        else:
            freq_temp = 15  # Fallback to 865 MHz channel offset
            self.offset_freq = 15

        air_speed_temp = self.lora_air_speed_dic.get(air_speed, 0x02)
        buffer_size_temp = self.lora_buffer_size_dic.get(buffer_size, self.SX126X_PACKAGE_SIZE_240_BYTE)
        power_temp = self.lora_power_dic.get(power, self.SX126X_Power_22dBm)

        # Enable packet RSSI byte
        rssi_temp = 0x80 if rssi else 0x00

        l_crypt = crypt & 0xFF
        h_crypt = (crypt >> 8) & 0xFF

        if not relay:
            self.cfg_reg[3] = high_addr
            self.cfg_reg[4] = low_addr
            self.cfg_reg[5] = net_id_temp
            self.cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
            # 0x20 enables noise RSSI
            self.cfg_reg[7] = buffer_size_temp + power_temp + 0x20
            self.cfg_reg[8] = freq_temp
            # 0x40 fixed mode + 0x03 WOR + rssi_temp
            self.cfg_reg[9] = 0x43 + rssi_temp
            self.cfg_reg[10] = h_crypt
            self.cfg_reg[11] = l_crypt
        else:
            self.cfg_reg[3] = 0x01
            self.cfg_reg[4] = 0x02
            self.cfg_reg[5] = 0x03
            self.cfg_reg[6] = self.SX126X_UART_BAUDRATE_9600 + air_speed_temp
            self.cfg_reg[7] = buffer_size_temp + power_temp + 0x20
            self.cfg_reg[8] = freq_temp
            self.cfg_reg[9] = 0x03 + rssi_temp
            self.cfg_reg[10] = h_crypt
            self.cfg_reg[11] = l_crypt

        self.ser.flushInput()

        # Send configuration to module
        for i in range(2):
            self.ser.write(bytes(self.cfg_reg))
            time.sleep(0.2)
            if self.ser.in_waiting > 0:
                time.sleep(0.1)
                r_buff = self.ser.read(self.ser.in_waiting)
                if len(r_buff) > 0 and r_buff[0] == 0xC1:
                    logger.debug("LoRa SX126x configuration successful")
                    break
            else:
                self.ser.flushInput()
                time.sleep(0.2)

        # Switch back to normal mode
        self._set_mode_normal()
        time.sleep(0.1)

    def send(self, data: Union[str, bytes], target_addr: int = 0xFFFF, channel: Optional[int] = None):
        """
        Send data via LoRa in FIXED transmission mode.
        Format: [ADDR_H, ADDR_L, CHANNEL, PAYLOAD...]
        Default 0xFFFF broadcasts to all nodes on the channel.
        """
        self._set_mode_normal()

        if isinstance(data, str):
            data = data.encode("utf-8")

        ch = self.offset_freq if channel is None else channel
        h_addr = (target_addr >> 8) & 0xFF
        l_addr = target_addr & 0xFF

        packet = bytes([h_addr, l_addr, ch]) + data
        self.ser.write(packet)
        try:
            self.ser.flush()
        except Exception:
            pass
        time.sleep(0.02)

    def receive(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Receive data from LoRa module.
        Data format: [PAYLOAD...] + [RSSI_BYTE (optional)]
        Uses inter-character silence detection to ensure complete frame capture without fragmentation.
        Returns (payload_str, rssi_dbm)
        """
        if self.ser.in_waiting > 0:
            r_buff = bytearray()
            # Accumulate bytes until no new bytes arrive for at least 30ms (inter-frame silence)
            while True:
                waiting = self.ser.in_waiting
                if waiting > 0:
                    r_buff.extend(self.ser.read(waiting))
                time.sleep(0.025)
                if self.ser.in_waiting == 0:
                    break

            if len(r_buff) == 0:
                return None, None

            # If RSSI byte is enabled, the E22 module appends 1 byte at the end of the RF packet
            if self.rssi and len(r_buff) >= 2:
                raw_rssi = r_buff[-1]
                calc_rssi = -(256 - raw_rssi)
                rssi_val = calc_rssi if -130 <= calc_rssi <= 0 else None
                msg_data = bytes(r_buff[:-1])
            else:
                rssi_val = None
                msg_data = bytes(r_buff)

            try:
                msg = msg_data.decode("utf-8", errors="ignore")
            except Exception:
                msg = str(msg_data)

            return msg, rssi_val
        return None, None

    def close(self):
        """Close serial connection and cleanup GPIO if applicable."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

        if HAS_RPI_GPIO:
            try:
                GPIO.cleanup()
            except Exception:
                pass
