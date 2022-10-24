"""
    Usage: python3 server.py localhost 12000

    Adapted from example multi-threaded server code on course homepage
"""
from socket import *
from threading import Thread
import sys, select, time

# Acquire server port and max fail attempts from command line parameter
if len(sys.argv) != 3:
    print("\nError usage: python3 server.py SERVER_PORT, NUM_CONSECUTIVE_FAIL_ATTEMPTS")
    exit(0)
serverHost = "127.0.0.1"
serverPort = int(sys.argv[1])
maxFailAttempts = int(sys.argv[2])
serverAddress = (serverHost, serverPort)

if maxFailAttempts < 1 or maxFailAttempts > 5:
    print("\nError usage: NUM_CONSECUTIVE_FAIL_ATTEMPTS must be between 1 and 5 (inclusive)")
    exit(0)

# define socket for the server side and bind address
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(serverAddress)

"""
    Data structs
"""

blockedAccounts = []


"""
    Helper functions
"""

# Given a usernamelooks for it in credentials file
def usernameLookup(username):
    credsFile = open("credentials.txt", "r")
    credsLines = credsFile.readlines()
    credsFile.close()
    for line in credsLines:
        lineUsername = line.split()[0]
        if username == lineUsername:
            return True
    return False

# Given a username and password looks for it in credentials file
def passwordLookup(username, password):
    credsFile = open("credentials.txt", "r")
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

def blockAccount(username):
    blockedAccounts.append(username)
    time.sleep(10)
    blockedAccounts.remove(username)

def checkBlocked(username):
    if username in blockedAccounts:
        return True
    else:
        return False

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
        
        print("===== New connection created for: ", clientAddress)
        self.clientAlive = True
        
    def run(self):
        message = ''
        
        while self.clientAlive:
            
            if not self.authenticated:
                self.promptLogin()

                # If still not authenticated user reached fail limit
                if not self.authenticated:
                    self.clientAlive = False
                    print("===== user killed - ", clientAddress)
                    break
            
            # use recv() to receive message from the client
            data = self.clientSocket.recv(1024)
            message = data.decode()
            
            # if the message from client is empty, the client would be off-line then set the client as offline (alive=Flase)
            if message == 'exit':
                self.clientAlive = False
                self.authenticated = False
                print("===== the user disconnected - ", clientAddress)
                break
            
            # handle message from the client
            if message == 'login':
                print(f"[{clientAddress}:recv] New login request")
                self.promptLogin()
            elif message == 'download':
                print(f"[{clientAddress}:recv] Download request")
                message = 'download filename'
                print(f"[{clientAddress}:send] " + message)
                self.clientSocket.send(message.encode())
            else:
                print(f"[{clientAddress}:recv] " + message)
                print(f"[{clientAddress}:send] Cannot understand this message")
                message = 'Cannot understand this message'
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
        message = 'username authentication request'
        print(f'[{clientAddress}:send] ' + message)
        self.clientSocket.send(message.encode())

        # Validate username
        while not validUsername:
            data = self.clientSocket.recv(1024)
            usernameClaim = data.decode()
            
            if usernameLookup(usernameClaim):
                if not checkBlocked(usernameClaim):
                    # Successful authentication
                    validUsername = True
                else:
                    # Valid credentials but account blocked
                    message = "blocked account"
                    print(f'[{clientAddress}:send] ' + message)
                    self.clientSocket.send(message.encode())
                    break
            else:
                failedAttempts += 1
                if failedAttempts == maxFailAttempts:
                    # Max failed attempts reached. Block account
                    message = "max failed attempts"
                    print(f'[{clientAddress}:send] ' + message)
                    self.clientSocket.send(message.encode())
                    blockAccount()
                    break

                # Re-request username
                message = 'retry username authentication request'
                print(f'[{clientAddress}:send] ' + message)
                self.clientSocket.send(message.encode())

        # Initial get password from client
        message = 'password authentication request'
        print(f'[{clientAddress}:send] ' + message)
        self.clientSocket.send(message.encode())

        # Validate password
        while True:
            data = self.clientSocket.recv(1024)
            passwordClaim = data.decode()
            
            if passwordLookup(usernameClaim, passwordClaim):
                if not checkBlocked(usernameClaim):
                    # Successful authentication
                    self.authenticated = True
                    message = "welcome"
                    print(f'[{clientAddress}:send] ' + message)
                    self.clientSocket.send(message.encode())
                    break
                else:
                    # Valid credentials but account blocked
                    message = "blocked account"
                    print(f'[{clientAddress}:send] ' + message)
                    self.clientSocket.send(message.encode())
                    break
            else:
                failedAttempts += 1
                if failedAttempts == maxFailAttempts:
                    # Max failed attempts reached. Block account
                    message = "max failed attempts"
                    print(f'[{clientAddress}:send] ' + message)
                    self.clientSocket.send(message.encode())
                    blockAccount()
                    break

                # Re-request credentials
                message = 'retry password authentication request'
                print(f'[{clientAddress}:send] ' + message)
                self.clientSocket.send(message.encode())


print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")


while True:
    serverSocket.listen()
    clientSockt, clientAddress = serverSocket.accept()
    clientThread = ClientThread(clientAddress, clientSockt)
    clientThread.start()