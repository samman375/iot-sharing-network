"""
    Usage: python3 client.py localhost 12000

    Adapted from example multi-threaded client code on course homepage

    By Sam Thorley (z5257239)
"""
from socket import *
import sys

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
    if receivedMessage == "":
        print("[recv] Message from server is empty!")
    

    ### Auth related:
    
    # Get and send username
    elif receivedMessage == "username authentication request" or receivedMessage == "retry username authentication request":
        if receivedMessage == "retry username authentication request":
            print("Invalid Username. Please try again.")
        message = input("Username: ").strip()
        clientSocket.send(message.encode())
    # Get and send password
    elif receivedMessage == "password authentication request" or receivedMessage == "retry password authentication request":
        if receivedMessage == "retry password authentication request":
            print("Invalid Password. Please try again.")
        message = input("Password: ").strip()
        clientSocket.send(message.encode())
    # Max failed auth attempts. Account blocked.
    elif receivedMessage == "max failed attempts":
        print("Invalid Password. Your account has been blocked for 10s. Please try again later")
        break
    # Attempt to login to blocked account
    elif receivedMessage == "blocked account":
        print("Your account is blocked due to multiple authentication failures. Please try again later")
        break
    elif receivedMessage == "username already logged in":
        print("This username is already logged in. Try another.")
    
    ### Commands:
    
    # Get command
    elif receivedMessage == "welcome":
        print(f"Welcome!")
        message = input("Enter one of the following commands (EDG, UED, SCS, DTE, AED, OUT): ").strip().upper()
        clientSocket.send(message.encode())
    
    ### Misc:

    elif receivedMessage == "download filename":
        print("[recv] You need to provide the file name you want to download")
    else:
        print("[recv] Error: Unknown server response received")
    
    ans = input('\nDo you want to continue(y/n) :')
    if ans == 'y':
        continue
    else:
        message = "exit"
        clientSocket.send(message.encode())
        break

# close the socket
clientSocket.close()
