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
mainstream Linux distribution.  Module pySerial, on the other hand,
might need to be installed manually.  For example, on Ubuntu, you must
install package python-serial (or python3-serial for Python 3) to get
pySerial.  For operating system without a package management system
like Windows, please refer pySerial's installation manual for further
assistance.

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
the microcontroller to enable the in-system programming (ISP) routing,
otherwise, stcflash cannot connect to the target.

If the microcontoller does not hook up to the first USB-to-serial
port, You can use `--port` to specify a different serial port.  It is
also possible to specify a different initial baudrate using
`--lowbaud` option, although this should not be necessary in most
cases.  The following is an example.

```
$ python stcflash.py --port /dev/ttyUSB1 --lowbaud 1200
Connect to /dev/ttyUSB1 at baudrate 1200
Detecting target...
```

To download program into the target, the compiled code must be in
binary format (.bin), as it is the only format that stcflash supports.
If you want to program an Intel HEX file (.ihx or .hex), it needs to
be converted to binary format first.  On a Linux system, this can be
done as follows,

```
$ objcopy -Iihex -Obinary program.hex program.bin
```

Then you can program the .bin file using the following command,

```
$ python stcflash.py program.bin
Connect to /dev/ttyUSB0 at baudrate 2400
Detecting target... done
 FOSC: 11.955MHz
 Model: STC89C52RC (ver4.3C) 
 ROM: 8KB
Baudrate: 38400
Erasing target... done
Programming: #################### done
```

At this moment, stcflash can program STC89C5xx, STC12C5Axx, STC12C52xx
series and their low voltage variants.  It might work properly with
other series by specifying a programming protocol using `--protocol`
option.  For example, if a microcontoller uses the same programming
protocol as STC89C5xx series, then you can program it as follows,

```
$ python stcflash.py --protocol 89 program.bin
```

If its protocol is compatible with STC12C5Axx or STC12C52xx series,
then use the following command instead,

```
$ python stcflash.py --protocol 12 program.bin
```

Troubleshooting
---------------

Use `--verbose` or `--debug` to get more or MOAR runtime information.

If you have any questions, please feel free to contact me at
laborer(a)126.com.
