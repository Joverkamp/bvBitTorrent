# [NameServer] Client
from socket import *
from sys import argv
from pathlib import Path
import threading
import os

fileData = []
fileLock = threading.Lock()

def getLine(conn):
    msg = b''
    while True:
        ch = conn.recv(1)
        msg += ch
        if ch == b'\n' or len(ch) == 0:
            break
    return msg.decode()

def getFullMsg(conn, msgLength):
    msg = b''
    while len(msg) < msgLength:
        retVal = conn.recv(msgLength - len(msg))
        msg += retVal
        if len(retVal) == 0:
            break   
    return msg

def getClientList(trackerSock):
    msg = "CLIENT_LIST\n"
    trackerSock.send(msg.encode())
    numClients = int(getLine(trackerSock).rstrip())
    clientList = {}
    for i in range(numClients):
        #rawClient = getLine(trackerSock).rstrip().split(":")
        rawClient = getLine(trackerSock).rstrip().split(",")
        #clientIP = rawClient[0]
        #clientPortMask = rawClient[1]
        clientIPPort = rawClient[0]
        clientMask = rawClient[1]
        #clientList.update({clientIP: clientPortMask}) 
        clientList.update({clientIPPort: clientMask}) 
    return clientList
'''
def getSudoClientList():
    sudoList = {
        "10.12.32.45":"12345,00010001011100001",
        "12.43.86.12":"96592,01001101101010010",
        "11.11.11.01":"37584,01101100100001111",
        "10.32.07.19":"19593,00000000000100000",
        "17.17.19.14":"99999,11110101001101111",
        "16.11.60.34":"64646,11101101010101111"}
    return sudoList
'''

def getSudoClientList():
    sudoList = {
        "10.172.0.249:34344":"11111111111111111",
        "10.12.32.45:12345":"00010001011100001",
        "12.43.86.12:96592":"01001101101010010",
        "11.11.11.01:37584":"01101100100001111",
        "10.32.07.19:19593":"11111000110100000",
        "17.17.19.14:99999":"11110101001101111",
        "16.11.60.34:64646":"11011001010101111"}
    return sudoList

def printClients(clientList):
    print()
    print("Client List")   
    for i, ip in enumerate(clientList, start=1):
        clientInfo = clientList[ip].split(",")
        port = clientInfo[0]
        mask = clientInfo[1]
        print("{}:{} - {}".format(ip, port, mask))
        print("------------------------------------------------------")

def printCommands():
    print("Commands")
    print("   [1] Update Mask")
    print("   [2] Get Client List")
    print("   [3] Request Chunks")
    print("   [4] Disconnect")

def addToChunkMask(chunkMask,i):
    maskList = list(chunkMask)
    if maskList[i] == "0":
        maskList[i] = "1"
    return "".join(maskList)
'''
def getMasks(clientList):
    masks = []
    for client in clientList:
        port,mask = clientList[client].split(',')
        masks.append(mask)
    return masks
'''
def getMasks(clientList):
    masks = []
    for client, mask in clientList.items():
        masks.append(mask)
    return masks

def getScarceChunk(masks, ourMask):
    chunkOwners = {}
    for i in range(0, len(ourMask)):
        chunkOwners[i] = 0

    for mask in masks:
        for i in range(0, len(mask)):
            chunkOwners[i] += int(mask[i])
    targetBlock = -1
    minVal = 0
    for block, numOwners in chunkOwners.items():
        if ourMask[block] == '1':
            pass
        elif targetBlock == -1:
            targetBlock = block
            minVals = numOwners
        elif numOwners < minVals:
            targetBlock = block
            minVals = numOwners

    return targetBlock
'''
def getTargetClient(clientList, chunkNum):
    clients = {}
    for client in clientList:
        ip = clients
        port = clientList[client][0]
        mask = clientList[client][1]
        ipPort = "{}:{}".format(ip,port)
        clients.update({ipPort: mask}) 
    for k,v in clientList.items():
        if v[chunkNum] == "1":
            return k
'''
def getTargetClient(clientList, chunkNum):
    for k,v in clientList.items():
        if v[chunkNum] == "1":
            return k

def getChunk(ip, port, chunkNum, fileSize, chunkSize, numChunks):
    clientSock = socket(AF_INET, SOCK_STREAM)
    clientSock.connect( (ip, port) )

    msg = str(chunkNum) + "\n"
    msg = msg.encode()
    clientSock.send(msg)
    if chunkNum < numChunks - 1:
        chunk = getFullMsg(clientSock, chunkSize)
    else:
        chunk = getFullMsg(clientSock, fileSize % chunkSize)

    fileLock.acquire()
    fileData[chunkNum] += chunk
    fileLock.release()
'''
def requestChunk(peerInfo, chunkNum):
    peerIP = peerInfo[0]
    peerPort = int(peerInfo[1])
    
    peerSock = socket(AF_INET, SOCK_STREAM)
    peerSock.connect( (peerIP, peerPort) )
'''
def disconnect(trackerSock):
    msg = "DISCONNECT!\n"
    trackerSock.send(msg.encode())
    os._exit(1)

def handleTracker(trackerSock, listeningPort): 
    #Receive intitial file and chunk info
    fileName = getLine(trackerSock).rstrip()
    chunkSize = int(getLine(trackerSock).rstrip()) 
    numChunks = int(getLine(trackerSock).rstrip())
    
    #Initialize the chunk data as empty
    fileLock.acquire()
    for i in range(0, numChunks):
        fileData.append(b'')
    fileLock.release()
    
    fileSize = 0
    chunks = []
    for i in range(numChunks):
        chunk = getLine(trackerSock).split(",")
        sz = int(chunk[0].rstrip())
        fileSize += sz
        digest = chunk[1].rstrip()
        chunks.append((sz, digest))
    
    #Send our information to the tracker server
    chunkMask = "0" * numChunks#FIXME function to initialize chunks we have
    ourClientInfo = "{},{}\n".format(listeningPort,chunkMask)
    trackerSock.send(ourClientInfo.encode())   

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
            chunksToGet = int(input("How many chunks would you like to get?"))
            for i in range(chunksToGet):
                #update peer list
                #clientList = getClientList(trackerSock)
                clientList = getSudoClientList()
                peerMasks = getMasks(clientList)
                chunkToGet = getScarceChunk(peerMasks, chunkMask)
                targetIPPort = getTargetClient(clientList, chunkToGet).split(':')
                #get info for peer who has least common chunk
                print(chunkToGet)
                print(targetIPPort)
                #request chunk
                #requestChunk(peerInfo, chunkNum)
                print(fileData)
                getChunk(targetIPPort[0],int(targetIPPort[1]),chunkToGet,fileSize,chunkSize, numChunks)
                print(fileData)
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

if __name__ == "__main__":
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
    listeningPort = "27120"

    #This thread will be for communicating with the tracker
    threading.Thread(target=handleTracker, args=(trackerSock,listeningPort,),daemon=False).start()

    #Create a listening socket to receive requests from peers
    listener = socket(AF_INET, SOCK_STREAM)
    listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    listener.bind(('', int(listeningPort)))
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

