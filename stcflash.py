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
import getopt
import serial


PROTOCOL_STC89 = 89
PROTOCOL_STC12 = 12
PROTOCOL_STC12Cx052 = 12.1052


class Programmer:
    def __init__(self, conn, protocol=None):
        self.conn = conn
        self.protocol = protocol

        self.conn.timeout = 0.05
        if self.protocol in (PROTOCOL_STC89, PROTOCOL_STC12Cx052, None):
            self.conn.parity = serial.PARITY_NONE
        else:
            self.conn.parity = serial.PARITY_EVEN

        self.chkmode = 0

    def __conn_read(self, size):
        buf = []
        while len(buf) < size:
            s = [i if isinstance(i, int) else ord(i) 
                 for i in self.conn.read(size - len(buf))]
            buf += s

            logging.debug("recv: " + ' '.join(['%02X' % i for i in s]))

            if len(s) == 0:
                raise IOError()

        return buf

    def __conn_write(self, s):
        logging.debug("send: " + ' '.join(['%02X' % i for i in s]))
        
        s = ''.join(chr(i) for i in s) if sys.version_info[0] < 3 else bytes(s)
        self.conn.write(s)

    def __conn_baudrate(self, baud, flush=True):
        logging.debug("baud: %d" % baud)

        if flush:
            self.conn.flush()
            time.sleep(0.2)

        self.conn.baudrate = baud

    def __model_database(self, model):
        modelmap = {0xE0: ('12', 1, {(0x00, 0x1F): ('C54', ''),
                                     (0x60, 0x7F): ('C54', 'AD'),
                                     (0x80, 0x9F): ('LE54', ''),
                                     (0xE0, 0xFF): ('LE54', 'AD'),
                                     }),
                    0xE1: ('12', 1, {(0x00, 0x1F): ('C52', ''),
                                     (0x20, 0x3F): ('C52', 'PWM'),
                                     (0x60, 0x7F): ('C52', 'AD'),
                                     (0x80, 0x9F): ('LE52', ''),
                                     (0xA0, 0xBF): ('LE52', 'PWM'),
                                     (0xE0, 0xFF): ('LE52', 'AD'),
                                     }),
                    0xE2: ('11', 1, {(0x00, 0x1F): ('F', ''),
                                     (0x20, 0x3F): ('F', 'E'),
                                     (0x70, 0x7F): ('F', ''),
                                     (0x80, 0x9F): ('L', ''),
                                     (0xA0, 0xBF): ('L', 'E'),
                                     (0xF0, 0xFF): ('L', ''),
                                     }),
                    0xE6: ('12', 1, {(0x00, 0x1F): ('C56', ''),
                                     (0x60, 0x7F): ('C56', 'AD'),
                                     (0x80, 0x9F): ('LE56', ''),
                                     (0xE0, 0xFF): ('LE56', 'AD'),
                                     }),
                    0xD1: ('12', 2, {(0x20, 0x3F): ('C5A', 'CCP'),
                                     (0x40, 0x5F): ('C5A', 'AD'),
                                     (0x60, 0x7F): ('C5A', 'S2'),
                                     (0xA0, 0xBF): ('LE5A', 'CCP'),
                                     (0xC0, 0xDF): ('LE5A', 'AD'),
                                     (0xE0, 0xFF): ('LE5A', 'S2'),
                                     }),
                    0xD2: ('10', 1, {(0x00, 0x0F): ('F', ''),
                                     (0x60, 0x6F): ('F', 'XE'),
                                     (0x70, 0x7F): ('F', 'X'),
                                     (0xA0, 0xAF): ('L', ''),
                                     (0xE0, 0xEF): ('L', 'XE'),
                                     (0xF0, 0xFF): ('L', 'X'),
                                     }),
                    0xD3: ('11', 2, {(0x00, 0x1F): ('F', ''),
                                     (0x40, 0x5F): ('F', 'X'),
                                     (0x60, 0x7F): ('F', 'XE'),
                                     (0xA0, 0xBF): ('L', ''),
                                     (0xC0, 0xDF): ('L', 'X'),
                                     (0xE0, 0xFF): ('L', 'XE'),
                                     }),
                    0xF0: ('89', 4, {(0x00, 0x10): ('C5', 'RC'),
                                     (0x20, 0x30): ('C5', 'RC'),  #STC90C5xRC
                                     }),
                    0xF1: ('89', 4, {(0x00, 0x10): ('C5', 'RD+'),
                                     (0x20, 0x30): ('C5', 'RD+'),  #STC90C5xRD+
                                     }),
                    0xF2: ('12', 1, {(0x00, 0x0F): ('C', '052'),
                                     (0x10, 0x1F): ('C', '052AD'),
                                     (0x20, 0x2F): ('LE', '052'),
                                     (0x30, 0x3F): ('LE', '052AD'),
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
                prefix = '90'

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
                romfix = '%02d' % romsize
            
            name = 'IAP' if model in iapmcu else 'STC' 
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
            logging.debug('recv(..): timeout'); 
            raise IOError()

        chksum = start[-1]

        s = self.__conn_read(2)
        n = s[0] * 256 + s[1]
        if n > 64:
            logging.debug('recv(..): incorrect packet size');
            raise IOError()
        chksum += sum(s);

        s = self.__conn_read(n - 3)
        if s[n - 4] != 0x16:
            logging.debug('recv(..): missing terminal symbol');
            raise IOError()
        
        chksum += sum(s[:-(1+self.chkmode)])
        if self.chkmode > 0 and chksum & 0xFF != s[-2]:
            logging.debug('recv(..): incorrect checksum[0]');
            raise IOError()
        elif self.chkmode > 1 and (chksum >> 8) & 0xFF != s[-3]:
            logging.debug('recv(..): incorrect checksum[1]');
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
        self.version = '%d.%d%c' % (self.info[0] >> 4, 
                                    self.info[0] & 0x0F, 
                                    self.info[1])
        self.model = self.info[3:5]

        self.name, self.romsize = self.__model_database(self.model)

        logging.info("Model ID: %02X %02X" % tuple(self.model))
        logging.info("Model name: %s" % self.name)
        logging.info("ROM size: %s" % self.romsize)

        if self.protocol is None:
            try:
                self.protocol = {0xF0: PROTOCOL_STC89,       #STC89/90C5xRC
                                 0xF1: PROTOCOL_STC89,       #STC89/90C5xRD+
                                 0xF2: PROTOCOL_STC12Cx052,  #STC12Cx052
                                 0xD1: PROTOCOL_STC12,       #STC12C5Ax
                                 0xD2: PROTOCOL_STC12,       #STC10Fx
                                 0xE1: PROTOCOL_STC12,       #STC12C52x
                                 0xE2: PROTOCOL_STC12,       #STC11Fx
                                 0xE6: PROTOCOL_STC12,       #STC12C56x
                                 }[self.model[0]]
            except KeyError:
                pass
            
        if self.protocol in (PROTOCOL_STC89, PROTOCOL_STC12Cx052):
            self.chkmode = 1
            self.conn.parity = serial.PARITY_NONE
        elif self.protocol == PROTOCOL_STC12:
            self.chkmode = 2
            self.conn.parity = serial.PARITY_EVEN

        if self.protocol is not None:
            del self.info[-self.chkmode:]

            logging.info("Protocol ID: %d" % self.protocol)
            logging.info("Checksum mode: %d" % self.chkmode)
            logging.info("UART Parity: %s" 
                         % {serial.PARITY_NONE: 'NONE',
                            serial.PARITY_EVEN: 'EVEN',
                            }[self.conn.parity])

        for i in range(0, len(self.info), 16):
            logging.info("Info string [%d]: %s" 
                         % (i // 16, 
                            ' '.join(['%02X' % j for j in self.info[i:i+16]])))

    def handshake(self):
        baud0 = self.conn.baudrate

        for baud in [115200, 57600, 38400, 28800, 19200, 
                     14400, 9600, 4800, 2400, 1200]:

            t = self.fosc * 1000000 / baud / 32
            if self.protocol in (PROTOCOL_STC12, PROTOCOL_STC12Cx052):
                t *= 2

            if abs(round(t) - t) / t > 0.03:
                continue

            if self.protocol == PROTOCOL_STC89:
                tcfg = 0x10000 - int(t + 0.5)
            elif self.protocol in (PROTOCOL_STC12, PROTOCOL_STC12Cx052):
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
                            ' '.join(['%02X' % i for i in baudstr])))

            if self.protocol == PROTOCOL_STC89:
                freqlist = (40, 20, 10, 5)
            elif self.protocol in (PROTOCOL_STC12, PROTOCOL_STC12Cx052):
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
        logging.info("Erase")

        if self.protocol == PROTOCOL_STC89:
            self.send(0x84, [0x01, 0x33, 0x33, 0x33, 0x33, 0x33, 0x33])
            cmd, dat = self.recv(10)
            assert cmd == 0x80

        elif self.protocol in (PROTOCOL_STC12, PROTOCOL_STC12Cx052):
            self.send(0x84, ([0x00, 0x00, self.romsize * 4,
                              0x00, 0x00, self.romsize * 4]
                             + [0x00] * 12
                             + [i for i in range(0x80, 0x0D, -1)]))
            cmd, dat = self.recv(10)
            assert (self.protocol != PROTOCOL_STC12Cx052 or cmd == 0x80)
            assert (self.protocol != PROTOCOL_STC12 or cmd == 0x00)
            if dat:
                logging.info("Serial number: " 
                             + ' '.join(['%02X' % j for j in dat]))
        
    def flash(self, code):
        code = [ord(i) for i in code] if sys.version_info[0] < 3 else list(code)
        code += [0x00] * (511 - (len(code) - 1) % 512)

        for i in range(0, len(code), 128):
            logging.info("Flash code region (%04X, %04X)" % (i, i + 127))

            addr = [0, 0, i >> 8, i & 0xFF, 0, 128]
            self.send(0x00, addr + code[i:i+128])
            cmd, dat = self.recv()
            assert dat[0] == sum(code[i:i+128]) % 256

            yield (i + 128.0) / len(code)

    def terminate(self):
        logging.info("Send termination command")
        
        self.send(0x82, b'')
        self.conn.flush()
        time.sleep(0.2)


def autoisp(conn, baud, magic):
    if not magic:
        return

    bak = conn.baudrate
    conn.baudrate = baud;
    conn.write(magic);
    conn.flush()
    time.sleep(0.5)
    conn.baudrate = bak

def program(prog, code):
    sys.stdout.write("Detecting target...")
    sys.stdout.flush()

    prog.detect()

    print(" done")
    
    print(" FOSC: %.3fMHz" % prog.fosc)
    print(" Model: %s (ver%s) " % (prog.name, prog.version))
    if prog.romsize is not None:
        print(" ROM: %dKB" % prog.romsize)
    
    # if prog.protocol == PROTOCOL_STC89:
    #     switchs = {0x80: "Reset stops watchdog",
    #                0x40: "Internal XRAM",
    #                0x20: "Normal ALE pin",
    #                0x10: "Full gain oscillator",
    #                0x04: "Download regardless P1",
    #                0x01: "12T mode"}
    #     for key, desc in switchs.items():
    #         print("[%c] %s" % ('X' if prog.info[2] & key != 0 else ' ', desc))

    if prog.protocol is None:
        raise IOError("Unsupported target")

    if code is None:
        return

    if prog.protocol == PROTOCOL_STC12:
        prog.send(0x50, [0x00, 0x00, 0x36, 0x01] + prog.model)
        cmd, dat = prog.recv()
        assert cmd == 0x8F and not dat

    sys.stdout.write("Baudrate: ")
    sys.stdout.flush()

    prog.handshake()

    print(prog.baudrate)

    if prog.protocol in (PROTOCOL_STC89, PROTOCOL_STC12Cx052):
        for i in range(5):
            logging.info("Send unknown packet (80 00 00 36 01 ...)")

            prog.send(0x80, [0x00, 0x00, 0x36, 0x01] + prog.model)
            cmd, dat = prog.recv()
            assert cmd == 0x80 and not dat

    sys.stdout.write("Erasing target...")
    sys.stdout.flush()

    prog.erase()

    print(" done")

    print("Size of the binary: %d" % len(code));

    # print("Programming: ", end='', flush=True)
    sys.stdout.write("Programming: ")
    sys.stdout.flush()

    oldbar = 0
    for progress in prog.flash(code):
        bar = int(progress * 20)
        # print('#' * (bar - oldbar), end='', flush=True)
        sys.stdout.write('#' * (bar - oldbar))
        sys.stdout.flush()
        oldbar = bar

    print(" done")

    if prog.protocol == PROTOCOL_STC12:
        logging.info("Send unknown packet (80 00 00 36 01 ...)")

        prog.send(0x69, [0x00, 0x00, 0x36, 0x01] + prog.model)
        cmd, dat = prog.recv()
        assert cmd == 0x8D and not dat

    # if prog.protocol == PROTOCOL_STC89:
    #     logging.info("Read configuration")

    #     prog.write(0x50, [])
    #     prog.read()

    prog.terminate()


def usage():
    port = 'COM3' if sys.platform.startswith('win') else '/dev/ttyUSB0'

    print("Usage: %s [OPTION]... [bin file]" % sys.argv[0])
    print("""
  -p, --port       specify serial port (default: %(port)s)
  -l, --lowbaud    specify lower baudrate (default: 2400)
  -r, --protocol   specify flashing procotol (default: auto)
  -a, --aispbaud   specify the baudrate for AutoISP (default: 4800)
  -m, --aispmagic  specify the magic word to restart to ISP mode
  -v, --verbose    be verbose
  -d, --debug      print debug message
  -h, --help       give this help list
""" % {'port': port})
  

def main():
    port = 'COM3' if sys.platform.startswith('win') else '/dev/ttyUSB0'
    lowbaud = 2400
    loglevel = logging.CRITICAL
    code = None
    protocol = None
    aispbaud = 4800
    aispmagic = None
    
    try:
        opts, args = getopt.getopt(sys.argv[1:], 
                                   "vdhp:l:r:a:m:", 
                                   ["verbose", 
                                    "debug", 
                                    "help", 
                                    "port=", 
                                    "lowbaud=", 
                                    "protocol=",
                                    "aispbaud=",
                                    "aispmagic="])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(2)
        
    for o, a in opts:
        if o in ('-v', '--verbose'):
            loglevel = min(loglevel, logging.INFO)
        elif o in ('-d', '--debug'):
            loglevel = min(loglevel, logging.DEBUG)
        elif o in ('-h', '--help'):
            usage()
            sys.exit()
        elif o in ('-p', '--port'):
            port = a
        elif o in ('-l', '--lowbaud'):
            lowbaud = int(a)
        elif o in ('-r', '--protocol'):
            try:
                protocol = {'89': PROTOCOL_STC89,
                            '12': PROTOCOL_STC12,
                            '12cx052': PROTOCOL_STC12Cx052,
                            'auto': None,
                            }[a.lower()]
            except:
                print("Unknown protocol")
                sys.exit(2)
        elif o in ('-a', '--aispbaud'):
            aispbaud = int(a)
        elif o in ('-m', '--aispmagic'):
            aispmagic = a;

    logging.basicConfig(format=('%(levelname)s: '
                                + '[%(relativeCreated)d] '
                                + '%(message)s'),
                        level=loglevel)

    if len(args) > 0:
        with open(args[0], 'rb') as f:
            code = f.read()

    print("Connect to %s at baudrate %d" % (port, lowbaud))
    with serial.Serial(port=port, 
                       baudrate=lowbaud, 
                       parity=serial.PARITY_NONE) as conn:
        if aispmagic:
            autoisp(conn, aispbaud, aispmagic)
        program(Programmer(conn, protocol), code)


if __name__ == "__main__":
    main()
