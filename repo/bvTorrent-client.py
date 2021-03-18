# [NameServer] Client
from socket import *
from sys import argv
from pathlib import Path
import threading
import os
import hashlib

# Creating a global list to store file data. Which I hate. I'd rather write it
# to disk immediately, but to write the middle of a file with python you need
# the whole thing in memory anyway, so might as well do this annoyingness
fileData = []
fileLock = threading.Lock()
running = True
runLock = threading.Lock()

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

# Two functions to communicate with the tracker server
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

# A function modify our own mask before sending updates to the server
def addToChunkMask(chunkMask,i):
    maskList = list(chunkMask)
    if maskList[i] == "0":
        maskList[i] = "1"
    return "".join(maskList)

# Getting just the client masks from the client dictionary.
def getMasks(clientList):
    masks = []
    for client, mask in clientList.items():
        masks.append(mask)
    return masks

# Returning a list (of length numBlocks) of the top scarce chunks in the torrent
def getScarceChunks(masks, ourMask, numBlocks):
    # Creating a dictionary where the key is the number of the chunk and the
    # value is how often it appears
    chunkOwners = {}
    for i in range(0, len(ourMask)):
        chunkOwners[i] = 0

    for mask in masks:
        for i in range(0, len(mask)):
            chunkOwners[i] += int(mask[i])

    # Iterating through that dictionary. If the current value is lower than the 
    # highest value in minVals, then we replace that block in targetBlocks with
    # the current key.
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

# Getting the ip:port of the first client we encounter who has the target chunk
def getTargetClient(clientList, chunkNum):
    for k,v in clientList.items():
        if v[chunkNum] == "1":
            return k

# Actually connecting to another client and getting a chunk
def getChunk(ip, port, chunkNum, fileSize, sizeDigest, numChunks):
    clientSock = socket(AF_INET, SOCK_STREAM)
    clientSock.connect( (ip, port) )

    print("Requesting chunk %d from client [%s:%d]" % (chunkNum, ip, port))

    chunkSize = sizeDigest[0]
    chunkDigest = sizeDigest[1]

    msg = str(chunkNum) + "\n"
    msg = msg.encode()
    clientSock.send(msg)
    chunk = getFullMsg(clientSock, chunkSize)

    currDigest = hashlib.sha224(chunk).hexdigest()

    if currDigest != chunkDigest:
        return

    fileLock.acquire()
    fileData[chunkNum] += chunk
    fileLock.release()

def disconnect(trackerSock):
    msg = "DISCONNECT!\n"
    trackerSock.send(msg.encode())
    os._exit(1)

def handleTracker(trackerSock, listeningPort):
    global running

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
    chunkMask = "0" * numChunks
    ourClientInfo = "{},{}\n".format(listeningPort,chunkMask)
    trackerSock.send(ourClientInfo.encode())   
    
    numPossessed = 0
    #Check if all chunks have been received and write file
    while running:
        try:
            #run threads to fetch chunks
            clientList = getClientList(trackerSock)
            #get info for peer who has least common chunk
            peerMasks = getMasks(clientList)
            # Getting 4 chunks by default because there's a decent chance that
            # more would start overwhelm the wifi this'll be running on
            numChunksToGet = min(4, numChunks-numPossessed)
            chunksToGet = getScarceChunks(peerMasks, chunkMask, numChunksToGet)
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
                # If this array is empty, it means that the thread didn't fetch
                # any data, so don't update metadata. Else, update metadata
                if fileData[chunksToGet[i]] == b'':
                    pass
                else:
                    chunkMask = addToChunkMask(chunkMask, chunksToGet[i])
                    updateMask(trackerSock, chunkMask)
                    numPossessed += 1
            
            if (chunkMask == "1"*numChunks):
                with open(fileName, "wb") as f:
                    for chunk in fileData:
                        f.write(chunk)
                print("{} successfully downloaded!".format(fileName))
                print("Press ctrl+c to exit torrent...")
                break
        except KeyboardInterrupt:
            runLock.acquire()
            running = False
            runLock.release()
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
        print("Rejected request from client [%s:%d]" 
                % (clientInfo[0],clientInfo[1]))
        clientConn.close()
        return

    print("Recieved connection from client [%s:%d]. Sending chunk %d"
            % (clientInfo[0], clientInfo[1], chunk))

    fileLock.acquire()
    if fileData[chunk] == b'':
        clientConn.close()
        fileLock.release()
        return
    data = fileData[chunk]
    fileLock.release()
    clientConn.send(data)
    clientConn.close()

def listen():
    #Create a listening socket to receive requests from peers
    listener.listen(4)

    #Handle clients as they make requests. Only allow 4 clients to make requests
    #At a time as not to be overloaded
    while running:
        threading.Thread(target=handleClient, args=(listener.accept(),),daemon=True).start()



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
    # And open a socket ofr other people to connect to
    listener = socket(AF_INET, SOCK_STREAM)
    listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    listener.bind(('', 0))
    listeningPort = listener.getsockname()[1]

    #This thread will be for communicating with the tracker
    clientThread = threading.Thread(target=handleTracker, args=(trackerSock,listeningPort,),daemon=False)
    clientThread.start()

    serverThread = threading.Thread(target=listen, args=(), daemon=True)
    serverThread.start()

    clientThread.join()
    serverThread.join()
