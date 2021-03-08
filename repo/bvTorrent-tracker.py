from socket import *
import threading
import hashlib
import sys
import time

port=42424
#chunkSize=2**16
chunkSize=2**20
fileName="eclipse.mp4"


# Fetch file data
fin = open(fileName, "rb")
fileData = fin.read()
fin.close()

# Get chunk information
# chunkFormat = (size, digest)
chunks = []
for i in range(0, len(fileData), chunkSize):
    sz = min(chunkSize, len(fileData)-i)
    digest = hashlib.sha224(fileData[i:i+sz]).hexdigest()
    chunks.append((sz,digest))
numChunks = len(chunks)

# Creation connection dictionary
clientList = {}
clientListLock = threading.Lock()


# Set up listening socket
listener = socket(AF_INET, SOCK_STREAM)
listener.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
listener.bind(('', port))
listener.listen(32) # Support up to 32 simultaneous connections



def getFullMsg(conn, msgLength):
    msg = b''
    while len(msg) < msgLength:
        retVal = conn.recv(msgLength - len(msg))
        msg += retVal
#        if len(retVal) == 0:
#            break   
#FIXME##########################################################3
    return msg

def getLine(conn):
    msg = b''
    while True:
        ch = conn.recv(1)
        msg += ch
        if ch == b'\n' or len(ch) == 0:
            break
    return msg.decode()

# Produces a newline delimited string of client descriptors
def getClientListMsg():
    clientMsg = ""
    clientListLock.acquire()
    numClients = len(clientList)
    for addr,mask in clientList.items():
        clientMsg += "%s:%d,%s\n" % (addr[0], addr[1], mask)
    clientListLock.release()
    return (numClients, clientMsg)

def printClientList():
  print("Updated List of Peers in Swarm")
  for client,mask in clientList.items():
    print("%s:%d - %s" % (client[0], client[1], mask))

# Adds or updates the chunkMask for a client participating in the swarm
def updateClientInfo(clientIP, clientPort, chunkMask):
    clientListLock.acquire()
    clientList[(clientIP,clientPort)] = chunkMask
    printClientList()
    clientListLock.release()

# Removes a pre-existing client from participation in the swarm
def removeClientInfo(clientIP, clientPort):
    clientListLock.acquire()
    del clientList[(clientIP,clientPort)]
    printClientList()
    clientListLock.release()

def handleClient(connInfo):

    clientConn, clientAddr = connInfo
    clientIP = clientAddr[0]
    print("Received connection from %s:%d" %(clientIP, clientAddr[1]))

    # [New Connection Protocol - Step 1 of 5]
    #  - SEND the filename terminated by "\n"
    clientConn.send( (fileName+"\n").encode() )
    
    # [New Connection Protocol - Step 2 of 5]
    #  - SEND the maximum chunk size in ASCII form terminated by "\n"
    clientConn.send( (str(chunkSize)+"\n").encode() )

    # [New Connection Protocol - Step 3 of 5]
    #  - SEND the number of chunks in the file in ASCII form terminated by "\n"
    clientConn.send( (str(numChunks)+"\n").encode() )

    # [New Connection Protocol - Step 4 of 5]
    #  - SEND a newline delimited msg of chunk descriptors of the form:
    #    msg = "chunk1Size,chunk1digest\n" +
    #          "chunk2Size,chunk2digest\n" +
    #          "chunk3Size,chunk3digest\n" +
    #          ....
    #          "chunkNSize,chunkNdigest\n"  
    chunkMsg = ""
    for chunk in chunks:
        chunkMsg += "%d,%s\n" % chunk
    clientConn.send( chunkMsg.encode() )

    # [New Connection Protocol - Step 5 of 5]
    #  - RECEIVE the port that the client will listen for connections on along
    #    with the chunk mask (denoting which chunks the client has available.
    #    The port and mask should be comma delimited and the message should be
    #    newline terminated. The mask should contain a 0 or 1 for each chunk.
    #    Example 1 (new client):  "12345,0000000000...0000000000\n"
    #    Example 2 (seed client): "12345,1111111111...1111111111\n"
    #
    #  - IMPORTANT NOTE: The port provided here by the client is NOT the port
    #    of the socket currently connected to the tracker. It is the port that
    #    the client has identified to listen for incoming connections from
    #    other clients. This port (along with the client's IP address) will be
    #    shared with all other clients in the swarm. If they wish to connect
    #    to another client, this is the port they will use to do so.
    clientPort,chunkMask = getLine(clientConn)[:-1].split(',')
    clientPort = int(clientPort)
    updateClientInfo(clientIP, clientPort, chunkMask)
    

    try:
        clientConnected = True
        while clientConnected:
            # Wait to receive a 12-byte control message & handle it appropriately.
            # Possible messages may include:
            #  1) "UPDATE_MASK\n" - Client wants to send its own updated chunk mask
            #  2) "CLIENT_LIST\n" - Client wants an up-to-date list of client masks
            #  3) "DISCONNECT!\n" - Client wants to disconnect
            #  *) Anything else is out-of-protocol -- Terminate the connection

            
            cmd = getFullMsg(clientConn, 12).decode()[:-1]
            print(" - Received control message [%s]" % (cmd))


            if cmd == "UPDATE_MASK":
                # [Update Mask Protcol - Step 1 of 1]
                #  - RECEIVE (numChunks) chars (1's and 0's) terminated by a "\n"
                chunkMask = getFullMsg(clientConn, numChunks+1).decode()[:-1]
                updateClientInfo(clientIP, clientPort, chunkMask)
                
            elif cmd == "CLIENT_LIST":
                numClients, clientListMsg = getClientListMsg()
                
                # [Client List Request Protocol - Step 1 of 2]
                #  - SEND the number of clients in ASCII form terminated by "\n"
                clientConn.send( (str(numClients)+"\n").encode() )

                # [Client List Request Protocol - Step 2 of 2]
                #  - SEND newline delimited descriptors of each client of the form:
                #     clientListMsg = "client1IP:client1Port,client1ChunkMask\n" +
                #                     "client2IP:client2Port,client2ChunkMask\n" +
                #                     "client3IP:client3Port,client3ChunkMask\n" +
                #                     ...
                #                     "clientNIP:clientNPort,clientNChunkMask\n"
                clientConn.send( clientListMsg.encode() )
                
            elif cmd == "DISCONNECT!":
                print("Client disconnected")
                clientConnected = False
            else:
                print("Connection terminated")
                clientConnected = False

    except Exception:
        print("Exception occurred, closing connection")

    clientConn.close()
    removeClientInfo(clientIP, clientPort)
    


running = True
while running:
    try:
        threading.Thread(target=handleClient, args=(listener.accept(),), daemon=True).start()
    except KeyboardInterrupt:
        print('\n[Shutting down]')
        running = False
