"""
    Usage: python3 server.py localhost 12000

    Adapted from example multi-threaded server code on course homepage

    By Sam Thorley (z5257239)
"""
from datetime import datetime
from socket import *
from threading import Thread, Lock
import sys, select, time, os, re

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
    print("\nError usage: NUM_CONSECUTIVE_FAIL_ATTEMPTS must be between 1 and 5 (inclusive)")
    exit(0)

# Define socket for the server side and bind address
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(serverAddress)

# Remove existing log file if exists
if os.path.exists(edgeDeviceLogFileName):
    os.remove(edgeDeviceLogFileName)

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

    logFile = open(edgeDeviceLogFileName, "a")
    
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
    UDPPortNum = 0                                      # TODO
    
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
        self.username = ''
        
        print("===== New connection created for: ", self.clientAddress)
        self.clientAlive = True
        
    def run(self):
        message = ''
        
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
            if message == 'OUT':
                print(f"[{self.clientAddress}:recv] OUT")
                
                self.sendMessage('successfully disconnected')

                self.clientAlive = False
                self.authenticated = False

                # Remove device
                removeDevice(self.username)

                print("===== the user disconnected - ", self.clientAddress)
                break
            
            # AED command
            elif message == 'AED':
                print(f"[{self.clientAddress}:recv] AED")
                self.activeEdgeDevices()
            
            # EDG command
            elif re.match("^EDG.*", message):
                # Ensure correct number of arguments supplied
                args = message.split()
                if len(args) != 3:
                    self.sendMessage("EDG resp: \nEDG command requires fileID and dataAmount as arguments.")
                    self.sendMessage("command request")
                else:
                    fileID = args[1]
                    dataAmount = args[2]
                    self.edgeDataGeneration(fileID, dataAmount)
            
            elif message == 'login':
                print(f"[{self.clientAddress}:recv] New login request")
                self.promptLogin()
            
            elif message == 'download':
                print(f"[{self.clientAddress}:recv] Download request")
                self.sendMessage('download filename')
            
            else:
                print(f"[{self.clientAddress}:recv] " + message)
                self.sendMessage('Cannot understand this message')
    
    # Given a message outputs to terminal and sends to client
    def sendMessage(self, message):
        message += '\r'
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
        self.sendMessage('username authentication request')

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
                    self.sendMessage("blocked account")
                    return
            elif usernameClaim in devicesInfo:
                # Username already logged in
                self.sendMessage("username already logged in")
            else:
                failedAttempts += 1
                if failedAttempts == maxFailAttempts:
                    # Max failed attempts reached. Block account
                    self.sendMessage("max failed attempts")
                    blockAccount(usernameClaim)
                    return

                # Re-request username
                self.sendMessage('retry username authentication request')

        # Initial get password from client
        self.sendMessage('password authentication request')

        # Validate password
        while True:
            data = self.clientSocket.recv(1024)
            passwordClaim = data.decode()
            
            if passwordLookup(usernameClaim, passwordClaim):
                if not checkBlocked(usernameClaim):
                    # Successful authentication
                    self.authenticated = True
                    self.username = usernameClaim
                    self.sendMessage("welcome")
                    addNewDevice(usernameClaim, self.clientAddress[0])
                    break
                else:
                    # Valid credentials but account blocked
                    self.sendMessage("blocked account")
                    break
            else:
                failedAttempts += 1
                if failedAttempts == maxFailAttempts:
                    # Max failed attempts reached. Block account
                    self.sendMessage("max failed attempts")
                    blockAccount(usernameClaim)
                    break

                # Re-request credentials
                self.sendMessage('retry password authentication request')
    
    # Return all other active edge devices and request new command
    def activeEdgeDevices(self):
        print(f"Edge device {self.username} issued AED command")
        message = "AED resp: "
        
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
        self.sendMessage("command request")
    
    # Creates a new file counting from 1 to specified amount each on new line
    # File of format: USERNAME-FILEID.txt
    def edgeDataGeneration(self, fileID, dataAmount):
        message = "EDG resp: "
        
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

            message += "\nData generation done."
            self.sendMessage(message)
            self.sendMessage("command request")
        except:
            # Error message for when non-integers supplied
            message += "\nThe fileID or dataAmount are not integers, you need to specify the parameter as integers."
            self.sendMessage(message)
            self.sendMessage("command request")


print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")


while True:
    serverSocket.listen()
    clientSockt, clientAddress = serverSocket.accept()
    clientThread = ClientThread(clientAddress, clientSockt)
    clientThread.start()