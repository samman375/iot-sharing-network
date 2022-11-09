"""
    Usage: python3 client.py localhost 12000 100

    Adapted from example multi-threaded client code on course homepage

    By Sam Thorley (z5257239)
"""
from socket import *
from threading import Thread
import sys, re, os, math, time


if len(sys.argv) != 4:
    print(
        "\n===== Error usage, python3 client.py SERVER_IP SERVER_PORT CLIENT_UDP_SERVER_PORT ======\n"
    )
    exit(0)
serverHost = sys.argv[1]
serverPort = int(sys.argv[2])
clientUDPServerPort = int(sys.argv[3])
serverAddress = (serverHost, serverPort)

if clientUDPServerPort < 1024 or clientUDPServerPort > 65535:
    print("Error: Invalid CLIENT_UDP_SERVER_PORT. Must be in range [1024, 65535].")
    exit(0)

username = ""

# define a TCP and UDP socket for the client side, it would be used to communicate with the server
clientSocket = socket(AF_INET, SOCK_STREAM)
clientUDPSocket = socket(AF_INET, SOCK_DGRAM)

# build connection with the server and send message to it
clientSocket.connect(serverAddress)
clientUDPSocket.bind(("", clientUDPServerPort))

# Allow UDP Thread to be killed with the TCP one exits
clientUDPSocket.settimeout(0)
killUDPThread = False


