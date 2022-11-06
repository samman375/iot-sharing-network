"""
    Usage: python3 server.py localhost 12000

    Adapted from example multi-threaded server code on course homepage

    By Sam Thorley (z5257239)
"""
from datetime import datetime
from socket import *
from threading import Thread, Lock
import sys, time, os, re

"""
    Data structs & Global variables
"""

blockedAccounts = set()
blockedAccountsLock = Lock()
devicesInfo = {}
nDevices = 0
nDevicesLock = Lock()

"""
    File names
"""

credentialsFileName = "credentials.txt"
edgeDeviceLogFileName = "edge-device-log.txt"
deletionLogFileName = "deletion-log.txt"
uploadLogFileName = "upload-log.txt"

"""
    Server setup
"""

# Acquire server port and max fail attempts from command line parameter
if len(sys.argv) != 3:
    print("\nError usage: python3 server.py SERVER_PORT NUM_CONSECUTIVE_FAIL_ATTEMPTS")
    exit(0)
serverHost = "127.0.0.1"
serverPort = int(sys.argv[1])
maxFailAttempts = int(sys.argv[2])
serverAddress = (serverHost, serverPort)

if maxFailAttempts < 1 or maxFailAttempts > 5:
    print(
        "\nError usage: NUM_CONSECUTIVE_FAIL_ATTEMPTS must be between 1 and 5 (inclusive)"
    )
    exit(0)

# Define socket for the server side and bind address
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(serverAddress)

# Remove existing log files if exist
if os.path.exists(edgeDeviceLogFileName):
    os.remove(edgeDeviceLogFileName)

if os.path.exists(deletionLogFileName):
    os.remove(deletionLogFileName)

"""
    Helper functions
"""

# Given a usernamelooks for it in credentials file
def usernameLookup(username):
    credsFile = open(credentialsFileName, "r")
    credsLines = credsFile.readlines()
    credsFile.close()
    for line in credsLines:
        lineUsername = line.split()[0]
        if username == lineUsername:
            return True
    return False


# Given a username and password looks for it in credentials file
def passwordLookup(username, password):
    credsFile = open(credentialsFileName, "r")
    credsLines = credsFile.readlines()
    credsFile.close()
    for line in credsLines:
        lineCreds = line.split()
        lineUsername = lineCreds[0]
        linePassword = lineCreds[1]
        if username == lineUsername:
            if password == linePassword:
                return True
            else:
                return False
    return False


# Given a username blocks that account for 10s
def blockAccount(username):
    blockedAccountsLock.acquire()
    blockedAccounts.add(username)
    blockedAccountsLock.release()

    time.sleep(10)

    blockedAccountsLock.acquire()
    blockedAccounts.remove(username)
    blockedAccountsLock.release()


# Given a username checks if that account is currently blocked
def checkBlocked(username):
    blockedAccountsLock.acquire()
    if username in blockedAccounts:
        blockedAccountsLock.release()
        return True
    else:
        blockedAccountsLock.release()
        return False


# Given a string writes it to the edge device log
def writeToEdgeDeviceLog(logString):
    edgeDeviceLogFile = open(edgeDeviceLogFileName, "a")
    edgeDeviceLogFile.write(logString)
    edgeDeviceLogFile.close()


# Writes edge device log based off data in devicesInfo object in order of seqNum
def createEdgeDeviceLog():
    # Remove existing log file if exists
    if os.path.exists(edgeDeviceLogFileName):
        os.remove(edgeDeviceLogFileName)

    # Create dictionary with seqNum as key and deviceName as value to be used in sort
    seqNums = {}
    for deviceName in devicesInfo:
        seqNums[devicesInfo[deviceName]["deviceSeqNum"]] = deviceName

    # Add devices to log sorted by seqNum
    for seqNum in sorted(seqNums.keys()):
        deviceObj = devicesInfo[seqNums[seqNum]]
        timestamp = deviceObj["timestamp"]
        username = seqNums[seqNum]
        deviceIPAddr = deviceObj["deviceIPAddr"]
        UDPPortNum = deviceObj["UDPPortNum"]

        logString = f"{seqNum}; {timestamp}; {username}; {deviceIPAddr}; {UDPPortNum}\n"
        writeToEdgeDeviceLog(logString)


