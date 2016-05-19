#!/usr/bin/env python

# stcflash  Copyright (C) 2013  laborer (laborer@126.com)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import time
import logging
import sys
import serial
import os.path
import binascii
import struct
import argparse


PROTOCOL_89 = "89"
PROTOCOL_12C5A = "12c5a"
PROTOCOL_12C52 = "12c52"
PROTOCOL_12Cx052 = "12cx052"

PROTOSET_89 = [PROTOCOL_89]
PROTOSET_12 = [PROTOCOL_12C5A, PROTOCOL_12C52, PROTOCOL_12Cx052]
PROTOSET_12B = [PROTOCOL_12C52, PROTOCOL_12Cx052]
PROTOSET_PARITY = [PROTOCOL_12C5A, PROTOCOL_12C52]


class Programmer:
    def __init__(self, conn, protocol=None):
        self.conn = conn
        self.protocol = protocol

        self.conn.timeout = 0.05
        if self.protocol in PROTOSET_PARITY:
            self.conn.parity = serial.PARITY_EVEN
        else:
            self.conn.parity = serial.PARITY_NONE

        self.chkmode = 0

    def __conn_read(self, size):
        buf = bytearray()
        while len(buf) < size:
            s = bytearray(self.conn.read(size - len(buf)))
            buf += s

            logging.debug("recv: " + " ".join(["%02X" % i for i in s]))

            if len(s) == 0:
                raise IOError()

        return list(buf)

    def __conn_write(self, s):
        logging.debug("send: " + " ".join(["%02X" % i for i in s]))

        self.conn.write(bytearray(s))

    def __conn_baudrate(self, baud, flush=True):
        logging.debug("baud: %d" % baud)

        if flush:
            self.conn.flush()
            time.sleep(0.2)

        self.conn.baudrate = baud

    def __model_database(self, model):
        modelmap = {0xE0: ("12", 1, {(0x00, 0x1F): ("C54", ""),
                                     (0x60, 0x7F): ("C54", "AD"),
                                     (0x80, 0x9F): ("LE54", ""),
                                     (0xE0, 0xFF): ("LE54", "AD"),
                                     }),
                    0xE1: ("12", 1, {(0x00, 0x1F): ("C52", ""),
                                     (0x20, 0x3F): ("C52", "PWM"),
                                     (0x60, 0x7F): ("C52", "AD"),
                                     (0x80, 0x9F): ("LE52", ""),
                                     (0xA0, 0xBF): ("LE52", "PWM"),
                                     (0xE0, 0xFF): ("LE52", "AD"),
                                     }),
                    0xE2: ("11", 1, {(0x00, 0x1F): ("F", ""),
                                     (0x20, 0x3F): ("F", "E"),
                                     (0x70, 0x7F): ("F", ""),
                                     (0x80, 0x9F): ("L", ""),
                                     (0xA0, 0xBF): ("L", "E"),
                                     (0xF0, 0xFF): ("L", ""),
                                     }),
                    0xE6: ("12", 1, {(0x00, 0x1F): ("C56", ""),
                                     (0x60, 0x7F): ("C56", "AD"),
                                     (0x80, 0x9F): ("LE56", ""),
                                     (0xE0, 0xFF): ("LE56", "AD"),
                                     }),
                    0xD1: ("12", 2, {(0x20, 0x3F): ("C5A", "CCP"),
                                     (0x40, 0x5F): ("C5A", "AD"),
                                     (0x60, 0x7F): ("C5A", "S2"),
                                     (0xA0, 0xBF): ("LE5A", "CCP"),
                                     (0xC0, 0xDF): ("LE5A", "AD"),
                                     (0xE0, 0xFF): ("LE5A", "S2"),
                                     }),
                    0xD2: ("10", 1, {(0x00, 0x0F): ("F", ""),
                                     (0x60, 0x6F): ("F", "XE"),
                                     (0x70, 0x7F): ("F", "X"),
                                     (0xA0, 0xAF): ("L", ""),
                                     (0xE0, 0xEF): ("L", "XE"),
                                     (0xF0, 0xFF): ("L", "X"),
                                     }),
                    0xD3: ("11", 2, {(0x00, 0x1F): ("F", ""),
                                     (0x40, 0x5F): ("F", "X"),
                                     (0x60, 0x7F): ("F", "XE"),
                                     (0xA0, 0xBF): ("L", ""),
                                     (0xC0, 0xDF): ("L", "X"),
                                     (0xE0, 0xFF): ("L", "XE"),
                                     }),
                    0xF0: ("89", 4, {(0x00, 0x10): ("C5", "RC"),
                                     (0x20, 0x30): ("C5", "RC"),  #STC90C5xRC
                                     }),
                    0xF1: ("89", 4, {(0x00, 0x10): ("C5", "RD+"),
                                     (0x20, 0x30): ("C5", "RD+"),  #STC90C5xRD+
                                     }),
                    0xF2: ("12", 1, {(0x00, 0x0F): ("C", "052"),
                                     (0x10, 0x1F): ("C", "052AD"),
                                     (0x20, 0x2F): ("LE", "052"),
                                     (0x30, 0x3F): ("LE", "052AD"),
                                     }),
                    }

        iapmcu = ((0xD1, 0x3F), (0xD1, 0x5F), (0xD1, 0x7F),
                  (0xD2, 0x7E), (0xD2, 0xFE),
                  (0xD3, 0x5F), (0xD3, 0xDF),
                  (0xE2, 0x76), (0xE2, 0xF6),
                  )

        try:
            model = tuple(model)

            prefix, romratio, fixmap = modelmap[model[0]]

            if model[0] in (0xF0, 0xF1) and 0x20 <= model[1] <= 0x30:
                prefix = "90"

            for key, value in fixmap.items():
                if key[0] <= model[1] <= key[1]:
                    break
            else:
                raise KeyError()

            infix, postfix = value

            romsize = romratio * (model[1] - key[0])

            try:
                romsize = {(0xF0, 0x03): 13}[model]
            except KeyError:
                pass

            if model[0] in (0xF0, 0xF1):
                romfix = str(model[1] - key[0])
            elif model[0] in (0xF2,):
                romfix = str(romsize)
            else:
                romfix = "%02d" % romsize

            name = "IAP" if model in iapmcu else "STC"
            name += prefix + infix + romfix + postfix
            return (name, romsize)

        except KeyError:
            return ("Unknown %02X %02X" % model, None)

    def recv(self, timeout = 1, start = [0x46, 0xB9, 0x68]):
        timeout += time.time()

        while time.time() < timeout:
            try:
                if self.__conn_read(len(start)) == start:
                    break
            except IOError:
                continue
        else:
            logging.debug("recv(..): Timeout")
            raise IOError()

        chksum = start[-1]

        s = self.__conn_read(2)
        n = s[0] * 256 + s[1]
        if n > 64:
            logging.debug("recv(..): Incorrect packet size")
            raise IOError()
        chksum += sum(s)

        s = self.__conn_read(n - 3)
        if s[n - 4] != 0x16:
            logging.debug("recv(..): Missing terminal symbol")
            raise IOError()

        chksum += sum(s[:-(1+self.chkmode)])
        if self.chkmode > 0 and chksum & 0xFF != s[-2]:
            logging.debug("recv(..): Incorrect checksum[0]")
            raise IOError()
        elif self.chkmode > 1 and (chksum >> 8) & 0xFF != s[-3]:
            logging.debug("recv(..): Incorrect checksum[1]")
            raise IOError()

        return (s[0], s[1:-(1+self.chkmode)])

    def send(self, cmd, dat):
        buf = [0x46, 0xB9, 0x6A]

        n = 1 + 2 + 1 + len(dat) + self.chkmode + 1
        buf += [n >> 8, n & 0xFF, cmd]

        buf += dat

        chksum = sum(buf[2:])
        if self.chkmode > 1:
            buf += [(chksum >> 8) & 0xFF]
        buf += [chksum & 0xFF, 0x16]

        self.__conn_write(buf)

    def detect(self):
        for i in range(1000):
            try:
                self.__conn_write([0x7F, 0x7F])
                cmd, dat = self.recv(0.015, [0x68])
                break
            except IOError:
                pass
        else:
            raise IOError()

        self.fosc = (float(sum(dat[0:16:2]) * 256 + sum(dat[1:16:2])) / 8
                     * self.conn.baudrate / 580974)
        self.info = dat[16:]
        self.version = "%d.%d%c" % (self.info[0] >> 4,
                                    self.info[0] & 0x0F,
                                    self.info[1])
        self.model = self.info[3:5]

        self.name, self.romsize = self.__model_database(self.model)

        logging.info("Model ID: %02X %02X" % tuple(self.model))
        logging.info("Model name: %s" % self.name)
        logging.info("ROM size: %s" % self.romsize)

        if self.protocol is None:
            try:
                self.protocol = {0xF0: PROTOCOL_89,       #STC89/90C5xRC
                                 0xF1: PROTOCOL_89,       #STC89/90C5xRD+
                                 0xF2: PROTOCOL_12Cx052,  #STC12Cx052
                                 0xD1: PROTOCOL_12C5A,    #STC12C5Ax
                                 0xD2: PROTOCOL_12C5A,    #STC10Fx
                                 0xE1: PROTOCOL_12C52,    #STC12C52x
                                 0xE2: PROTOCOL_12C5A,    #STC11Fx
                                 0xE6: PROTOCOL_12C52,    #STC12C56x
                                 }[self.model[0]]
            except KeyError:
                pass

        if self.protocol in PROTOSET_PARITY:
            self.chkmode = 2
            self.conn.parity = serial.PARITY_EVEN
        else:
            self.chkmode = 1
            self.conn.parity = serial.PARITY_NONE

        if self.protocol is not None:
            del self.info[-self.chkmode:]

            logging.info("Protocol ID: %s" % self.protocol)
            logging.info("Checksum mode: %d" % self.chkmode)
            logging.info("UART Parity: %s"
                         % {serial.PARITY_NONE: "NONE",
                            serial.PARITY_EVEN: "EVEN",
                            }[self.conn.parity])

        for i in range(0, len(self.info), 16):
            logging.info("Info string [%d]: %s"
                         % (i // 16,
                            " ".join(["%02X" % j for j in self.info[i:i+16]])))

    def print_info(self):
        print(" FOSC: %.3fMHz" % self.fosc)
        print(" Model: %s (ver%s) " % (self.name, self.version))
        if self.romsize is not None:
            print(" ROM: %dKB" % self.romsize)

        if self.protocol == PROTOCOL_89:
            switches = [( 2, 0x80, "Reset stops watchdog"),
                        ( 2, 0x40, "Internal XRAM"),
                        ( 2, 0x20, "Normal ALE pin"),
                        ( 2, 0x10, "Full gain oscillator"),
                        ( 2, 0x08, "Not erase data EEPROM"),
                        ( 2, 0x04, "Download regardless of P1"),
                        ( 2, 0x01, "12T mode")]

        elif self.protocol == PROTOCOL_12C5A:
            switches = [( 6, 0x40, "Disable reset2 low level detect"),
                        ( 6, 0x01, "Reset pin not use as I/O port"),
                        ( 7, 0x80, "Disable long power-on-reset latency"),
                        ( 7, 0x40, "Oscillator high gain"),
                        ( 7, 0x02, "External system clock source"),
                        ( 8, 0x20, "WDT disable after power-on-reset"),
                        ( 8, 0x04, "WDT count in idle mode"),
                        (10, 0x02, "Not erase data EEPROM"),
                        (10, 0x01, "Download regardless of P1")]
            print(" WDT prescal: %d" % 2**((self.info[8] & 0x07) + 1))

        elif self.protocol in PROTOSET_12B:
            switches = [(8, 0x02, "Not erase data EEPROM")]

        else:
            switches = []

        for pos, bit, desc in switches:
            print(" [%c] %s" % ("X" if self.info[pos] & bit else " ", desc))

    def handshake(self):
        baud0 = self.conn.baudrate

        for baud in [115200, 57600, 38400, 28800, 19200,
                     14400, 9600, 4800, 2400, 1200]:

            t = self.fosc * 1000000 / baud / 32
            if self.protocol not in PROTOSET_89:
                t *= 2

            if abs(round(t) - t) / t > 0.03:
                continue

            if self.protocol in PROTOSET_89:
                tcfg = 0x10000 - int(t + 0.5)
            else:
                if t > 0xFF:
                    continue
                tcfg = 0xC000 + 0x100 - int(t + 0.5)

            baudstr = [tcfg >> 8,
                       tcfg & 0xFF,
                       0xFF - (tcfg >> 8),
                       min((256 - (tcfg & 0xFF)) * 2, 0xFE),
                       int(baud0 / 60)]

            logging.info("Test baudrate %d (accuracy %0.4f) using config %s"
                         % (baud,
                            abs(round(t) - t) / t,
                            " ".join(["%02X" % i for i in baudstr])))

            if self.protocol in PROTOSET_89:
                freqlist = (40, 20, 10, 5)
            else:
                freqlist = (30, 24, 20, 12, 6, 3, 2, 1)

            for twait in range(0, len(freqlist)):
                if self.fosc > freqlist[twait]:
                    break

            logging.info("Waiting time config %02X" % (0x80 + twait))

            self.send(0x8F, baudstr + [0x80 + twait])

            try:
                self.__conn_baudrate(baud)
                cmd, dat = self.recv()
                break
            except Exception:
                logging.info("Cannot use baudrate %d" % baud)

                time.sleep(0.2)
                self.conn.flushInput()
            finally:
                self.__conn_baudrate(baud0, False)

        else:
            raise IOError()

        logging.info("Change baudrate to %d" % baud)

        self.send(0x8E, baudstr)
        self.__conn_baudrate(baud)
        self.baudrate = baud

        cmd, dat = self.recv()

    def erase(self):
        if self.protocol in PROTOSET_89:
            self.send(0x84, [0x01, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33])
            cmd, dat = self.recv(10)
            assert cmd == 0x80

        else:
            self.send(0x84, ([0x00, 0x00, self.romsize * 4,
                              0x00, 0x00, self.romsize * 4]
                             + [0x00] * 12
                             + [i for i in range(0x80, 0x0D, -1)]))
            cmd, dat = self.recv(10)
            if dat:
                logging.info("Serial number: "
                             + " ".join(["%02X" % j for j in dat]))

    def flash(self, code):
        code = list(code) + [0x00] * (511 - (len(code) - 1) % 512)

        for i in range(0, len(code), 128):
            logging.info("Flash code region (%04X, %04X)" % (i, i + 127))

            addr = [0, 0, i >> 8, i & 0xFF, 0, 128]
            self.send(0x00, addr + code[i:i+128])
            cmd, dat = self.recv()
            assert dat[0] == sum(code[i:i+128]) % 256

            yield (i + 128.0) / len(code)

    def options(self, **kwargs):
        erase_eeprom = kwargs.get("erase_eeprom", None)

        dat = []
        fosc = list(bytearray(struct.pack(">I", int(self.fosc * 1000000))))

        if self.protocol == PROTOCOL_89:
            if erase_eeprom is not None:
                self.info[2] &= 0xF7
                self.info[2] |= 0x00 if erase_eeprom else 0x08
            dat = self.info[2:3] + [0xFF]*3

        elif self.protocol == PROTOCOL_12C5A:
            if erase_eeprom is not None:
                self.info[10] &= 0xFD
                self.info[10] |= 0x00 if erase_eeprom else 0x02
            dat = (self.info[6:9] + [0xFF]*5 + self.info[10:11]
                   + [0xFF]*6 + fosc)

        elif self.protocol in PROTOSET_12B:
            if erase_eeprom is not None:
                self.info[8] &= 0xFD
                self.info[8] |= 0x00 if erase_eeprom else 0x02
            dat = (self.info[6:11] + fosc + self.info[12:16] + [0xFF]*4
                   + self.info[8:9] + [0xFF]*7 + fosc + [0xFF]*3)

        elif erase_eeprom is not None:
            logging.info("Modifying options is not supported for this target")
            return False

        if dat:
            self.send(0x8D, dat)
            cmd, dat = self.recv()

        return True

    def terminate(self):
        logging.info("Send termination command")

        self.send(0x82, [])
        self.conn.flush()
        time.sleep(0.2)

    def unknown_packet_1(self):
        if self.protocol in PROTOSET_PARITY:
            logging.info("Send unknown packet (50 00 00 36 01 ...)")
            self.send(0x50, [0x00, 0x00, 0x36, 0x01] + self.model)
            cmd, dat = self.recv()
            assert cmd == 0x8F and not dat

    def unknown_packet_2(self):
        if self.protocol not in PROTOSET_PARITY:
            for i in range(5):
                logging.info("Send unknown packet (80 00 00 36 01 ...)")
                self.send(0x80, [0x00, 0x00, 0x36, 0x01] + self.model)
                cmd, dat = self.recv()
                assert cmd == 0x80 and not dat

    def unknown_packet_3(self):
        if self.protocol in PROTOSET_PARITY:
            logging.info("Send unknown packet (69 00 00 36 01 ...)")
            self.send(0x69, [0x00, 0x00, 0x36, 0x01] + self.model)
            cmd, dat = self.recv()
            assert cmd == 0x8D and not dat


