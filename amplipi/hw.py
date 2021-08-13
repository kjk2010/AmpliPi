#!/usr/bin/env python3
#
# AmpliPi Home Audio
# Copyright (C) 2021 MicroNova LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""AmpliPi hardware interface """

import argparse
from enum import Enum
import io
import os
from RPi import GPIO
from serial import Serial
from smbus2 import SMBus
import subprocess
import sys
import time
from typing import Tuple

def is_amplipi():
  """ Check if the current hardware is an AmpliPi

    Checks if the system is a Raspberry Pi Compute Module 3 Plus
    with the proper serial port and I2C bus

    Returns:
      True if current hardware is an AmpliPi, False otherwise
  """
  amplipi = True

  # Check for Raspberry Pi
  try:
    # Also available in /proc/device-tree/model, and in /proc/cpuinfo's "Model" field
    with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
      desired_model = 'Raspberry Pi Compute Module 3 Plus'
      current_model = m.read()
      if desired_model.lower() not in current_model.lower():
        print(f"Device model '{current_model}'' doesn't match '{desired_model}*'")
        amplipi = False
  except Exception:
    print('Not running on a Raspberry Pi')
    amplipi = False

  # Check for the serial port
  if not os.path.exists('/dev/serial0'):
    print('Serial port /dev/serial0 not found')
    amplipi = False

  # Check for the i2c bus
  if not os.path.exists('/dev/i2c-1'):
    print('I2C bus /dev/i2c-1 not found')
    amplipi = False

  return amplipi


class Preamp:
  """ Low level discovery and communication for the AmpliPi Preamp's firmware """

  # Preamp register addresses
  class Reg(Enum):
    SRC_AD          = 0x00
    CH123_SRC       = 0x01
    CH456_SRC       = 0x02
    MUTE            = 0x03
    STANDBY         = 0x04
    CH1_ATTEN       = 0x05
    CH2_ATTEN       = 0x06
    CH3_ATTEN       = 0x07
    CH4_ATTEN       = 0x08
    CH5_ATTEN       = 0x09
    CH6_ATTEN       = 0x0A
    POWER_GOOD      = 0x0B
    FAN_STATUS      = 0x0C
    EXTERNAL_GPIO   = 0x0D
    LED_OVERRIDE    = 0x0E
    EXPANSION       = 0x0F
    HV1_VOLTAGE     = 0x10
    HV2_VOLTAGE     = 0x11
    HV1_TEMP        = 0x12
    HV2_TEMP        = 0x13
    VERSION_MAJOR   = 0xFA
    VERSION_MINOR   = 0xFB
    GIT_HASH_27_20  = 0xFC
    GIT_HASH_19_12  = 0xFD
    GIT_HASH_11_04  = 0xFE
    GIT_HASH_STATUS = 0xFF

  def __init__(self, unit: int, bus: SMBus):
    """ Preamp constructor

      Args:
        unit: integer unit number, master = 0, expansion #1 = 1, etc.
    """
    self.addr = (unit + 1) * 0x8
    self.bus = bus

  def available(self) -> bool:
    """ Check if a unit is available on the I2C bus by attempting to write to
        its Version register. The write will be discarded as this is a
        read-only register, however no error will be thrown so long as an
        ACK is received on the I2C bus.
    """
    try:
      self.bus.write_byte_data(self.addr, self.Reg.VERSION_MAJOR.value, 0)
    except OSError as e:
      #print(e)
      return False
    return True

  def read_leds(self) -> int:
    """ Read the LED board's status

      Returns:
        leds:   A 1-byte number with each bit corresponding to an LED
                Bit 0 => Green,
                Bit 1 => Red,
                Bit[2-7] => Zone[1-6]
    """
    return self.bus.read_byte_data(self.addr, self.Reg.LED_OVERRIDE.value)

  def write_leds(self, leds: int = 0xFF) -> None:
    """ Override the LED board's LEDs

      Args:
        leds:   A 1-byte number with each bit corresponding to an LED
                Bit 0 => Green,
                Bit 1 => Red,
                Bit[2-7] => Zone[1-6]
    """
    assert 0 <= leds <= 255
    self.bus.write_byte_data(self.addr, self.Reg.LED_OVERRIDE.value, leds)

  def read_version(self) -> Tuple[int, int, int, bool]:
    """ Read the firmware version of the preamp

      Returns:
        major:    The major revision number
        minor:    The minor revision number
        git_hash: The git hash of the build (7-digit abbreviation)
        dirty:    False if the git hash is valid, True otherwise
    """
    major = self.bus.read_byte_data(self.addr, self.Reg.VERSION_MAJOR.value)
    minor = self.bus.read_byte_data(self.addr, self.Reg.VERSION_MINOR.value)
    git_hash = self.bus.read_byte_data(self.addr, self.Reg.GIT_HASH_27_20.value) << 20
    git_hash |= (self.bus.read_byte_data(self.addr, self.Reg.GIT_HASH_19_12.value) << 12)
    git_hash |= (self.bus.read_byte_data(self.addr, self.Reg.GIT_HASH_11_04.value) << 4)
    git_hash4_stat = self.bus.read_byte_data(self.addr, self.Reg.GIT_HASH_STATUS.value)
    git_hash |= (git_hash4_stat >> 4)
    dirty = (git_hash4_stat & 0x01) != 0
    return major, minor, git_hash, dirty

  def reset_expander(self, bootloader: bool = False) -> None:
    """ Resets expansion unit connected to this preamp, if any """
    # Enter reset state
    reg_val = 2 if bootloader else 0
    self.bus.write_byte_data(self.addr, self.Reg.EXPANSION.value, reg_val)
    #i2cset -y 1 0x08 0x0F 0x02 &&
    #sleep 0.01 &&
    #i2cset -y 1 0x08 0x0F 0x0F &&

    # Hold the reset line low >300 ns, then set high
    time.sleep(0.01)
    reg_val |= 1
    self.bus.write_byte_data(self.addr, self.Reg.EXPANSION.value, reg_val)

    # Each preamps' microcontroller takes ~3ms to startup after releasing
    # NRST. Just to be sure wait 5 ms before sending an I2C address.
    time.sleep(0.005)

  def uart_passthrough(self, passthrough: bool) -> None:
    reg_val = self.bus.read_byte_data(self.addr, self.Reg.EXPANSION.value)
    if passthrough: # TODO: only 4 once single bit
      reg_val |= 12
    else:
      reg_val &= 3
    self.bus.write_byte_data(self.addr, self.Reg.EXPANSION.value, reg_val)