class UDPThread(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        while not killUDPThread:
            # Non-blocking recvfrom() to allow thread to be killed
            try:
                # Receive header message from another client
                data, recvAddress = clientUDPSocket.recvfrom(4096)
            except:
                continue

            message = data.decode("utf-8")

            # Very simple error checking
            if message[0:3] != "UVF" or message.split() != 4:
                print(f"Corrupted UVF file from {recvAddress} received.")
            else:
                message = message.split()
                fileName = message[1]
                nPacketsToRecv = message[2]
                senderDevice = message[3]

                outFile = open(fileName, "ab")

                # Receive and write each packet to file
                for i in range(0, nPacketsToRecv):
                    data, recvAddress = clientUDPSocket.recvfrom(4096)
                    outFile.write(data)

                outFile.close()

                print(f"File {fileName} received from {senderDevice}")


# Main interaction thread
class TCPThread(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        while True:
            # receive response from the server
            data = clientSocket.recv(1024)
            receivedMessage = data.decode()

            # RC bit header used to track if standard command is required after response received
            # Standard command is one of [EDG, UED, SCS, DTE, AED, OUT]
            # RC1 = command required, RC0 = other (eg. username or password request)
            commandRequested = False

            if re.match("^RC1;.*", receivedMessage):
                commandRequested = True

            # Remove RC header
            receivedMessage = receivedMessage[4:]

            # Error checking for empty response
            if receivedMessage.strip() == "" or receivedMessage.strip() == "\r":
                print("[recv] Message from server is empty!")

            ### Auth related:

            # Get and send username
            elif (
                receivedMessage == "username authentication request\r"
                or receivedMessage == "retry username authentication request\r"
            ):
                if receivedMessage == "retry username authentication request\r":
                    print("Invalid Username. Please try again.")
                message = input("Username: ").strip()
                username = message
                # UDP Server Port sent with username
                message += f" {clientUDPServerPort}"
                clientSocket.send(message.encode())

            # Get and send password
            elif (
                receivedMessage == "password authentication request\r"
                or receivedMessage == "retry password authentication request\r"
            ):
                if receivedMessage == "retry password authentication request\r":
                    print("Invalid Password. Please try again.")
                message = input("Password: ").strip()
                clientSocket.send(message.encode())

            # Max failed auth attempts. Account blocked.
            elif receivedMessage == "max failed attempts\r":
                print(
                    "Invalid Password. Your account has been blocked for 10s. Please try again later"
                )
                break

            # Attempt to login to blocked account
            elif receivedMessage == "blocked account\r":
                print(
                    "Your account is blocked due to multiple authentication failures. Please try again later"
                )
                break
            elif receivedMessage == "username already logged in\r":
                print("This username is already logged in. Try another.")
                message = input("Username: ").strip()
                username = message
                clientSocket.send(message.encode())

            # Disconnect
            elif receivedMessage == "successfully disconnected\r":
                # Kill UDP listening thread
                global killUDPThread
                killUDPThread = True
                print("Successfully logged out. Goodbye!")
                break

            ### Commands:

            # Get command
            elif (
                receivedMessage == "welcome\r" or receivedMessage == "command request\r"
            ):
                if receivedMessage == "welcome\r":
                    print("Welcome!")

            # AED
            elif re.match("^AED resp: \n.*", receivedMessage):
                # Remove header
                resp = re.sub("^AED resp: \n", "", receivedMessage)
                print(resp)

            # EDG
            elif re.match("^EDG resp: \n.*", receivedMessage):
                resp = re.sub("^EDG resp: \n", "", receivedMessage)
                print(resp)

            # DTE
            elif re.match("^DTE resp: \n.*", receivedMessage):
                resp = re.sub("^DTE resp: \n", "", receivedMessage)
                print(resp)

            # SCS
            elif re.match("^SCS resp: \n.*", receivedMessage):
                resp = re.sub("^SCS resp: \n", "", receivedMessage)
                print(resp)

            # UED
            elif re.match("^UED resp: \n.*", receivedMessage):
                resp = re.sub("^UED resp: \n", "", receivedMessage)
                print(resp)

            ### Misc:
            else:
                print(f"Error: Unknown server response received - {receivedMessage}")

            # If RC header was set to 1
            if commandRequested:
                # Keep requesting a command unless valid one given
                validInput = False
                while not validInput:
                    message = input(
                        "Enter one of the following commands (EDG, UED, SCS, DTE, AED, OUT, UVF): "
                    ).strip()

                    # Check valid command
                    if message[0:3] not in [
                        "EDG",
                        "UED",
                        "SCS",
                        "DTE",
                        "AED",
                        "OUT",
                        "UVF",
                    ]:
                        print("Invalid command.")

                    # UED command
                    elif message[0:3] == "UED":
                        # Check args provided
                        args = message.split()
                        if len(args) != 2:
                            print("A fileID is needed to upload data.")
                        elif not os.path.exists(f"{username}-{args[1]}.txt"):
                            print("The file to be uploaded does not exist.")
                        else:
                            validInput = True

                            requestedFileName = f"{username}-{args[1]}.txt"
                            requestedFile = open(requestedFileName, "r")

                            # Add all data from file into message on new line after header
                            message += "\n"
                            for line in requestedFile.readlines():
                                message += line

                            clientSocket.send(message.encode())

                    elif message[0:3] == "UVF":
                        # Check args provided
                        args = message.split()
                        if len(args) != 3:
                            print(
                                "A deviceName and fileName are required to send file."
                            )
                        elif not os.path.exists(args[2]):
                            print("The file to be sent does not exist.")
                        else:
                            # Check device is active via AED + get port and address
                            deviceName = args[1]
                            fileName = args[2]
                            deviceDetails = self.getDeviceDetails(deviceName)
                            if deviceDetails == None:
                                print(f"{deviceName} is offline.")
                            else:
                                # address, port = deviceDetails
                                packetSize = 4096

                                # Calculate number of packets
                                fileSize = os.path.getsize(fileName)
                                nPackets = math.ceil(fileSize / packetSize)

                                # Create and send header
                                message = f"UVF {fileName} {nPackets} {username}"
                                clientUDPSocket.sendto(
                                    bytes(message, encoding="utf-8"), deviceDetails
                                )

                                # Break file into packets reading 4096 bytes at a time and send
                                # Adapted from: https://stackoverflow.com/questions/6787233/python-how-to-read-bytes-from-file-and-save-it
                                byteFile = open(fileName, "rb")
                                while True:
                                    packet = byteFile.read(packetSize)

                                    # Break on empty packet
                                    if packet == b"":
                                        break

                                    time.sleep(1)
                                    clientUDPSocket.sendto(packet, deviceDetails)

                                print(f"{fileName} sent to {deviceName}.")
                    else:
                        validInput = True
                        clientSocket.send(message.encode())

    # Given a deviceName, checks it is active and gets address and port via AED command
    # Return None if device not found, otherwise a tuple with address and port
    def getDeviceDetails(self, deviceName):
        # Send and receive AED command
        clientSocket.send("AED".encode())
        data = clientSocket.recv(1024)
        receivedAED = data.decode()

        # Extract information from AED output
        # Example AED ouput:
        # test2, active since 09 November 2022 14:18:07, IP address: 1, UDP port number: 0
        devicesInfo = receivedAED.split("\n")
        # Remove header line
        devicesInfo = devicesInfo[1:]
        if devicesInfo[0] == "no other active edge devices":
            return None
        else:
            for device in devicesInfo:
                deviceInfo = device.split()
                name = deviceInfo[0][:-1]
                if name != deviceName:
                    continue
                address = deviceInfo[9][:-1]
                port = int(deviceInfo[13])
                return (address, port)
        return None


udpThread = UDPThread()
tcpThread = TCPThread()
udpThread.start()
tcpThread.start()

# Create the 2 threads
while tcpThread.is_alive() and udpThread.is_alive():
    continue

# close the sockets
# clientSocket.close()
# clientUDPSocket.close()