# Add new device to network
# Intialises device information in global struct and add to log file
def addNewDevice(username, clientIPAddr):
    nDevicesLock.acquire()
    global nDevices
    nDevices += 1
    deviceSeqNum = nDevices
    nDevicesLock.release()

    timestamp = getFormattedDatetime(datetime.now())
    UDPPortNum = 0  # TODO

    # Add device to devices object
    deviceObj = {}
    deviceObj["timestamp"] = timestamp
    deviceObj["deviceSeqNum"] = deviceSeqNum
    deviceObj["deviceIPAddr"] = clientIPAddr
    deviceObj["UDPPortNum"] = UDPPortNum
    devicesInfo[username] = deviceObj

    # Update edge device log
    createEdgeDeviceLog()


# Remove device from network
def removeDevice(usernameToRemove):
    nDevicesLock.acquire()
    global nDevices
    nDevices -= 1
    nDevicesLock.release()

    seqNumToRemove = devicesInfo[usernameToRemove]["deviceSeqNum"]

    devicesInfo.pop(usernameToRemove)
    for deviceName in devicesInfo:
        if devicesInfo[deviceName]["deviceSeqNum"] > seqNumToRemove:
            # Shift device sequence numbers down by 1
            devicesInfo[deviceName]["deviceSeqNum"] -= 1

    # Recreate edge log file
    createEdgeDeviceLog()


# Given a datetime timestamp converts to format "DD Month YYYY HH:MM:SS"
def getFormattedDatetime(ts):
    return ts.strftime("%d %B %Y %H:%M:%S")


"""
    Define multi-thread class for client
    This class would be used to define the instance for each connection from each client
    For example, client-1 makes a connection request to the server, the server will call
    class (ClientThread) to define a thread for client-1, and when client-2 make a connection
    request to the server, the server will call class (ClientThread) again and create a thread
    for client-2. Each client will be runing in a separate therad, which is the multi-threading
"""


