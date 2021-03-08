# [NameServer] Client
from socket import *
from sys import argv
from pathlib import Path
import threading
import os

def printClients(clientList):
    print()
    print("Client List")   
    for i, ip in enumerate(clientList, start=1):
        clientInfo = clientList[ip].split(",")
        port = clientInfo[0]
        mask = clientInfo[1]
        print("IP:{}   Port:{}   Mask:{}".format(ip, port, mask))
        print("------------------------------------------------------")

def printCommands():
    print("Commands")
    print("   [1] Update Mask")
    print("   [2] Get Client List")
    print("   [3] Request Chunk")
    print("   [4] Disconnect")

def addToChunkMask(mask, i):
    maskList = list(mask)
    if maskList[i] == "0":
        maskList[i] = "1"
    return "".join(maskList)

def getLine(conn):
    msg = b''
    while True:
        ch = conn.recv(1)
        msg += ch
        if ch == b'\n' or len(ch) == 0:
            break
    return msg.decode()

def getClientList(clientSock):
    msg = "CLIENT_LIST\n"
    clientSock.send(msg.encode())
    numClients = int(getLine(clientSock).rstrip())
    clientList = {}
    for i in range(numClients):
        rawClient = getLine(clientSock).rstrip().split(":")
        clientIP = rawClient[0]
        clientPortMask = rawClient[1]
        clientList.update({clientIP: clientPortMask})
    return clientList

def disconnect(clientSock):
    msg = "DISCONNECT!\n"
    clientSock.send(msg.encode())
    os._exit(1)


def findChunk(clientList, chunkNum):
    for client in clientList:
        port,mask = clientList[client].split(",")
        if mask[chunkNum] == "1":
            print("Chunk Found")
            return (client, port)
    return False

def requestChunk(clientSock, peerInfo, chunkNum):
    peerIP, peerPort = peerInfo
    print("{}   {}   {}".format(peerIP,peerPort,chunkNum))
    peerSock = socket(AF_INET, SOCK_STREAM)
    peerSock.connect( (peerIP, peerPort) )
    msg = "123456789123\n"
    peerSock.send(msg.encode())

def handleTracker(clientSock):
    connected = True
    while connected == True:
        printCommands()
        command = input("> ")
        command = int(command)
        if command == 1:
            msg = "UPDATE_MASK\n"
            clientSock.send(msg.encode())
            msg = "{}\n".format(chunkMask) 
            clientSock.send(msg.encode())
        elif command == 2:
            clientList = getClientList(clientSock)
            printClients(clientList)
        elif command == 3:
            chunkNum = int(input("Which chunk would you like to get?"))
            clientList = getClientList(clientSock)
            peerInfo = findChunk(clientList, chunkNum)
            if peerInfo == False:
                print("Chunk not found")
            else:
                requestChunk(clientSock, peerInfo)
        elif command == 4:
            disconnect(clientSock)
            connected = False

        else:
            print("Invalid Command\n")
        print()

def handleClient(connInfo):
    peerConn, peerAddr = connInfo
    peerIP = clientAddr[0]
    print("Recieved connection from {} {}".format(peerIP, peerAddr[1]))

# Set server/port from command line
progname = argv[0]
if len(argv) != 3:
    print("Usage: python3 {} <IPaddress> <port>".format(progname))
    exit(1)
serverIP = argv[1]
serverPort = int(argv[2])

# Establish connection to tracker
clientSock = socket(AF_INET, SOCK_STREAM)
clientSock.connect( (serverIP, serverPort) )

# Receive intitial file and chunk info
fileName = getLine(clientSock).rstrip()
chunkSize = int(getLine(clientSock).rstrip()) 
numChunks = int(getLine(clientSock).rstrip())
chunks = []
for i in range(numChunks):
    chunk = getLine(clientSock).split(",")
    sz = int(chunk[0].rstrip())
    digest = chunk[1].rstrip()
    chunks.append((sz, digest))

#Send our information to the tracker server
port = "27120"
chunkMask = "0" * numChunks#FIXME function to initialize chunks we have
ourClientInfo = "{},{}\n".format(port,chunkMask)
clientSock.send(ourClientInfo.encode())


threading.Thread(target=handleTracker, args=(clientSock,),daemon=False).start()

listener = socket(AF_INET, SOCK_STREAM)
listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
listener.bind(('', int(port)))
listener.listen(4)

running = True
while running:
    try:
        threading.Thread(target=handleClient, args=(listener.accept(),),daemon=True).start()
    except KeyboardInterrupt:
        running = False
#clientSock.close()