def autoisp(conn, baud, magic):
    if not magic:
        return

    bak = conn.baudrate
    conn.baudrate = baud
    conn.write(bytearray(ord(i) for i in magic))
    conn.flush()
    time.sleep(0.5)
    conn.baudrate = bak


def program(prog, code, erase_eeprom=None):
    sys.stdout.write("Detecting target...")
    sys.stdout.flush()

    prog.detect()

    print(" done")

    prog.print_info()

    if prog.protocol is None:
        raise IOError("Unsupported target")

    if code is None:
        return

    prog.unknown_packet_1()

    sys.stdout.write("Baudrate: ")
    sys.stdout.flush()

    prog.handshake()

    print(prog.baudrate)

    prog.unknown_packet_2()

    sys.stdout.write("Erasing target...")
    sys.stdout.flush()

    prog.erase()

    print(" done")

    print("Size of the binary: %d" % len(code))

    # print("Programming: ", end="", flush=True)
    sys.stdout.write("Programming: ")
    sys.stdout.flush()

    oldbar = 0
    for progress in prog.flash(code):
        bar = int(progress * 20)
        sys.stdout.write("#" * (bar - oldbar))
        sys.stdout.flush()
        oldbar = bar

    print(" done")

    prog.unknown_packet_3()

    sys.stdout.write("Setting options...")
    sys.stdout.flush()

    if prog.options(erase_eeprom=erase_eeprom):
        print(" done")
    else:
        print(" failed")

    prog.terminate()


