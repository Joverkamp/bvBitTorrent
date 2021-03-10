from socket import *
import threading
import hashlib
import sys
import time
import math
import random


port = 10000


filename = "culture.txt"
fileSize = 2242226
chunkSize = 2**17
numChunks = math.ceil(fileSize/chunkSize)

# Reading the file into memory. Which I hate, but it's the most effecicient
# option possible with python
filedata = []
for i in range(0, numChunks):
    filedata.append(b'')
fileLock = threading.Lock()


sock = socket(AF_INET, SOCK_STREAM)
sock.bind( ('', port) )
# The listener thread will read this while the client thread that's downloading
# the file for us will write to it.
running = True

clientList = [
    "10.159.16.2:34344,111000111000111000",
    "10.159.16.2:34344,000111000111000111",
    "10.159.16.2:34344,101001010101010100",
    "10.159.16.2:34344,101011110101011101",
]

# This is just a placeholder for the client-server code, so this is fine
clients = [
    ["10.172.0.249", 34344, "111000111000111000"],
    ["10.172.0.249", 34345, "000111000111000111"],
    ["10.172.0.249", 34346, "101001010101010100"],
    ["10.172.0.249", 34347, "101011110101011101"],
]


def topScarceBlocks(masks, ourMask, nBlocks):
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
        elif len(targetBlocks) < nBlocks:
            targetBlocks.append(block)
            minVals.append(numOwners)
        elif numOwners < max(minVals):
            del targetBlocks[minVals.index(max(minVals))]
            targetBlocks.append(block)
            minVals.remove(max(minVals))
            minVals.append(numOwners)

    return targetBlocks


# Doing a little extra work to choose a random client to download from
def getTargetClient(masks, chunkNum):
    clientsWithChunk = []
    for i in range(0, len(masks)):
        if masks[i][chunkNum] == "1":
            clientsWithChunk.append(i)

    # If len(clientsWithChunks) is 0, the torrent is broken, so I'm ignoring
    # that possible error for now and returning the index of a random client
    return clientsWithChunk[random.randint(0, len(clientsWithChunk)-1)]


def getFullMsg(conn, msgLength):
    msg = b''
    while len(msg) < msgLength:
        retVal = conn.recv(msgLength - len(msg))
        msg += retVal
        if len(retVal) == 0:
            break
    return msg


def getLine(conn):
    msg = b''
    while True:
        ch = conn.recv(1)
        msg += ch
        if ch == b'\n' or len(ch) == 0:
            break
    return msg.decode()


def handleConn(connInfo):
    clientConn, clientInfo = connInfo

    chunkStr = getLine(clientConn)[:-1]
    try:
        chunk = int(chunkStr)
    except ValueError:
        clientConn.close()
        return

    fileLock.acquire()
    if filedata[chunk] == b'':
        clientConn.close()
        fileLock.release()
        return
    data = filedata[chunk]
    fileLock.release()
    clientConn.send(data)
    clientConn.close()


def getChunk(ip, port, chunkNum):
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
    filedata[chunkNum] += chunk
    fileLock.release()
    print("Got chunk {}".format(chunkNum))


def listen():
    sock.listen(4) #FIXME: Decide what the right number is
    while running:
        connInfo = sock.accept()
        threading.Thread(target=handleConn, args=(connInfo, ), daemon=True).start()


def getServerStuff():
    return clients


def download():
    ourMask = "0"*numChunks
    chunksGathered = 0

    while chunksGathered < numChunks:
        # Leaving a space to insert server stuff here
        clients = getServerStuff()
        # Getting a mask list from clients
        masks = []
        for client in clients:
            masks.append(client[2])
        # Determining whether we're on the last fetch of blocks
        chunksLeft = numChunks - chunksGathered
        # Getting 4 chunks at a time by default
        chunksToGet = min(4, chunksLeft)
        print("Chunks to get: {}".format(chunksToGet))
        # Determining what chunks we need
        targetChunks = topScarceBlocks(masks, ourMask, chunksToGet)
        print("Le chunks:" + str(targetChunks))
        # And finding indexes of clients that have those blocks
        targetClients = []
        for i in range(0, chunksToGet):
            targetClients.append(getTargetClient(masks, targetChunks[i]))

        print("Le clients: " + str(targetClients))
        threads = []
        for i in range(0, chunksToGet):
            print("i: " + str(i))
            threads.append(
                threading.Thread(
                    target=getChunk, args=(
                        clients[targetClients[i]][0],
                        clients[targetClients[i]][1],
                        targetChunks[i]
                    ),
                    daemon=True
                )
            )

            threads[i].start()
            print("Getting block {} from port {}".format(targetChunks[i],\
                                            clients[targetClients[i]][1]))

        for i in range(0, len(threads)):
            threads[i].join()
            index = targetChunks[i]
            print(type(index))
            print(index)
            ourMask = ourMask[:index] + "1" + ourMask[index+1:]
        chunksGathered += chunksToGet
        # TODO: Update our mask and do server stuff here?
        
    with open(filename, "wb") as f:
        for chunk in filedata:
            f.write(chunk)


clientThread = threading.Thread(target=download, args=(), daemon=True)
clientThread.start()
serverThread = threading.Thread(target=listen, args=(), daemon=True)
serverThread.start()

clientThread.join()
serverThread.join()
