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

def getClientList(trackerSock):
    msg = "CLIENT_LIST\n"
    trackerSock.send(msg.encode())
    numClients = int(getLine(trackerSock).rstrip())
    clientList = {}
    for i in range(numClients):
        rawClient = getLine(trackerSock).rstrip().split(":")
        clientIP = rawClient[0]
        clientPortMask = rawClient[1]
        clientList.update({clientIP: clientPortMask})
    return clientList

def disconnect(trackerSock):
    msg = "DISCONNECT!\n"
    trackerSock.send(msg.encode())
    os._exit(1)


def findChunk(clientList, chunkNum):
    for client in clientList:
        port,mask = clientList[client].split(",")
        if mask[chunkNum] == "1":
            return (client, port)
    return False

def requestChunk(peerInfo, chunkNum):
    peerIP = peerInfo[0]
    peerPort = int(peerInfo[1])
    
    peerSock = socket(AF_INET, SOCK_STREAM)
    peerSock.connect( (peerIP, peerPort) )

def handleTracker(trackerSock):
    connected = True
    while connected == True:
        printCommands()
        command = input("> ")
        #Upadate tracker with mask
        if command == "1":
            msg = "UPDATE_MASK\n"
            trackerSock.send(msg.encode())
            msg = "{}\n".format(chunkMask) 
            trackerSock.send(msg.encode())
        #Get and view clients connected to tracker
        elif command == "2":
            clientList = getClientList(trackerSock)
            printClients(clientList)
        #Request and receive a chunk if it exists in swarm
        elif command == "3":
            chunkNum = int(input("Which chunk would you like to get?"))
            clientList = getClientList(trackerSock)
            peerInfo = findChunk(clientList, chunkNum)
            if peerInfo == False:
                print("Chunk does not exist in swarm. You're screwed")
            else:
                requestChunk(peerInfo, chunkNum)
        #Disconnect from swarm
        elif command == "4":
            disconnect(trackerSock)
            connected = False
        #Must print valid command
        else:
            print("Invalid Command")
        print()


#A peer has made a request for one of your chunks we can assume that we
#We should have the chunk available to send to the peer as they have 
#Already checked our chunk mask. However if somethin went wrong we should
#Send a negative acknowledgement
def handleClient(connInfo):
    peerConn, peerAddr = connInfo
    peerIP = peerAddr[0]
    print("Recieved connection from {} {}".format(peerIP, peerAddr[1]))

# Set server/port from command line
progname = argv[0]
if len(argv) != 3:
    print("Usage: python3 {} <IPaddress> <port>".format(progname))
    exit(1)
serverIP = argv[1]
serverPort = int(argv[2])

# Establish connection to tracker
trackerSock = socket(AF_INET, SOCK_STREAM)
trackerSock.connect( (serverIP, serverPort) )

# Receive intitial file and chunk info
fileName = getLine(trackerSock).rstrip()
chunkSize = int(getLine(trackerSock).rstrip()) 
numChunks = int(getLine(trackerSock).rstrip())
chunks = []
for i in range(numChunks):
    chunk = getLine(trackerSock).split(",")
    sz = int(chunk[0].rstrip())
    digest = chunk[1].rstrip()
    chunks.append((sz, digest))

#Send our information to the tracker server
port = "27120"
chunkMask = "0" * numChunks#FIXME function to initialize chunks we have
ourClientInfo = "{},{}\n".format(port,chunkMask)
trackerSock.send(ourClientInfo.encode())

#This thread will be for communicating with the tracker
threading.Thread(target=handleTracker, args=(trackerSock,),daemon=False).start()

#Create a listening socket to receive requests from peers
listener = socket(AF_INET, SOCK_STREAM)
listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
listener.bind(('', int(port)))
listener.listen(4)

#Handle clients as they make requests. Only allow 4 clients to make requests
#At a time as not to be overloaded
running = True
while running:
    try:
        threading.Thread(target=handleClient, args=(listener.accept(),),daemon=True).start()
    except KeyboardInterrupt:
        running = False
#clientSock.close()

