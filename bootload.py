#!/usr/bin/env python
#
# Bootloader for the Swift Navigation Piksi GPS Receiver
#
# Copyright (C) 2010 Gareth McMullin <gareth@blacksphere.co.nz>
# Copyright (C) 2011 Piotr Esden-Tempski <piotr@esden.net>
# Copyright (C) 2013-2014 Swift Navigation Inc <www.swift-nav.com>
#
# Contacts: Colin Beighley <colin@swift-nav.com>
#           Fergus Noble <fergus@swift-nav.com>
#
# Based on luftboot, a bootloader for the Paparazzi UAV project.
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import sbp_piksi as ids
import time
import struct

class Bootloader():

  def __init__(self, link):
    self.stopped = False
    self.handshake_received = False
    self.version = None
    self.link = link
    self.link.add_callback(ids.BOOTLOADER_HANDSHAKE,self._handshake_callback)

  def __del__(self):
    if not self.stopped:
      self.stop()

  def stop(self):
    self.stopped = True
    self.link.rm_callback(ids.BOOTLOADER_HANDSHAKE, self._handshake_callback)

  def _handshake_callback(self, data):
    if len(data)==1 and struct.unpack('B', data[0])==0:
      # == v0.1 of the bootloader, returns hardcoded version number 0.
      self.version = "v0.1"
    else:
      # > v0.1 of the bootloader, returns git commit string.
      self.version = data[:]
    self.handshake_received = True

  def wait_for_handshake(self):
    self.handshake_received = False
    while not self.handshake_received:
      time.sleep(0.1)

  def reply_handshake(self):
    self.link.send_message(ids.BOOTLOADER_HANDSHAKE, '\x00')

  def jump_to_app(self):
    self.link.send_message(ids.BOOTLOADER_JUMP_TO_APP, '\x00')

if __name__ == "__main__":
  import argparse
  import thread
  import sys
  from intelhex import IntelHex
  import serial_link
  import flash
  parser = argparse.ArgumentParser(description='Piksi Bootloader')
  parser.add_argument("file",
                      help="the Intel hex file to write to flash.")
  parser.add_argument('-m', '--m25',
                      help='write the file to the M25 (FPGA) flash.',
                      action="store_true")
  parser.add_argument('-s', '--stm',
                      help='write the file to the STM flash.',
                      action="store_true")
  parser.add_argument('-e', '--erase',
                      help='erase sectors 1-11 of the STM flash.',
                      action="store_true")
  parser.add_argument('-p', '--port',
                      default=[serial_link.DEFAULT_PORT], nargs=1,
                      help='specify the serial port to use.')
  parser.add_argument("-b", "--baud",
                      default=[serial_link.DEFAULT_BAUD], nargs=1,
                      help="specify the baud rate to use.")
  parser.add_argument("-f", "--ftdi",
                      help="use pylibftdi instead of pyserial.",
                      action="store_true")
  args = parser.parse_args()
  serial_port = args.port[0]
  baud = args.baud[0]
  if args.stm and args.m25:
    parser.error("Only one of -s or -m options may be chosen")
    sys.exit(2)
  elif not args.stm and not args.m25:
    parser.error("One of -s or -m options must be chosen")
    sys.exit(2)
  if args.erase and not args.stm:
    parser.error("The -e option requires the -s option to also be chosen")
  ihx = IntelHex(args.file)

  # Create serial link with device
  print "Waiting for device to be plugged in ...",
  sys.stdout.flush()
  link = None
  while not link:
    try:
      link = serial_link.SerialLink(serial_port, baud=baud, use_ftdi=args.ftdi,
                                    print_unhandled = False)
    except KeyboardInterrupt:
      if link:
        link.close()
      sys.exit()
    except:
      time.sleep(0.01)
  print "link successfully created."

  # Reset device if the payload is running
  link.send_message(ids.RESET, '')

  # Tell Bootloader we want to change flash data
  piksi_bootloader = Bootloader(link)
  print "Waiting for bootloader handshake message from Piksi ...",
  sys.stdout.flush()
  try:
    piksi_bootloader.wait_for_handshake()
  except KeyboardInterrupt:
    # Clean up and exit
    link.close()
    sys.exit()
  piksi_bootloader.reply_handshake()
  print "received."
  print "Piksi Onboard Bootloader Version:", piksi_bootloader.version

  try:

    if args.stm:
      piksi_flash = flash.Flash(link, flash_type="STM")
    elif args.m25:
      piksi_flash = flash.Flash(link, flash_type="M25")

    if args.erase:
      for s in range(1,12):
        print "\rErasing STM Sector", s,
        sys.stdout.flush()
        piksi_flash.erase_sector(s)
      print

    piksi_flash.write_ihx(ihx, sys.stdout, mod_print = 0x10)

  except KeyboardInterrupt:
    print
    link.close()
    sys.exit()

  print "Bootloader jumping to application"
  piksi_bootloader.jump_to_app()

  piksi_flash.stop()
  piksi_bootloader.stop()

  # Clean up and exit
  link.close()
  sys.exit()

