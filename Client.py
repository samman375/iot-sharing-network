"""
    Usage: python3 client.py localhost 12000

    Adapted from example multi-threaded client code on course homepage

    By Sam Thorley (z5257239)
"""
from socket import *
import sys, re

# Server would be running on the same host as Client
if len(sys.argv) != 4:
    print("\n===== Error usage, python3 client.py SERVER_IP SERVER_PORT CLIENT_UDP_SERVER_PORT ======\n")
    exit(0)
serverHost = sys.argv[1]
serverPort = int(sys.argv[2])
clientUDPServerPort = int(sys.argv[3])
serverAddress = (serverHost, serverPort)

# define a socket for the client side, it would be used to communicate with the server
clientSocket = socket(AF_INET, SOCK_STREAM)

# build connection with the server and send message to it
clientSocket.connect(serverAddress)

while True:
    # message = input("===== Please type any messsage you want to send to server: =====\n")
    # clientSocket.sendall(message.encode())

    # receive response from the server
    # 1024 is a suggested packet size, you can specify it as 2048 or others
    data = clientSocket.recv(1024)
    receivedMessage = data.decode()

    # parse the message received from server and take corresponding actions
    if receivedMessage == "" or receivedMessage == "\r":
        print("[recv] Message from server is empty!")
    
    ### Auth related:
    
    # Get and send username
    elif receivedMessage == "username authentication request\r" or receivedMessage == "retry username authentication request\r":
        if receivedMessage == "retry username authentication request\r":
            print("Invalid Username. Please try again.")
        message = input("Username: ").strip()
        clientSocket.send(message.encode())
    # Get and send password
    elif receivedMessage == "password authentication request\r" or receivedMessage == "retry password authentication request\r":
        if receivedMessage == "retry password authentication request\r":
            print("Invalid Password. Please try again.")
        message = input("Password: ").strip()
        clientSocket.send(message.encode())
    # Max failed auth attempts. Account blocked.
    elif receivedMessage == "max failed attempts\r":
        print("Invalid Password. Your account has been blocked for 10s. Please try again later")
        break
    # Attempt to login to blocked account
    elif receivedMessage == "blocked account\r":
        print("Your account is blocked due to multiple authentication failures. Please try again later")
        break
    elif receivedMessage == "username already logged in\r":
        print("This username is already logged in. Try another.")
        message = input("Username: ").strip()
        clientSocket.send(message.encode())

    # Disconnect
    elif receivedMessage == "successfully disconnected\r":
        print("Successfully logged out. Goodbye!")
        break

    ### Commands:
    
    # Get command
    elif receivedMessage == "welcome\r" or receivedMessage == "command request\r":
        if receivedMessage == "welcome\r":
            print("Welcome!")
        validInput = False
        while not validInput:
            message = input("Enter one of the following commands (EDG, UED, SCS, DTE, AED, OUT): ").strip().upper()
            if message[0:3] not in ['EDG', 'UED', 'SCS', 'DTE', 'AED', 'OUT']:
                print("Invalid command.")
            else:
                validInput = True
                clientSocket.send(message.encode())
    
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

    ### Misc:
    else:
        print(f"Error: Unknown server response received - {receivedMessage}")


# close the socket
clientSocket.close()