class ClientThread(Thread):
    def __init__(self, clientAddress, clientSocket):
        Thread.__init__(self)
        self.clientAddress = clientAddress
        self.clientSocket = clientSocket
        self.clientAlive = False
        self.authenticated = False
        self.username = ""

        print("===== New connection created for: ", self.clientAddress)
        self.clientAlive = True

    def run(self):
        message = ""

        while self.clientAlive:

            if not self.authenticated:
                self.promptLogin()

                # If still not authenticated user reached fail limit
                if not self.authenticated:
                    self.clientAlive = False
                    print("===== user killed - ", self.clientAddress)
                    break

            # Receive message from the client
            data = self.clientSocket.recv(1024)
            message = data.decode()

            # OUT command
            # Usage: OUT
            if message == "OUT":
                print(f"[{self.clientAddress}:recv] OUT")

                self.sendMessage("RC0;successfully disconnected")

                self.clientAlive = False
                self.authenticated = False

                # Remove device
                removeDevice(self.username)

                print("===== the user disconnected - ", self.clientAddress)
                break

            # AED command
            # Usage: AED
            elif message == "AED":
                print(f"[{self.clientAddress}:recv] AED")
                self.activeEdgeDevices()

            # EDG command
            # Usage: EDG fileID dataAmount
            elif re.match("^EDG.*", message):
                # Ensure correct number of arguments supplied
                args = message.split()
                if len(args) != 3:
                    self.sendMessage(
                        "RC1;EDG resp: \nEDG command requires fileID and dataAmount as arguments."
                    )
                else:
                    fileID = args[1]
                    dataAmount = args[2]
                    self.edgeDataGeneration(fileID, dataAmount)

            # DTE command
            # Usage: DTE fileID
            elif re.match("^DTE.*", message):
                # Ensure correct number of arguments supplied
                args = message.split()
                if len(args) != 2:
                    self.sendMessage(
                        "RC1;DTE resp: \nDTE command requires fileID as argument."
                    )
                else:
                    fileID = args[1]
                    self.deleteDataFile(fileID)

            # SCS command
            # Usage: SCS fileID compuationOperation
            # computationOperation must be one of [AVERAGE, MAX, MIN, SUM]
            elif re.match("^SCS.*", message):
                # Ensure correct number of arguments supplied
                args = message.split()
                if len(args) != 3:
                    self.sendMessage(
                        "RC1;SCS resp: \nSCS command requires fileID and computationOperation as arguments."
                    )
                else:
                    fileID = args[1]
                    compOp = args[2]
                    self.serverComputationService(fileID, compOp)

            # UED command
            # Usage: UED fileID
            elif re.match("^UED.*", message):
                # Error handling done on client side in this case
                args = message.split()
                fileID = args[1]

                # File data is everything after "UED {fileID}\n"
                # Remove everything before first '\n'
                fileData = message[(message.find("\n") + 1) :]

                self.uploadEdgeData(fileID, fileData)

            else:
                print(f"[{self.clientAddress}:recv] " + message)
                self.sendMessage("RC1;Cannot understand this message")

    # Given a message outputs to terminal and sends to client
    def sendMessage(self, message):
        message += "\r"
        print(f"[{clientAddress}:send] " + message)
        self.clientSocket.send(message.encode())

    """
        You can create more customized APIs here, e.g., logic for processing user authentication
        Each api can be used to handle one specific function
    """

    # Authenticate User
    def promptLogin(self):
        failedAttempts = 0
        validUsername = False
        usernameClaim = ""

        # Initial get username from client
        self.sendMessage("RC0;username authentication request")

        # Validate username
        while not validUsername:
            data = self.clientSocket.recv(1024)
            usernameClaim = data.decode()

            if usernameLookup(usernameClaim) and usernameClaim not in devicesInfo:
                if not checkBlocked(usernameClaim):
                    # Successful username
                    validUsername = True
                else:
                    # Valid credentials but account blocked
                    self.sendMessage("RC0;blocked account")
                    return
            elif usernameClaim in devicesInfo:
                # Username already logged in
                self.sendMessage("RC0;username already logged in")
            else:
                failedAttempts += 1
                if failedAttempts == maxFailAttempts:
                    # Max failed attempts reached. Block account
                    self.sendMessage("RC0;max failed attempts")
                    blockAccount(usernameClaim)
                    return

                # Re-request username
                self.sendMessage("RC0;retry username authentication request")

        # Initial get password from client
        self.sendMessage("RC0;password authentication request")

        # Validate password
        while True:
            data = self.clientSocket.recv(1024)
            passwordClaim = data.decode()

            if passwordLookup(usernameClaim, passwordClaim):
                if not checkBlocked(usernameClaim):
                    # Successful authentication
                    self.authenticated = True
                    self.username = usernameClaim
                    self.sendMessage("RC1;welcome")
                    addNewDevice(usernameClaim, self.clientAddress[0])
                    break
                else:
                    # Valid credentials but account blocked
                    self.sendMessage("RC0;blocked account")
                    break
            else:
                failedAttempts += 1
                if failedAttempts == maxFailAttempts:
                    # Max failed attempts reached. Block account
                    self.sendMessage("RC0;max failed attempts")
                    blockAccount(usernameClaim)
                    break

                # Re-request credentials
                self.sendMessage("RC0;retry password authentication request")

    # Return all other active edge devices and request new command
    def activeEdgeDevices(self):
        print(f"Edge device {self.username} issued AED command")
        message = "RC1;AED resp: "

        if len(devicesInfo.keys()) == 1:
            message += "\nno other active edge devices"
        else:
            for deviceName in devicesInfo:
                if deviceName == self.username:
                    continue
                else:
                    timestamp = devicesInfo[deviceName]["timestamp"]
                    ipAddr = devicesInfo[deviceName]["deviceIPAddr"][0]
                    udpPortNum = devicesInfo[deviceName]["UDPPortNum"]
                    message += f"\n{deviceName}, active since {timestamp}, IP address: {ipAddr}, UDP port number: {udpPortNum}"

        self.sendMessage(message)

    # Creates a new file counting from 1 to specified amount each on new line
    # File of format: USERNAME-FILEID.txt
    def edgeDataGeneration(self, fileID, dataAmount):
        message = "RC1;EDG resp: "

        try:
            # Check only integers supplied
            fileIDInt = int(fileID)
            dataAmountInt = int(dataAmount)

            dateFile = open(f"{self.username}-{fileID}.txt", "w")
            fileOutput = ""

            # Data generated always from 1 to specified amount
            for i in range(1, dataAmountInt + 1):
                fileOutput += f"{i}\n"

            # Write to file removing trailing new line
            dateFile.write(fileOutput[:-1])
            dateFile.close()

            message += "\nData generation done."
        except:
            # Error message for when non-integers supplied
            message += "\nThe fileID or dataAmount are not integers, you need to specify the parameter as integers."

        self.sendMessage(message)

    # Deletes requested file and logs operation if exists, else returns an error
    def deleteDataFile(self, fileID):
        message = "RC1;DTE resp: "
        requestedFileName = f"{self.username}-{fileID}.txt"
        # Return error if file does not exist on server side
        if not os.path.exists(requestedFileName):
            message += "\nSpecified file does not exist at the server side."
        else:
            # Calculate data amount of requested file
            requestedFile = open(requestedFileName, "r")
            dataAmount = len(requestedFile.readlines())
            requestedFile.close()

            os.remove(requestedFileName)

            # Append to deletion log
            deletionLogFile = open(deletionLogFileName, "a")
            timestamp = getFormattedDatetime(datetime.now())
            deletionLogFile.write(
                f"{self.username}; {timestamp}; {fileID}; {dataAmount}\n"
            )
            deletionLogFile.close()

            message += f"\nFile with ID of {fileID} has been successfully removed from the central server."

        self.sendMessage(message)

    # Given a fileID and a computationOperation executes requested operation on the file if valid
    def serverComputationService(self, fileID, compOp):
        message = "RC1;SCS resp: "
        requestedFileName = f"{self.username}-{fileID}.txt"

        # Allows case insensitive argument parsing
        upperCompOp = compOp.upper()

        if not os.path.exists(requestedFileName):
            message += "\nSpecified file does not exist at the server side."
        else:
            try:
                # Check only integer supplied for fileID
                fileIDInt = int(fileID)

                # Check valid operation requested
                if upperCompOp not in ["SUM", "AVERAGE", "MAX", "MIN"]:
                    message += "\nThe computationOperation must be one of [SUM, AVERAGE, MAX, MIN]."
                else:
                    requestedFile = open(requestedFileName, "r")
                    requestedFileLines = requestedFile.readlines()
                    requestedFile.close()

                    fileNums = []

                    for line in requestedFileLines:
                        try:
                            fileNums.append(int(line.strip()))
                        except:
                            # Skip line if not integer
                            continue

                    # Execute computation
                    if len(fileNums) == 0:
                        # Return Null if no numbers in file
                        message += "\nNull"
                    elif upperCompOp == "SUM":
                        message += f"\n{sum(fileNums)}"
                    elif upperCompOp == "AVERAGE":
                        message += f"\n{sum(fileNums)/len(fileNums)}"
                    elif upperCompOp == "MAX":
                        message += f"\n{max(fileNums)}"
                    elif upperCompOp == "MIN":
                        message += f"\n{min(fileNums)}"

            except:
                # Error message for when non-integer fileID supplied
                message += "\nThe fileID should be an integer."

        self.sendMessage(message)

    # Given a fileID and fileData creates that file, and logs action
    def uploadEdgeData(self, fileID, fileData):
        messageToSend = "RC1;UED resp: "
        receivedFileName = f"{self.username}-{fileID}.txt"

        # Output file onto server
        receivedFile = open(receivedFileName, "w+")
        receivedFile.write(fileData)

        # Add to upload log
        uploadLogFile = open(uploadLogFileName, "a")
        timestamp = getFormattedDatetime(datetime.now())
        dataAmount = len(receivedFile.readlines())
        uploadLogFile.write(f"{self.username}; {timestamp}; {fileID}; {dataAmount}\n")

        uploadLogFile.close()
        receivedFile.close()

        # Send success response back to client
        messageToSend += f"\nFile with ID {fileID} successfully received by server."
        self.sendMessage(messageToSend)

        # remove commented code from refactoring earlier on client side


print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")


while True:
    serverSocket.listen()
    clientSockt, clientAddress = serverSocket.accept()
    clientThread = ClientThread(clientAddress, clientSockt)
    clientThread.start()