# Convert Intel HEX code to binary format
def hex2bin(code):
    buf = bytearray()
    base = 0
    line = 0

    for rec in code.splitlines():
        # Calculate the line number of the current record
        line += 1

        try:
            # bytes(...) is to support python<=2.6
            # bytearray(...) is to support python<=2.7
            n = bytearray(binascii.a2b_hex(bytes(rec[1:3])))[0]
            dat = bytearray(binascii.a2b_hex(bytes(rec[1:n*2+11])))
        except:
            raise Exception("Line %d: Invalid format" % line)

        if rec[0] != ord(":"):
            raise Exception("Line %d: Missing start code \":\"" % line)
        if sum(dat) & 0xFF != 0:
            raise Exception("Line %d: Incorrect checksum" % line)

        if dat[3] == 0:      # Data record
            addr = base + (dat[1] << 8) + dat[2]
            # Allocate memory space and fill it with 0xFF
            buf[len(buf):] = [0xFF] * (addr + n - len(buf))
            # Copy data to the buffer
            buf[addr:addr+n] = dat[4:-1]

        elif dat[3] == 1:    # EOF record
            if n != 0:
                raise Exception("Line %d: Incorrect data length" % line)

        elif dat[3] == 2:    # Extended segment address record
            if n != 2:
                raise Exception("Line %d: Incorrect data length" % line)
            base = ((dat[4] << 8) + dat[5]) << 4

        elif dat[3] == 4:    # Extended linear address record
            if n != 2:
                raise Exception("Line %d: Incorrect data length" % line)
            base = ((dat[4] << 8) + dat[5]) << 16

        else:
            raise Exception("Line %d: Unsupported record type" % line)

    return buf