class Preamps:
  """ AmpliPi Preamp Board manager """

  """ The maximum number of AmpliPi units, including the master """
  MAX_UNITS = 6

  """ Valid UART baud rates """
  BAUD_RATES = (  1200,   1800,   2400,   4800,    9600,  19200,
                 38400,  57600, 115200, 128000,  230400, 256000,
                460800, 500000, 576000, 921600, 1000000)

  class Pin(Enum):
    """ Pi GPIO pins to control the master unit's preamp """
    NRST  = 4
    BOOT0 = 5

  def __init__(self, reset: bool = False):
    self.bus = SMBus(1)
    self.preamps = []
    if reset:
      print('Resetting all preamps...')
      self.reset(unit = 0, bootloader = False)
    else:
      self.enumerate()

  def __getitem__(self, key: int) -> Preamp:
    return self.preamps[key]

  def __setitem__(self, key: int, value: Preamp) -> None:
    self.preamps[key] = value

  def __len__(self) -> int:
    return len(self.preamps)

  def reset(self, unit: int = 0, bootloader: bool = False) -> None:
    """ Resets the master unit's preamp board.
        Any expansion preamps will be reset one-by-one by the previous preamp.
        After resetting, an I2C address is assigned.

      Args:
        unit:       Reset from the given unit number onward. 0=master
        bootloader: If True, set BOOT0 pin high to enter bootloader mode after reset
    """

    # TODO: If unit=1,2,3,4, or 5, only reset those units and onward

    if unit == 0:
      # Reset and return if bringing up in bootloader mode
      self._reset_master(bootloader)
      if bootloader:
        time.sleep(0.01)
        return

      # Send I2C address over UART
      with Serial('/dev/serial0', baudrate=115200) as ser:
        ser.write((0x41, 0x10, 0x0D, 0x0A))
      if not Preamp(0, self.bus).available():
        print('Falling back to 9600 baud, is firmware version >=1.2?')
        # The failed attempt at 115200 baud seems to put v1.1 firmware in a bad
        # state, so reset and try again at 9600 baud.
        self._reset_master(bootloader = False)
        with Serial('/dev/serial0', baudrate=9600) as ser:
          ser.write((0x41, 0x10, 0x0D, 0x0A))
    else:
      self.preamps[unit - 1].reset_expander(bootloader)

    # Delay to account for address being set
    # Each box theoretically takes ~5ms to receive its address. Again, estimate for max boxes and include some padding
    time.sleep(0.01 * (self.MAX_UNITS - unit))

    # If resetting the master and not entering bootloader mode, re-enumerate
    if not bootloader and unit == 0:
      self.enumerate()

  def _reset_master(self, bootloader: bool) -> None:
    # Reset the master (and by extension any expansion units)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(self.Pin.NRST.value, GPIO.OUT)
    GPIO.output(self.Pin.NRST.value, 0)

    # After reset the BOOT0 pin is sampled to determine whether to boot
    # from the bootloader ROM or flash.
    GPIO.setup(self.Pin.BOOT0.value, GPIO.OUT)
    GPIO.output(self.Pin.BOOT0.value, bootloader)

    # Hold the reset line low >300 ns
    time.sleep(0.001)
    GPIO.output(self.Pin.NRST.value, 1)

    # Each preamps' microcontroller takes ~3ms to startup after releasing
    # NRST. Just to be sure wait 5 ms before sending an I2C address.
    time.sleep(0.005)
    GPIO.cleanup()

  def enumerate(self) -> None:
    """ Re-enumerate preamp connections """
    self.preamps = []
    for i in range(self.MAX_UNITS):
      p = Preamp(i, self.bus)
      if not p.available():
        break
      self.preamps.append(p)
    print(f'Found {len(self.preamps)} preamp(s)')

  def flash(self, filepath: str, baud: int = 115200) -> None:
    """ Flash all available preamps with a given file """

    if baud not in self.BAUD_RATES:
      raise ValueError(f'Baud rate must be one of {self.BAUD_RATES}')

    # Flash all units found, but if nothing shows up
    # attempt flashing the master preamp at least
    num_units = len(self.preamps)
    if num_units == 0:
      num_units = 1

    for unit in range(num_units):
      #i2cset -y 1 0x08 0x0F 0x02 &&
      #sleep 0.01 &&
      #i2cset -y 1 0x08 0x0F 0x0F &&
      print(f"Resetting unit {unit}'s preamp and starting execution in bootloader ROM")
      self.reset(unit = unit, bootloader = True)
      for p in range(unit): # Set UART passthrough on any previous units
        print(f'Setting unit {p} as passthrough')
        self.preamps[p].uart_passthrough(True)
      subprocess.run([f'stm32flash -vb {baud} -w {filepath} /dev/serial0'], shell=True, check=True)
      # TODO: Error handling
      print('Resetting all preamps and starting execution in user flash')
      self.reset()
      major, minor, git_hash, dirty = self.preamps[unit].read_version()
      print(f'Unit {unit} version: {major}, {minor}')


