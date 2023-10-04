#! /bin/python3
"""Parser for AR8327 switch initvals configuration files."""

import re
import os
import sys
import getopt
import pathlib

# Constants for bitmasks and values
MAC06_EXCHANGE = 0x80000000
RGMII_EN = 0x4000000
RGMII_TX_DELAY = 0x2000000
RGMII_RX_DELAY = 0x1000000
TX_DELAY_MASK = 0xC00000
RX_DELAY_MASK = 0x300000
RX_FALLING_EDGE = 0x80000
TX_FALLING_EDGE = 0x40000
SGMII_EN = 0x80
POWER_ON_SEL = 0x80000000
LED_OPEN_DRAIN = 0x1000000
SERDES_AEN = 0x80
SGMII_MODE_MASK = 0xC00000
SGMII_EN_PLL = 0x2
SGMII_EN_RX = 0x4
SGMII_EN_TX = 0x8
SGMII_EN_SD = 0x10
PWR_RGMII_0 = 0x80000
PWR_RGMII_56 = 0x40000
PATTERN_EN_MASK = 0xC000
BLINK_FREQ_MASK = 0x3
LINKUP_OVER_EN = 0x4
TX_BLINK = 0x10
RX_BLINK = 0x20
COL_BLINK = 0x80
LINK_10M = 0x100
LINK_100M = 0x200
LINK_1000M = 0x400
POWER_ON_RESET = 0x800
HALF_DUPLEX = 0x1000
FULL_DUPLEX = 0x2000
BLINK_HIGH_TIME_MASK = 0x3
PATTERN_EN_EXTEND_MASK = 0x3

VERBOSE = False


def print_verbose(ts):
    if VERBOSE:
        print(ts)


def check_remaining_bit(reg, val):
    if val != 0x0:
        print(f"!!MISSING TO CONVERT REMAINING BIT {hex(val)} FOR REG {hex(reg)}")


def parse_tx_delay(val: int) -> int:
    # Extract TX delay from bits 22-23 (0xC00000)
    return (val & TX_DELAY_MASK) >> 22


def parse_rx_delay(val: int) -> int:
    # Extract RX delay from bits 20-21 (0x300000)
    return (val & RX_DELAY_MASK) >> 20


def parse_sgmii_mode_delay(val: int) -> str:
    # Extract SGMII mode from bits 22-23
    mode = (val & SGMII_MODE_MASK) >> 22
    if mode == 0x0:
        return "BASE-X"
    if mode == 0x1:
        return "PHY"
    if mode == 0x2:
        return "MAC"
    return "UNKNOWN"


def parse_PAD_config(reg: int, val: int) -> None:
    """
    Parse PAD configuration register values for ports 0, 5, 6.
    Decodes RGMII/SGMII settings, delays, and edge configurations.
    Prints human-readable configuration strings.
    """
    ts = []
    if reg == 0x4:
        if val == 0x0:
            print(
                "Absent config (regs set to 0x0) for pad5. "
                "Not attached port0????? WTH THIS CAN'T BE POSSIBLE!"
            )
            return
        ts.append("pad0")
    if reg == 0x8:
        if val == 0x0:
            print("Absent config (regs set to 0x0) for pad5. Not attached port5?")
            return
        ts.append("pad5")
    if reg == 0xC:
        if val == 0x0:
            print("Absent config (regs set to 0x0) for pad6. Not attached port6?")
            return
        ts.append("pad6")

    tx_delay = 0
    rx_delay = 0

    if val & MAC06_EXCHANGE:
        ts.append("mac06_exchange")
        val &= ~MAC06_EXCHANGE
    if val & RGMII_EN:
        ts.append("rgmii")
        val &= ~RGMII_EN
    if val & RGMII_TX_DELAY:
        ts.append("rgmii_tx_delay")
        val &= ~RGMII_TX_DELAY
    if val & RGMII_RX_DELAY:
        ts.append("rgmii_rx_delay")
        val &= ~RGMII_RX_DELAY
    if val & TX_DELAY_MASK:
        tx_delay = parse_tx_delay(val)
        if tx_delay != 1:
            ts.append(f"rgmii_tx_delay_sel {tx_delay}")
        val &= ~TX_DELAY_MASK
    if val & RX_DELAY_MASK:
        rx_delay = parse_rx_delay(val)
        if rx_delay != 2:
            ts.append(f"rgmii_rx_delay_sel {rx_delay}")
        val &= ~RX_DELAY_MASK
    if val & RX_FALLING_EDGE:
        ts.append("rx falling edge")
        val &= ~RX_FALLING_EDGE
    if val & TX_FALLING_EDGE:
        ts.append("tx falling edge")
        val &= ~TX_FALLING_EDGE
    if val & SGMII_EN:
        ts.append("sgmii")
        val &= ~SGMII_EN

    print_verbose(ts)

    strings = []

    if "pad0" in ts:
        strings.append("Conf for cpu port0")

    if "pad5" in ts:
        strings.append("Conf for cpu port5")

    if "pad6" in ts:
        strings.append("Conf for cpu port6")

    if "rgmii_tx_delay" in ts and "rgmii_rx_delay" in ts:
        strings.append("Mode rgmii-id")
    else:
        if "rgmii_tx_delay" not in ts and "rgmii_rx_delay" not in ts and "rgmii" in ts:
            strings.append("Mode rgmii")
        if "rgmii_tx_delay" in ts:
            strings.append("Mode rgmii-txid")
        if "rgmii_rx_delay" in ts:
            strings.append("Mode rgmii-rxid")

    if f"rgmii_tx_delay_sel {tx_delay}" in ts:
        strings.append(f"With tx-internal-delay-ps of {tx_delay * 1000}")

    if f"rgmii_rx_delay_sel {rx_delay}" in ts:
        strings.append(f"With rx-internal-delay-ps of {rx_delay * 1000}")

    if "sgmii" in ts:
        strings.append("Mode sgmii")

    if "rx falling edge" in ts:
        strings.append("With qca,sgmii-rxclk-falling-edge")

    if "tx falling edge" in ts:
        strings.append("With qca,sgmii-txclk-falling-edge")

    if "mac06_exchange" in ts:
        strings.append("With qca,mac6-exchange")

    print(", ".join(strings))

    check_remaining_bit(reg, val)


