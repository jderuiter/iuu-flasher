import argparse
import usb.core
import sys
from math import ceil
from intelhex import IntelHex16bit

parser = argparse.ArgumentParser(description='Dump/flash ATMega Card using Infinity USB Unlimited.')
parser.add_argument('--action', '-a', choices=['dump', 'flash'], nargs=1, required=True)
parser.add_argument('--format', '-f', choices=['hex', 'bin'], default=["hex"], nargs=1)
parser.add_argument('--verbose', '-v', default=False, action='store_true')
parser.add_argument('filename', nargs=1)

def send_data(data, wait=True):
	exception = None
        result = []

	if verbose:        
                print "Command:\n\t",
                for (d,c) in enumerate(data):
                        print "%#04x" % c,
                for (d,c) in enumerate(data):
                        print "%1s" % chr(c),
                print ""

        dev.write(ep_out.bEndpointAddress, data, intf.bInterfaceNumber, 50)

	if not wait:
		return result

	received = False

	if verbose:
                print "Response:"
	for x in range(0, 10):
		try:
			resp = dev.read(ep_in.bEndpointAddress, 4096, intf.bInterfaceNumber, 50)
                        result.extend(resp)
			received = True

                        if verbose:
                                print "\t",
                                for c in resp:
                                        print "%#04x" % c,
                                print ""
		except Exception as e:
			if received:
				exception = e
				break
			else:
				exception = e

	if verbose and not received:
		print "\tNothing received", exception

        return result

# Parse commandline arguments
args = parser.parse_args()

action = args.action
verbose = args.verbose
filename = args.filename[0]
fileformat = args.format[0]

# Connect device
# Infinity USB unlimited
dev = usb.core.find(idVendor=0x104f, idProduct=0x0004)

if dev is None:
    print "No Infinity USB Unlimited connected"
    exit(-1)

print "Infinity USB Unlimited found"

# Initialisation
dev.set_configuration()
cfg = dev.get_active_configuration()
intf = cfg[(0,0)]

ep_in = usb.util.find_descriptor(intf, custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
ep_out = usb.util.find_descriptor(intf, custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)

print "Initialising IUU"
dev.ctrl_transfer(0x40, 0x02, 0x0002, 0)

# Reset AVR
# Added in case the device is still stuck in AVR mode
send_data([0x24], False)

# Set LED to green
send_data([0x04, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0xFF], False)

send_data([0x03])

# Get product name
name = send_data([0x02])
print "Product name: ",
print "".join(map(chr, name))

# Get firmware version
firmware = send_data([0x01])
print "Firmware version: ",
print "".join(map(chr, firmware))

if verbose:
        print "Get status"
status = send_data([0x03])
if status <> [0x01]:
        print "No card inserted"
        send_data([0x03])
        # Set LED to blue
        send_data([0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x50, 0xFF], False)
        exit(-1)

if verbose:
        print "Enable AVR"
send_data([0x21], False)

if verbose:
        print "Set programming mode"
send_data([0x20,0xAC,0x53,0x00,0x00])

if verbose:
        print "Get signature"
signature = send_data([0x1F,0x30,0x00,0x00,0x1F,0x30,0x00,0x01,0x1F,0x30,0x00,0x02])

if signature <> [0x1E, 0x94, 0x02]:
        print "Invalid card signature (not an ATMega163?)"

        # Set LED to blue
        send_data([0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x50, 0xFF], False)

        exit(-1)

# Set LED to red
send_data([0x04, 0x00, 0x50, 0x00, 0x00, 0x00, 0x00, 0xE0], False)

page_size = 0x40
page_size_bytes = page_size * 2

if action == ["dump"]:
        ih = IntelHex16bit()
        
        # Dump data
        if verbose:
                print "Reset PC"
        send_data([0x25, 0x07, 0x0F], False)

        data = []

        print "Read data ...",

        for i in range(0, 32):
                print i, "...",
                sys.stdout.flush()

                page = send_data([0x2A, 0xFF])

                # Change data to big endian
                for j in range(0, len(page), 2):
                        data.extend([page[j + 1], page[j]])
                
        print "32", "...",
        sys.stdout.flush()

        page = send_data([0x2A, 0x20])

        # Change to big endian
        for j in range(0, len(page), 2):
                data.extend([page[j + 1], page[j]])

        ih.frombytes(data)
        ih.tofile(filename, fileformat)

        print "done"


if action == ["flash"]:
        ih = IntelHex16bit()
        ih.loadfile(filename, fileformat)

        print "Erasing flash and EEPROM"
        send_data([0x1E, 0xAC, 0x80, 0x00, 0x00], False)

        if verbose:
                print "Set programming mode"
        send_data([0x20,0xAC,0x53,0x00,0x00])

        #TODO Is reset PC needed? 
        if verbose:
                print "Reset PC"
        send_data([0x25], False)

        nr_pages = int(ceil(len(ih) / page_size_bytes))

        print "Writing data ...",
        for i in range(0, nr_pages):
                command = [0x2E, 0x00, 0x40]

                page = ih.tobinarray(start = i * page_size, size = page_size)
                
                # Change data to big endian
                for v in page:
                        command.extend([v >> 8, v & 0xFF])
                
                command.extend([0x03])

                print i, '...',
                sys.stdout.flush()
                send_data(command)

        # Reset PC
        if verbose:
                print "Reset PC"
        send_data([0x25, 0x03])

        # Write fuses and lock bits
        if verbose:
                print "Writing fuses and lock bits"
        send_data([0x1E, 0xAC, 0xA0, 0x00, 0xF0, 0x06, 0x02, 0x1E, 0xAC, 0xA8, 0x00, 0xFF, 0x06, 0x02], False)
        send_data([0x1E, 0xAC, 0xFF, 0xFF, 0xFF, 0x06, 0x0A], False)
        
        print "done" 

if verbose:
        print "Disable AVR"
send_data([0x22], False)

if verbose:
        print "Get status"
send_data([0x03])

# Set LED to blue
send_data([0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x50, 0xFF], False)

