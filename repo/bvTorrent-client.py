# [NameServer] Client
from socket import *
from sys import argv
from pathlib import Path
import threading
import os
import hashlib

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

def updateMask(trackerSock, mask):
    msg = "UPDATE_MASK\n"
    trackerSock.send(msg.encode())
    msg = "{}\n".format(mask) 
    trackerSock.send(msg.encode())

def getClientList(trackerSock):
    msg = "CLIENT_LIST\n"
    trackerSock.send(msg.encode())
    numClients = int(getLine(trackerSock).rstrip())
    clientList = {}
    for i in range(numClients):
        rawClient = getLine(trackerSock).rstrip().split(",")
        clientIPPort = rawClient[0]
        clientMask = rawClient[1]
        clientList.update({clientIPPort: clientMask}) 
    return clientList

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
    for client in clientList:
        mask = clientList[client]
        ipPort = client.split(":")
        ip = ipPort[0]
        port = ipPort[1]
        print("{}:{} - {}".format(ip, port, mask))
        print("-----------------------------------")

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

def getMasks(clientList):
    masks = []
    for client, mask in clientList.items():
        masks.append(mask)
    return masks

def getScarceChunk(masks, ourMask, numBlocks):
    chunkOwners = {}
    for i in range(0, len(ourMask)):
        chunkOwners[i] = 0

    for mask in masks:
        for i in range(0, len(mask)):
            chunkOwners[i] += int(mask[i])

    targetBlocks = []
    minVals = []
    for block, numOwners in chunkOwners.items():
        if ourMask[block] == '1':
            pass
        elif len(targetBlocks) < numBlocks:
            targetBlocks.append(block)
            minVals.append(numOwners)
        elif numOwners < max(minVals):
            del targetBlocks[minVals.index(max(minVals))]
            targetBlocks.append(block)
            minVals.remove(max(minVals))
            minVals.append(numOwners)

    return targetBlocks

def getTargetClient(clientList, chunkNum):
    for k,v in clientList.items():
        if v[chunkNum] == "1":
            return k

def getChunk(ip, port, chunkNum, fileSize, sizeDigest, numChunks):
    clientSock = socket(AF_INET, SOCK_STREAM)
    clientSock.connect( (ip, port) )

    chunkSize = sizeDigest[0]
    chunkDigest = sizeDigest[1]

    msg = str(chunkNum) + "\n"
    msg = msg.encode()
    clientSock.send(msg)
    chunk = getFullMsg(clientSock, chunkSize)

    currDigest = hashlib.sha224(chunk).hexdigest()
    print("Correct digest: [" + str(chunkDigest) + "]")
    print("Our digest: [" + str(currDigest) + "]")

    if currDigest != chunkDigest:
        return

    print("It's actually writing")
    fileLock.acquire()
    fileData[chunkNum] += chunk
    fileLock.release()

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
    
    #fill up list of chunk digests
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
    
    numPossessed = 0
    #Send command to tracker until connection is closed
    connected = True
    #Check if all chunks have been received and write file
    while connected == True:
        try:
            #run threads to fetch chunks
            clientList = getClientList(trackerSock)
            #get info for peer who has least common chunk
            peerMasks = getMasks(clientList)
            numChunksToGet = min(4, numChunks-numPossessed)
            chunksToGet = getScarceChunk(peerMasks, chunkMask, numChunksToGet)
            threads = []
            for i in range(0, numChunksToGet):
                targetIPPort = getTargetClient(clientList, chunksToGet[i]).split(':')
                targetIP = targetIPPort[0]
                targetPort = int(targetIPPort[1])
                #request chunk
                threads.append(
                    threading.Thread(
                        target=getChunk, args=(
                            targetIP,targetPort,chunksToGet[i],
                            fileSize,chunks[chunksToGet[i]],numChunks
                        ),
                        daemon=True
                    )
                )
                threads[i].start()

            for i in range(len(threads)):
                threads[i].join()
                chunkMask = addToChunkMask(chunkMask, chunksToGet[i])
                updateMask(trackerSock, chunkMask)
                numPossessed += 1
            
            if (chunkMask == "1"*numChunks):
                with open(fileName, "wb") as f:
                    for chunk in fileData:
                        f.write(chunk)
                break
        except KeyboardInterrupt:
            running = False
            disconnect(trackerSock)
            

#A peer has made a request for one of your chunks. They have already updated
#their peer list just before making this request and between any following
#requests. There should not be a case in which they request a chunk we do not
#have. However if that is so, we will send will simply close the connection.
def handleClient(connInfo):
    clientConn, clientInfo = connInfo

    chunkStr = getLine(clientConn)[:-1]
    try:
        chunk = int(chunkStr)
    except ValueError:
        clientConn.close()
        return

    fileLock.acquire()
    if fileData[chunk] == b'':
        clientConn.close()
        fileLock.release()
        return
    data = fileData[chunk]
    fileLock.release()
    clientConn.send(data)
    clientConn.close()


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