def parse_PWS_REG_config(reg, val):
    ts = []

    ts.append("PWS_REG")

    if val & POWER_ON_SEL:
        ts.append("power_on_sel")
        val &= ~POWER_ON_SEL
    if val & 0x40000000:
        val &= ~0x40000000
    if val & LED_OPEN_DRAIN:
        ts.append("led_open_drain")
        val &= ~LED_OPEN_DRAIN
    if val & SERDES_AEN:
        ts.append("serdes_aen")
        val &= ~SERDES_AEN

    val &= ~0x261320

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if "power_on_sel" in ts:
        strings.append("Set qca,power-on-sel in switch node")

    if "led_open_drain" in ts:
        strings.append("Set qca,led-open-drain in switch node")

    print(", ".join(strings))


def parse_SGMII_CTRL_config(reg, val):
    ts = []
    ts.append("SGMII_CTRL")

    sgmii_mode = ""

    if val & SGMII_MODE_MASK:
        sgmii_mode = parse_sgmii_mode_delay(val)
        ts.append(f"mode_ctrl_25m {sgmii_mode}")
        val &= ~SGMII_MODE_MASK
    if val & SGMII_EN_PLL:
        ts.append("sgmii_en_pll")
        val &= ~SGMII_EN_PLL
    if val & SGMII_EN_RX:
        ts.append("sgmii_en_rx")
        val &= ~SGMII_EN_RX
    if val & SGMII_EN_TX:
        ts.append("sgmii_en_tx")
        val &= ~SGMII_EN_TX
    if val & SGMII_EN_SD:
        ts.append("sgmii_en_sd")
        val &= ~SGMII_EN_SD

    val &= ~0xC70164C0

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if f"mode_ctrl_25m {sgmii_mode}" in ts:
        strings.append(
            f"Sgmii mode set to {sgmii_mode}. If set to PHY you can ignore "
            f"this settings as qca8k should automatically set this"
        )

    if "sgmii_en_tx" in ts or "sgmii_en_rx" in ts or "sgmii_en_pll" in ts:
        strings.append("Set qca,sgmii-enable-pll in cpu port node that use sgmii mode")

    print(", ".join(strings))


def parse_MAC_POWER_SEL_config(reg, val):
    ts = []
    ts.append("MAC_POWER_SEL")

    if val & PWR_RGMII_0:
        ts.append("pwr_rgmii 0")
        val &= ~PWR_RGMII_0
    if val & PWR_RGMII_56:
        ts.append("pwr_rgmii 56")
        val &= ~PWR_RGMII_56

    val &= ~0x2A545

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if "pwr_rgmii 0" in ts:
        strings.append("Set qca,rgmii0-1-8v  in switch node")

    if "pwr_rgmii 56" in ts:
        strings.append("Set qca,rgmii56-1-8v in switch node")

    print(", ".join(strings))


def parse_pattern_en(val):
    mode = (val & 0xC000) >> 14
    if mode == 0x0:
        return "off"
    if mode == 0x1:
        return "blink"
    if mode == 0x2:
        return "on"
    if mode == 0x3:
        return "rule"