#class PeakDetect:
  #""" """


# Remove duplicate metavars
# https://stackoverflow.com/a/23941599/8055271
class AmpliPiHelpFormatter(argparse.HelpFormatter):
  def _format_action_invocation(self, action):
    if not action.option_strings:
      metavar, = self._metavar_formatter(action, action.dest)(1)
      return metavar
    parts = []
    if action.nargs == 0:                   # -s, --long
      parts.extend(action.option_strings)
    else:                                   # -s, --long ARGS
      args_string = self._format_args(action, action.dest.upper())
      for option_string in action.option_strings:
        parts.append('%s' % option_string)
      parts[-1] += ' %s' % args_string
    return ', '.join(parts)

  def _get_help_string(self, action):
    help_str = action.help
    if '%(default)' not in action.help:
      if action.default is not argparse.SUPPRESS and action.default is not None:
        defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
        if action.option_strings or action.nargs in defaulting_nargs:
          help_str += ' (default: %(default)s)'
    return help_str


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description="Interface to AmpliPi's Preamp Board firmware",
                                 formatter_class=AmpliPiHelpFormatter)
  parser.add_argument('-r', '--reset', action='store_true', default=False,
                      help='reset the preamp(s) before communicating over I2C')
  parser.add_argument('--flash', metavar='FW.bin',
                      help='update the preamp(s) with the firmware in a .bin file')
  parser.add_argument('-b', '--baud', type=int, default=115200,
                      help='baud rate to use for UART communication')
  parser.add_argument('-v', '--version', action='store_true', default=False,
                      help='print preamp firmware version(s)')
  parser.add_argument('-l', '--log', metavar='LEVEL', default='WARNING',
                      help='set logging level as DEBUG, INFO, WARNING, ERROR, or CRITICAL')
  args = parser.parse_args()

  preamps = Preamps(args.reset)

  if args.flash is not None:
    preamps.flash(filepath = args.flash, baud = args.baud)

  if len(preamps) == 0:
    print('No preamps found, exiting')
    sys.exit(1)

  if args.version:
    major, minor, git_hash, dirty = preamps[0].read_version()
    print(f'Master preamp firmware version: {major}.{minor}-{git_hash:07X}, {"dirty" if dirty else "clean"}')