def main():
    if sys.platform == "win32":
        port = "COM3"
    elif sys.platform == "darwin":
        port = "/dev/tty.usbserial"
    else:
        port = "/dev/ttyUSB0"

    parser = argparse.ArgumentParser(
        description=("Stcflash, a command line programmer for "
                     + "STC 8051 microcontroller.\n"
                     + "https://github.com/laborer/stcflash"))
    parser.add_argument("image",
                        help="code image (bin/hex)",
                        type=argparse.FileType("rb"), nargs='?')
    parser.add_argument("-p", "--port",
                        help="serial port device (default: %s)" % port,
                        default=port)
    parser.add_argument("-l", "--lowbaud",
                        help="initial baud rate (default: 2400)",
                        type=int,
                        default=2400)
    parser.add_argument("-r", "--protocol",
                        help="protocol to use for programming",
                        choices=["89", "12c5a", "12c52", "12cx052", "auto"],
                        default="auto")
    parser.add_argument("-a", "--aispbaud",
                        help="baud rate for AutoISP (default: 4800)",
                        type=int,
                        default=4800)
    parser.add_argument("-m", "--aispmagic",
                        help="magic word for AutoISP")
    parser.add_argument("-v", "--verbose",
                        help="be verbose",
                        default=0,
                        action="count")
    parser.add_argument("-e", "--erase_eeprom",
                        help=("erase data eeprom during next download"
                              +"(experimental)"),
                        action="store_true")
    parser.add_argument("-ne", "--not_erase_eeprom",
                        help=("do not erase data eeprom next download"
                              +"(experimental)"),
                        action="store_true")

    opts = parser.parse_args()

    opts.loglevel = (logging.CRITICAL,
                     logging.INFO,
                     logging.DEBUG)[min(2, opts.verbose)]

    opts.protocol = {'89': PROTOCOL_89,
                     '12c5a': PROTOCOL_12C5A,
                     '12c52': PROTOCOL_12C52,
                     '12cx052': PROTOCOL_12Cx052,
                     'auto': None}[opts.protocol]

    if not opts.erase_eeprom and not opts.not_erase_eeprom:
        opts.erase_eeprom = None

    logging.basicConfig(format=("%(levelname)s: "
                                + "[%(relativeCreated)d] "
                                + "%(message)s"),
                        level=opts.loglevel)

    if opts.image:
        code = bytearray(opts.image.read())
        opts.image.close()
        if os.path.splitext(opts.image.name)[1] in (".hex", ".ihx"):
            code = hex2bin(code)
    else:
        code = None

    print("Connect to %s at baudrate %d" % (opts.port, opts.lowbaud))

    with serial.Serial(port=opts.port,
                       baudrate=opts.lowbaud,
                       parity=serial.PARITY_NONE) as conn:
        if opts.aispmagic:
            autoisp(conn, opts.aispbaud, opts.aispmagic)
        program(Programmer(conn, opts.protocol), code, opts.erase_eeprom)


if __name__ == "__main__":
    main()