def parse_blink_freq(val):
    mode = val & 0x3
    if mode == 0x0:
        return "2hz"
    if mode == 0x1:
        return "4hz"
    if mode == 0x2:
        return "8hz"
    if mode == 0x3:
        return "auto"


def parse_LEDS_NORMAL_config(reg, val):
    phys = ["phy0123", "phy4"]
    led_num = ""
    for phy in phys:
        ts = []
        pattern_en = "off"
        blink_mode = ""
        if reg == 0x50:
            if (val & 0xFFFF) == 0xCC35:
                continue
            ts.append("LED_CTRL0")
            led_num = 0
        if reg == 0x54:
            if (val & 0xFFFF) == 0xCA35:
                continue
            ts.append("LED_CTRL1")
            led_num = 1
        if reg == 0x58:
            if (val & 0xFFFF) == 0xC935:
                continue
            ts.append("LED_CTRL2")
            led_num = 2

        if val & 0x3:
            blink_mode = parse_blink_freq(val)
            ts.append(f"{phy} blink freq {blink_mode}")
            val &= ~0x3
        if val & 0x4:
            ts.append(f"{phy} linkup_over_en ")
            val &= ~0x4
        if val & 0x10:
            ts.append(f"{phy} tx_blink")
            val &= ~0x10
        if val & 0x20:
            ts.append(f"{phy} rx_blink")
            val &= ~0x20
        if val & 0x80:
            ts.append(f"{phy} col_blink")
            val &= ~0x80
        if val & 0x100:
            ts.append(f"{phy} link_10m")
            val &= ~0x100
        if val & 0x200:
            ts.append(f"{phy} link_100m")
            val &= ~0x200
        if val & 0x400:
            ts.append(f"{phy} link_1000m")
            val &= ~0x400
        if val & 0x800:
            ts.append(f"{phy} power_on_reset")
            val &= ~0x800
        if val & 0x1000:
            ts.append(f"{phy} half_duplex")
            val &= ~0x1000
        if val & 0x2000:
            ts.append(f"{phy} full_duplex")
            val &= ~0x2000
        if val & 0xC000:
            if phy == "phy0123":
                real_phy = "phy0"
            else:
                real_phy = phy
            pattern_en = parse_pattern_en(val)
            ts.append(f"{real_phy} pattern_en {pattern_en}")
            val &= ~0xC000

        if reg == 0x50:
            val &= ~0xCC35
        if reg == 0x54:
            val &= ~0xCA35
        if reg == 0x58:
            val &= ~0xC935

        print_verbose(ts)
        check_remaining_bit(reg, val & 0xFFFF)

        val = val >> 16

        strings = []

        strings.append(
            f"Custom rule for {phy} led {led_num} applied using qca,led_rules"
        )

        if f"{phy} blink freq {blink_mode}" in ts:
            strings.append(f"blink-{blink_mode}")

        if f"{phy} linkup_over_en" in ts:
            strings.append("linkup-over")

        if f"{phy} tx_blink" in ts:
            strings.append("tx-blink")

        if f"{phy} rx_blink" in ts:
            strings.append("rx-blink")

        if f"{phy} col_blink" in ts:
            strings.append("collision-blink")

        if f"{phy} link_10m" in ts:
            strings.append("link-10M")

        if f"{phy} link_100m" in ts:
            strings.append("link-100M")

        if f"{phy} link_1000m" in ts:
            strings.append("link-1000M")

        if f"{phy} power_on_reset" in ts:
            strings.append("power-on-reset")

        if f"{phy} half_duplex" in ts:
            strings.append("half-duplex")

        if f"{phy} full_duplex" in ts:
            strings.append("full-duplex")

        print(", ".join(strings))

        strings = []

        if f"phy0 pattern_en {pattern_en}" in ts or (
            pattern_en == "off" and phy == "phy0123"
        ):
            strings.append(
                f"port0 led {led_num} is set to mode {pattern_en}"
            )

        if f"phy4 pattern_en {pattern_en}" in ts or (
            pattern_en == "off" and phy == "phy4"
        ):
            strings.append(
                f"port4 led {led_num} is set to mode {pattern_en}"
            )

        print(", ".join(strings))


def parse_blink_high_time(val):
    mode = val & 0x3
    if mode == 0x0:
        return "50%"
    if mode == 0x1:
        return "12.5%"
    if mode == 0x2:
        return "25%"
    if mode == 0x3:
        return "75%"


def parse_pattern_en_extend(val):
    mode = val & 0x3
    if mode == 0x0:
        return "off"
    if mode == 0x1:
        return "blink"
    if mode == 0x2:
        return "on"
    if mode == 0x3:
        return "rule"


