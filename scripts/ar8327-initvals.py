#! /bin/python3

import linecache
import re
from shutil import copyfile
import os
import sys, getopt
import pathlib

verbose = False


def print_verbose(ts):
    if verbose:
        print(ts)


def check_remaining_bit(reg, val):
    if val != 0x0:
        print("!!MISSING TO CONVERT REMAINING BIT " + hex(val) + " FOR REG " + hex(reg))


def parse_tx_delay(val):
    return (val & 0xC00000) >> 22


def parse_rx_delay(val):
    return (val & 0x300000) >> 20


def parse_sgmii_mode_delay(val):
    mode = (val & 0xC00000) >> 22
    if mode == 0x0:
        return "BASE-X"
    if mode == 0x1:
        return "PHY"
    if mode == 0x2:
        return "MAC"


def parse_PAD_config(reg, val):
    ts = []
    if reg == 0x4:
        if val == 0x0:
            print(
                "Absent config (regs set to 0x0) for pad5. Not attached port0????? WTH THIS CAN'T BE POSSIBLE!"
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

    if val & 0x80000000:
        ts.append("mac06_exchange")
        val &= val & ~0x80000000
    if val & 0x4000000:
        ts.append("rgmii")
        val &= val & ~0x4000000
    if val & 0x2000000:
        ts.append("rgmii_tx_delay")
        val &= val & ~0x2000000
    if val & 0x1000000:
        ts.append("rgmii_rx_delay")
        val &= val & ~0x1000000
    if val & 0xC00000:
        tx_delay = parse_tx_delay(val)
        if tx_delay != 1:
            ts.append("rgmii_tx_delay_sel " + str(tx_delay))
        val &= val & ~0xC00000
    if val & 0x300000:
        rx_delay = parse_rx_delay(val)
        if rx_delay != 2:
            ts.append("rgmii_rx_delay_sel " + str(rx_delay))
        val &= val & ~0x300000
    if val & 0x80000:
        ts.append("rx falling edge")
        val &= val & ~0x80000
    if val & 0x40000:
        ts.append("tx falling edge")
        val &= val & ~0x40000
    if val & 0x80:
        ts.append("sgmii")
        val &= val & ~0x80

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
        if not "rgmii_tx_delay" in ts and not "rgmii_rx_delay" in ts and "rgmii" in ts:
            strings.append("Mode rgmii")
        if "rgmii_tx_delay" in ts:
            strings.append("Mode rgmii-txid")
        if "rgmii_rx_delay" in ts:
            strings.append("Mode rgmii-rxid")

    if "rgmii_tx_delay_sel " + str(tx_delay) in ts:
        strings.append("With tx-internal-delay-ps of " + str(tx_delay * 1000))

    if "rgmii_rx_delay_sel " + str(rx_delay) in ts:
        strings.append("With rx-internal-delay-ps of " + str(rx_delay * 1000))

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

    if val & 0x80000000:
        ts.append("power_on_sel")
        val &= val & ~0x80000000
    if val & 0x40000000:
        ts.append("package48_en")
        val &= val & ~0x40000000
    if val & 0x1000000:
        ts.append("led_open_drain")
        val &= val & ~0x1000000
    if val & 0x80:
        ts.append("serdes_aen")
        val &= val & ~0x80

    val &= val & ~0x261320

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if "power_on_sel" in ts:
        strings.append("Set qca,power-on-sel in switch node")

    if "package48_en" in ts:
        strings.append("Assume qca8327. Set qca,package48 in switch noe")

    if "led_open_drain" in ts:
        strings.append("Set qca,led-open-drain in switch node")

    print(", ".join(strings))


def parse_SGMII_CTRL_config(reg, val):
    ts = []
    ts.append("SGMII_CTRL")

    sgmii_mode = ""

    if val & 0xC00000:
        sgmii_mode = parse_sgmii_mode_delay(val)
        ts.append("mode_ctrl_25m " + sgmii_mode)
        val &= val & ~0xC00000
    if val & 0x2:
        ts.append("sgmii_en_pll")
        val &= val & ~0x2
    if val & 0x4:
        ts.append("sgmii_en_rx")
        val &= val & ~0x4
    if val & 0x8:
        ts.append("sgmii_en_tx")
        val &= val & ~0x8
    if val & 0x10:
        ts.append("sgmii_en_sd")
        val &= val & ~0x10

    val &= val & ~0xC70164C0

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if "mode_ctrl_25m " + sgmii_mode in ts:
        strings.append(
            "Sgmii mode set to "
            + sgmii_mode
            + " If set to PHY you can ignore this settings as qca8k should automatically set this"
        )

    if "sgmii_en_tx" in ts or "sgmii_en_rx" in ts or "sgmii_en_pll" in ts:
        strings.append("Set qca,sgmii-enable-pll in cpu port node that use sgmii mode")

    print(", ".join(strings))


def parse_MAC_POWER_SEL_config(reg, val):
    ts = []
    ts.append("MAC_POWER_SEL")

    if val & 0x80000:
        ts.append("pwr_rgmii 0")
        val &= val & ~0x80000
    if val & 0x40000:
        ts.append("pwr_rgmii 56")
        val &= val & ~0x40000

    val &= val & ~0x2A545

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
            ts.append(phy + " blink freq " + blink_mode)
            val &= val & ~0x3
        if val & 0x4:
            ts.append(phy + " linkup_over_en ")
            val &= val & ~0x4
        if val & 0x10:
            ts.append(phy + " tx_blink")
            val &= val & ~0x10
        if val & 0x20:
            ts.append(phy + " rx_blink")
            val &= val & ~0x20
        if val & 0x80:
            ts.append(phy + " col_blink")
            val &= val & ~0x80
        if val & 0x100:
            ts.append(phy + " link_10m")
            val &= val & ~0x100
        if val & 0x200:
            ts.append(phy + " link_100m")
            val &= val & ~0x200
        if val & 0x400:
            ts.append(phy + " link_1000m")
            val &= val & ~0x400
        if val & 0x800:
            ts.append(phy + " power_on_reset")
            val &= val & ~0x800
        if val & 0x1000:
            ts.append(phy + " half_duplex")
            val &= val & ~0x1000
        if val & 0x2000:
            ts.append(phy + " full_duplex")
            val &= val & ~0x2000
        if val & 0xC000:
            if phy == "phy0123":
                real_phy = "phy0"
            else:
                real_phy = phy
            pattern_en = parse_pattern_en(val)
            ts.append(real_phy + " pattern_en " + pattern_en)
            val &= val & ~0xC000

        if reg == 0x50:
            val &= val & ~0xCC35
        if reg == 0x54:
            val &= val & ~0xCA35
        if reg == 0x58:
            val &= val & ~0xC935

        print_verbose(ts)
        check_remaining_bit(reg, val & 0xFFFF)

        val = val >> 16

        strings = []

        strings.append(
            "Custom rule for {0} led {1} applied using qca,led_rules".format(
                phy, led_num
            )
        )

        if phy + " blink freq " + blink_mode in ts:
            strings.append("blink-" + blink_mode)

        if phy + " linkup_over_en" in ts:
            strings.append("linkup-over")

        if phy + " tx_blink" in ts:
            strings.append("tx-blink")

        if phy + " rx_blink" in ts:
            strings.append("rx-blink")

        if phy + " col_blink" in ts:
            strings.append("collision-blink")

        if phy + " link_10m" in ts:
            strings.append("link-10M")

        if phy + " link_100m" in ts:
            strings.append("link-100M")

        if phy + " link_1000m" in ts:
            strings.append("link-1000M")

        if phy + " power_on_reset" in ts:
            strings.append("power-on-reset")

        if phy + " half_duplex" in ts:
            strings.append("half-duplex")

        if phy + " full_duplex" in ts:
            strings.append("full-duplex")

        print(", ".join(strings))

        strings = []

        if "phy0 pattern_en " + pattern_en in ts or (
            pattern_en == "off" and phy == "phy0123"
        ):
            strings.append(
                "port0 led {0} is set to mode {1}".format(led_num, pattern_en)
            )

        if "phy4 pattern_en " + pattern_en in ts or (
            pattern_en == "off" and phy == "phy4"
        ):
            strings.append(
                "port4 led {0} is set to mode {1}".format(led_num, pattern_en)
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
        ts.append("blink high time " + blink_time)
        val &= val & ~0x3

    val = val >> 8

    for phy in range(3):
        for i in range(3):
            mode = parse_pattern_en_extend(val)
            ts.append("phy" + str(phy + 1) + "_" + str(i) + " pattern_en " + mode)
            val &= val & ~0x3
            val = val >> 2

            print("port{0} led {1} is set to mode {2}".format(phy + 1, i, mode))

    val &= val & ~0x3FFFF00

    print_verbose(ts)
    check_remaining_bit(reg, val)

    strings = []

    if "blink high time " + blink_time in ts:
        strings.append("Blink high time (NOT SUPPORTED?) set to " + blink_time)

    ", ".join(strings)


def parse_unknown(reg, val):
    print("Unknown val: {0} for reg: {1}".format(hex(val), hex(reg)))


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
    if not reg in known_reg:
        return parse_unknown(reg, val)

    if reg == 0x4 or reg == 0x8 or reg == 0xC:
        return parse_PAD_config(reg, val)

    if reg == 0x10:
        return parse_PWS_REG_config(reg, val)

    if reg == 0xE0:
        return parse_SGMII_CTRL_config(reg, val)

    if reg == 0xE4:
        return parse_MAC_POWER_SEL_config(reg, val)

    if reg == 0x50 or reg == 0x54 or reg == 0x58:
        return parse_LEDS_NORMAL_config(reg, val)

    if reg == 0x5C:
        return parse_LEDS_EXTENDED_config(reg, val)


def give_info_regs(data):
    for phy in data:
        # print("regs for " + phy)
        for reg, val in data[phy].items():
            function_tbl(reg, val)


def parse_qca8k(filename, path):
    file = os.path.join(path, filename)
    found = 0
    have_qca8k = 0
    data = {}

    #     print("Analyzing " + os.path.join(path, filename))
    with open(file) as fp:
        for line in fp.readlines():
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
                print("Found qca8k switch in " + os.path.join(path, filename))
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

    if have_qca8k:
        print("#######################END###############################\n")


def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "i:d", ["ifile=", "debug"])
    except getopt.GetoptError:
        print("test.py -i <inputfile>")
        sys.exit(2)

    global verbose

    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            verbose = True

    for file in pathlib.Path(args[0]).iterdir():
        if file.suffix == ".dts" or file.suffix == ".dtsi":
            parse_qca8k(str(file.name), str(file.parent))


if __name__ == "__main__":
    main(sys.argv[1:])
