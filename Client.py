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

# Ensure provided UDP port is in valid range
if clientUDPServerPort < 1024 or clientUDPServerPort > 65535:
    print("Error: Invalid CLIENT_UDP_SERVER_PORT. Must be in range [1024, 65535].")
    exit(0)

# Define a TCP and UDP socket for the client side
clientTCPSocket = socket(AF_INET, SOCK_STREAM)
clientUDPSocket = socket(AF_INET, SOCK_DGRAM)

# Build connection with the server and send message to it
clientTCPSocket.connect(serverAddress)
clientUDPSocket.bind(("", clientUDPServerPort))

# Allow listener thread to be killed when the interactive one dies
clientUDPSocket.settimeout(0)
killUDPThread = False

username = ""

# Constantly running daemon thread to allow UDP contact from another client for UVF command
# Initialised at startup and killed when 'OUT' command run via the interactive thread
class ListenerThread(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        while not killUDPThread:
            # Non-blocking recvfrom() to allow thread to be killed
            try:
                # Receive header message from other client
                data, recvAddress = clientUDPSocket.recvfrom(4096)
            except:
                continue

            # 'latin-1' encoding used as 'utf-8' fails for some reason
            message = data.decode("latin-1")

            if message[0:3] != "UVF":
                print(f"\nCorrupted UVF file from {recvAddress} received.")
            else:
                # Extract information from header
                message = message.split()
                fileName = message[1]
                nPacketsToRecv = int(message[2])
                senderDevice = message[3]

                outFile = open(fileName, "ab")

                # Temporarily remove socket non-blocking for file transfer
                clientUDPSocket.settimeout(5)

                # Receive and write each packet to file
                for i in range(0, nPacketsToRecv):
                    data, recvAddress = clientUDPSocket.recvfrom(4096)
                    outFile.write(data)

                outFile.close()
                print(f"\nFile {fileName} received from {senderDevice}")

            # Reinstate socket non-blocking
            clientUDPSocket.settimeout(0)


# Main thread to allow interaction for a user
class InteractiveThread(Thread):
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        while True:
            # Receive response from the server
            data = clientTCPSocket.recv(1024)
            receivedMessage = data.decode()

            # RC bit header used to track if a standard command is required after response received
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

            ### Auth related responses:

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
                clientTCPSocket.send(message.encode())

            # Get and send password
            elif (
                receivedMessage == "password authentication request\r"
                or receivedMessage == "retry password authentication request\r"
            ):
                if receivedMessage == "retry password authentication request\r":
                    print("Invalid Password. Please try again.")
                message = input("Password: ").strip()
                clientTCPSocket.send(message.encode())

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
                clientTCPSocket.send(message.encode())

            # Disconnect
            elif receivedMessage == "successfully disconnected\r":
                # Kill UDP listening thread
                global killUDPThread
                killUDPThread = True
                print("Successfully logged out. Goodbye!")
                break

            ### Command-related responses:

            # Get command
            elif (
                receivedMessage == "welcome\r"
                or receivedMessage == "command request\r"
                or receivedMessage == "Cannot understand this message\r"
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
                # Keep prompting a command from user unless valid one given
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

                            clientTCPSocket.send(message.encode())

                    # UVF command
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
                                packetSize = 4096

                                # Calculate number of packets
                                fileSize = os.path.getsize(fileName)
                                nPackets = math.ceil(fileSize / packetSize)

                                # Create and send header
                                message = f"UVF {fileName} {nPackets} {username}"
                                clientUDPSocket.sendto(
                                    message.encode("latin-1"), deviceDetails
                                )

                                # Break file into packets reading 4096 bytes at a time and send
                                # Adapted from: https://stackoverflow.com/questions/6787233/python-how-to-read-bytes-from-file-and-save-it
                                byteFile = open(fileName, "rb")
                                sentPackets = 0
                                while True:
                                    packet = byteFile.read(packetSize)
                                    sentPackets += 1

                                    # Exit loop on empty packet
                                    if packet == b"":
                                        break

                                    time.sleep(0.25)
                                    print(
                                        f"Sending packet {sentPackets}/{nPackets} ({math.floor(100 * sentPackets/nPackets)}%)"
                                    )
                                    clientUDPSocket.sendto(packet, deviceDetails)

                                byteFile.close()
                                print(f"{fileName} successfully sent to {deviceName}.")
                    else:
                        validInput = True
                        clientTCPSocket.send(message.encode())

    # Given a deviceName, checks it is active and gets address and port via AED command
    # Return None if device not found, otherwise a tuple with address and port
    def getDeviceDetails(self, deviceName):
        # Send and receive AED command
        clientTCPSocket.send("AED".encode())
        data = clientTCPSocket.recv(1024)
        receivedAED = data.decode()

        # Extract information from AED output
        # Example AED ouput:
        # 'test2, active since 09 November 2022 14:18:07, IP address: 1, UDP port number: 0'
        devicesInfo = receivedAED.split("\n")

        # Remove header line
        devicesInfo = devicesInfo[1:]

        # Scrape required information
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


# Create the main and listener threads
listenerThread = ListenerThread()
intThread = InteractiveThread()
listenerThread.start()
intThread.start()

# Close the sockets after threads are killed
while intThread.is_alive() and listenerThread.is_alive():
    continue

clientTCPSocket.close()
clientUDPSocket.close()