def parse_LEDS_EXTENDED_config(reg, val):
    ts = []
    ts.append("LED_CTRL3")

    blink_time = ""

    if val & 0x3:
        blink_time = parse_blink_high_time(val)
        ts.append(f"blink high time {blink_time}")
        val &= ~0x3

    val = val >> 8

    for phy in range(3):
        for i in range(3):
            mode = parse_pattern_en_extend(val)
            ts.append(f"phy{phy + 1}_{i} pattern_en {mode}")
            val &= ~0x3
            val = val >> 2

            print(f"port{phy + 1} led {i} is set to mode {mode}")

    val &= ~0x3FFFF00

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if f"blink high time {blink_time}" in ts:
        strings.append(f"Blink high time (NOT SUPPORTED?) set to {blink_time}")

    ", ".join(strings)


def parse_unknown(reg, val):
    print(f"Unknown val: {hex(val)} for reg: {hex(reg)}")


known_reg = [0x4, 0x8, 0xC, 0x10, 0xE4, 0xE0, 0x50, 0x54, 0x58, 0x5C]
ignore_reg = [
    0x0007C,
    0x00094,
    0x00970,
    0x00974,
    0x00978,
    0x0097C,
    0x00980,
    0x00984,
    0x00988,
    0x0098C,
    0x00990,
    0x00994,
    0x00998,
    0x0099C,
    0x009A0,
    0x009A4,
]


def function_tbl(reg, val):
    if reg in ignore_reg:
        return
    if reg not in known_reg:
        return parse_unknown(reg, val)

    if reg in [0x4, 0x8, 0xC]:
        return parse_PAD_config(reg, val)

    if reg == 0x10:
        return parse_PWS_REG_config(reg, val)

    if reg == 0xE0:
        return parse_SGMII_CTRL_config(reg, val)

    if reg == 0xE4:
        return parse_MAC_POWER_SEL_config(reg, val)

    if reg in [0x50, 0x54, 0x58]:
        return parse_LEDS_NORMAL_config(reg, val)

    if reg == 0x5C:
        return parse_LEDS_EXTENDED_config(reg, val)


def give_info_regs(data):
    for phy in data:
        # print("regs for " + phy)
        for reg, val in data[phy].items():
            function_tbl(reg, val)


def parse_qca8k(filename: str, path: str) -> None:
    """
    Parse a DTS/DTSI file for qca,ar8327-initvals configurations.
    Extracts register-value pairs and decodes them using appropriate parsers.
    Prints decoded configurations for the AR8327 switch.

    Args:
        filename: Name of the DTS/DTSI file to parse.
        path: Directory path containing the file.
    """
    file = os.path.join(path, filename)
    found = 0
    have_qca8k = 0
    data = {}

    #     print("Analyzing " + os.path.join(path, filename))
    try:
        with open(file, encoding="utf-8") as fp:
            curr_phy = "phy0"
            for line in fp:
                if (
                    "ethernet-phy@0" in line
                    or "ethernet-switch@0" in line
                    or "switch0@1f" in line
                    or "qca,ar8327" in line
                ):
                    curr_phy = "phy0"
                if "ethernet-phy@4" in line or "ethernet-switch@4" in line:
                    curr_phy = "phy4"
                if "qca,ar8327-initvals" in line:
                    print("######################START##############################")
                    print(f"Found qca8k switch in {os.path.join(path, filename)}")
                    found = 1
                    have_qca8k = 1
                    data[curr_phy] = {}
                    continue
                if ">;" in line:
                    give_info_regs(data)
                    found = 0
                    data = {}
                if found == 0:
                    continue

                regex = re.search(r".*(0x\S+) (0x\S+)", line)
                if not regex:
                    continue
                reg = regex.group(1)
                val = regex.group(2)

                reg = int(reg, 16)
                val = int(val, 16)

                data[curr_phy][reg] = val
    except FileNotFoundError:
        print(f"Error: File {file} not found.")
    except ValueError as e:
        print(f"Error parsing file {file}: {e}")
    except OSError as e:
        print(f"Error reading file {file}: {e}")

    if have_qca8k:
        print("#######################END###############################\n")


def main(argv: list[str]) -> None:
    try:
        opts, args = getopt.getopt(argv[1:], "d", ["debug"])
    except getopt.GetoptError:
        print("ar8327-initvals.py [--debug] <directory>")
        sys.exit(2)

    global VERBOSE

    for opt, _ in opts:
        if opt in ("-d", "--debug"):
            VERBOSE = True

    for file in pathlib.Path(args[0]).iterdir():
        if file.suffix in [".dts", ".dtsi"]:
            parse_qca8k(str(file.name), str(file.parent))


if __name__ == "__main__":
    main(sys.argv[1:])
