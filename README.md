stcflash
========

A command line programmer for STC 8051 microcontroller.

The programmer software provided by [STC](http://www.stcmcu.com/) for
their 8051-compatible microcontrollers (MCUs) only runs on Microsoft
Windows.  For developers who are more used to other operating systems,
this project, named *stcflash*, provides a more convenient way to
download program to STC 8051 microcontroller across different
platforms.  Other than its portability, stcflash also has the
advantage of employing a simple command line interface, so integrating
it in a development toolchain is fairly easy.

Installation
------------

[Python](http://www.python.org) (>=2.6) and its serial port extension
model [pySerial](http://pyserial.sf.net/) are required to run
stcflash.  Python is most likely pre-installed if you are using a
mainstream Linux distribution or OS X.  Module pySerial, on the other
hand, might need to be installed manually.  For example, on some
versions of Ubuntu, you must install package python-serial (or
python3-serial for Python 3) to get pySerial.  For operating system
without a package management system like Windows, please refer
pySerial's installation manual for further assistance.

How to use
----------

To read model information from the target microcontroller, simply run
stcflash without giving any parameter.

```
$ python stcflash.py
Connect to /dev/ttyUSB0 at baudrate 2400
Detecting target... done
 FOSC: 11.955MHz
 Model: STC89C52RC (ver4.3C)
 ROM: 8KB
```

Please note that, just like using the official STC programmer, once
the "Detecting target..." prompt is shown, you need to turn off and on
the microcontroller to enable the in-system programming (ISP) routine,
otherwise, stcflash cannot connect to the target.

If the microcontroller hooks up to a different port than the first
USB-to-serial port, you can use `--port` to specify the name of the
port.  It is also possible to specify a different initial baudrate
using `--lowbaud` option, although this should not be necessary in
most cases.  Here is an example,

```
$ python stcflash.py --port /dev/ttyUSB1 --lowbaud 1200
Connect to /dev/ttyUSB1 at baudrate 1200
Detecting target...
```

This program can download compiled code in either binary (.bin) or
Intel HEX (.ihx/.hex) format into the target microcontroller like the
following example,

```
$ python stcflash.py program.hex
Connect to /dev/ttyUSB0 at baudrate 2400
Detecting target... done
 FOSC: 11.955MHz
 Model: STC89C52RC (ver4.3C)
 ROM: 8KB
Baudrate: 38400
Erasing target... done
Size of the binary: 917
Programming: #################### done
```

For now, stcflash supports the following series of MCUs and their low
voltage variants.

> STC89C5xRC, STC89C5xRD+, STC90C5xRC, STC10Fxx, STC11Fxx,
> STC12Cx052x, STC12C52xx, STC12C56xx, STC12C5Axx

If stcflash is unable to detect the microcontroller, forcing the
programming protocol using `--protocol` option might solve the
problem.  For example, if a microcontroller uses the same programming
protocol as STC89C5xRC series, then you can program it as follows,

```
$ python stcflash.py --protocol 89 program.bin
```

The following is a table of protocols and corresponding MCUs that have
been tested working with each protocol.

Protocol | MCUs
---------|---------------------
89       | STC89C52RC (v4.3C), STC89C54RD+ (v4.3C), STC90C52RC (v4.3C)
12cx052  | STC12C2052 (v5.8D)
12c52    | STC12C5608AD (v6.0G), STC12C5204AD (v6.0H)
12c5a    | STC10F04XE (v6.5J), STC12C5A16S2 (v6.2I),  STC11F02E (v6.5K)

Before connecting to a microcontroller using one of the ISP protocols,
stcflash can send a magic word first at a given baudrate to ask the
microcontroller to enter ISP mode without user switching its power off
and on.  Please note that the user program on the microcontroller must
be able to reboot itself to the ISP section upon receiving the magic
word to make this scheme work.  The following is an example,

```
$ python stcflash.py --aispbaud 2400 --aispmagic 6af23Qtr program.bin
```

You can use `-e` option to enable erasing data EEPROM during every
programming operation and use `-ne` to disable this function.

Troubleshooting
---------------

Use `-v` or `-vv` to get more or MOAR runtime information.

If you have any questions, please feel free to contact me at
laborer(a)126.com.
