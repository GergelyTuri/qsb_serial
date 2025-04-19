from encodings import utf_8
import serial.tools.list_ports
import serial
import time
import os
import sys
import waitforkey as waitforkey

def send_qsb_command(device, command):
    if command[-1] != '\n':
        command += "\n"
        
    return device.write(command.encode('ascii')) > 0
       
def read_qsb_response(device):    
    return (device.read_until(size=21))    

def process_qsb_command(device, command):
    if send_qsb_command(device, command):
        parse_qsb_response(read_qsb_response(device))
    
def parse_qsb_response(response_bytes):
    if len(response_bytes) >= 21:        
        try:            
            response = response_bytes.decode('ascii').rstrip()  
            cmdType = response[0]    
            if 'rws'.find(cmdType) > -1 and response[-1] == '!' :

                cmd = 'Read' if cmdType == 'r' else 'Wrote' if cmdType == 'w' else 'Stream'
                register = response[1:3] 
                data = int(response[3:11],16)
                timestamp = int(response[11:19],16) * 1.95
                print(f'{cmd} register = {register}, Data = {data}, TimeStamp = {round(timestamp,2)}')
                if cmdType == 'r' and register == '14':
                    # parse the serial number, device type, and version
                    serialNo = int(response[3:8],16)
                    devType = int(response[8:9], 16)
                    devTypeStr = 'DeviceType'
                    if devType == 0:
                        devTypeStr = 'QSB-D'
                    elif devType == 1:
                        devTypeStr = 'QSB-M'
                    elif devType == 2:
                        devTypeStr = 'QSB-S'
                    else: 
                        devTypeStr = 'QSB-I'
                    fwVersion = int(response[9:11],16)
                    print(f'\tDevice Type: {devTypeStr}\n\tSerial Number: {serialNo}\n\tFirmware Version: {fwVersion}')
            else:
                print(f'Read Error: {response}', end='\r\n', flush=True)
        except Exception as ex:
            print(f'Parse exeption: {response}\r\n{ex}')

def display_qsb_count_response(response_bytes):
    if len(response_bytes) >= 21:
        try:
            response = response_bytes.decode('ascii').rstrip()
            cmdType = response[0]
            if 'rs'.find(cmdType) and response[-1] == '!' :
                data = int(response[3:11],16)
                timestamp = int(response[11:19],16) * 1.95
                print(f'Count = {data}, TimeStamp = {round(timestamp,2)}   ', end='\r', flush=True)
            else:
                print(f'Read Error: {response}', end='\r\n', flush=True)
        except Exception as ex:
            print(f'Parse exeption: {response}\r\n{ex.__cause__}')

    
serialPort = 'COM7'

if (len(sys.argv) > 1):
    serialPort = sys.argv[1]
else:
    all_comports = serial.tools.list_ports.comports()
    all_comports.sort()
    num = 0
    ports = [] 
    for comport in all_comports:
        ports.append(comport.device)
    
    if len(ports) == 1:
        serialPort = ports[0]
    else:
        print ('Missing port parameter')
        print ('syntax: streamQSB.py port')
        print (f'Available ports: {", ".join(ports)}')    
        exit(0)

# Create a serial object for the QSB encoder
serEncoder = serial.Serial(
    port=serialPort, 
    baudrate=230400,
    bytesize=serial.EIGHTBITS, # 8 data bits
    parity=serial.PARITY_NONE, # no parity
    stopbits=serial.STOPBITS_ONE, # 1 stop b
    timeout=1    
    )

try:
    # Check if the port is already open
    if not serEncoder.is_open:
        # Open the serial port
        serEncoder.open()        
    
    # Allow time for communications to stabilize
    time.sleep(2)       
    
    print("*************************************************************");
    print("                      streamQSB.c Demo");
    print("Refer to the QSB Commands List.pdf for register descriptions.");
    print("*************************************************************");
    
    # The QSB may already be streaming data.    
    # Tell the QSB to stop all streaming.
    send_qsb_command(serEncoder, "W161")

    # Clear out the serial port input buffer.
    serEncoder.readlines()

    print('Configuring the QSB...')
    
    # Configure the QSB response format to include a line feed and a time stamp
    # This is done to ensure we get the command response length we look for in the 
    # rest of the commands.
    process_qsb_command(serEncoder, 'W155')
    
    # Read the serial number, product type, and firmware version number.
    process_qsb_command(serEncoder, "R14")   

    # Set the encoder mode to quadrature
    process_qsb_command(serEncoder, 'W000')
    
    # Set the quadrature mode: X4, modulo-N, index disabled
    process_qsb_command(serEncoder, 'W03F')
    
    # Set the counter mode: Enabled, Non-invert, No-triggers
    process_qsb_command(serEncoder, 'W040')

    # Set the maximum count (Preset) to decimal 499
    process_qsb_command(serEncoder, "W081F3")

    # Reset the counter to zero
    process_qsb_command(serEncoder, 'W092')

    # Set the threshold register to 0
    process_qsb_command(serEncoder, 'W0B0')
    
    # Set the interval rate register to zero for the fastest rate possible 
    process_qsb_command(serEncoder, 'W0C0')

    # Reset the timestamp
    process_qsb_command(serEncoder, 'W0D1')

    # Begin streaming the encoder count register 
    process_qsb_command(serEncoder, 'S0E')

    kb = waitforkey.KBHit()
    print("\nPress ESC to stop streaming and exit")

    # loop until a ESC is pressed.
    while True:
        if kb.kbhit():
            c = kb.getch()
            if ord(c) == 27: # ESC
                break
        
        display_qsb_count_response(read_qsb_response(serEncoder))

    print ("\n\nStreaming stopped.")

    # Reading the encoder count register will stop streaming encoder counts
    process_qsb_command(serEncoder, 'R0E')
    print ("All Done.")
       
except serial.SerialException as se:
    print(f"SerialException: {se}")
    if serEncoder.is_open:
        serEncoder.close()
