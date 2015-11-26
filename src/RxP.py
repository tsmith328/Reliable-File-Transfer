import socket
import hashlib
import random
import string
import math
import time
import os
import threading
import queue

#Implementation constants

#Endpoint types
CLIENT = 0
SERVER = 1

MAX_RETRIES = 5
MAX_PAYLOAD = 486
PKT_SIZE = 512
TIMEOUT = 0.5

#Packet p_types
ACK = 0b100000
NACK = 0b010000
SYN = 0b001000
FIN = 0b000100
DATA = 0b000010
RST = 0b000001

server_conn = None
connections = queue.Queue()


def connect(address, bindport):
    """
    Attempts to connect to the server located at address.
    Params:
        address -- a tuple: (ip_address (str), port_number (str or int))
        bindport - port to bind the client to
    Returns:
        A Connection to this server, or None if it cannot connect.
    """
    try:
        port = int(address[1])
        bindport = int(bindport)
        address = (address[0], port)
    except ValueError:
        print("ValueError")
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(TIMEOUT)
        sock.bind(('localhost', bindport))
        sock.connect(address)
        conn = Connection(sock, CLIENT, (address[0], port))
        return conn if conn._handshake() else None
    except socket.error as e:
        print("Socket Error " + str(e))
        return None

def listen(port):
    """
    Initializes the server socket and starts listening for connections.
    Params:
        port -- a str or int: the port to listen for connections on
    Returns:
        True if the port has been initialized, False otherwise.
    """
    try:
        port = int(port)
    except ValueError:
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("localhost", port))
        server_c = Connection(sock, SERVER)
        global server_conn
        server_conn = server_c
        listener = _Listener(server_conn, connections)
        listener.start()
    except socket.error as e:
        return False

class _Listener(threading.Thread):
    def __init__(self, connection, connection_list):
        threading.Thread.__init__(self)
        self.connection = connection
        self.connection_list = connection_list

    def run(self):
        while True:
            self.connection.sock.settimeout(None)
            pkt = self.connection._recv()
            self.connection.sock.settimeout(TIMEOUT)
            if pkt.flg == SYN:
                print("Syn received")
                self.connection.other_addr = (pkt.src_ip, pkt.src_port)
                if self.connection._handshake():
                    c = Connection(s, SERVER, self.connection.other_addr)
                    connection_list.put(c)

def accept():
    """
    Accepts a connection from a client and starts the session.
    Returns:
        a Connection to the client
    """
    while connections.empty():
        time.sleep(0.1)
    conn = connections.get()
    return conn


class Connection(object):
    """
    A Connection object: equivalent to UNIX socket, but
    with functionality that fits RxP
    """
    def __init__(self, sock, c_type, other_addr = ""):
        self.last_sent = 0
        self.win_size = 4
        self.sock = sock
        self.other_addr = other_addr
        self.c_type = c_type
        self.is_open = True


    def _handshake(self):
        """
        Returns True for good handshake, False for bad
        """
        return self._client_handshake() if self.c_type == CLIENT else self._server_handshake()

    def _client_handshake(self):
        """
        Client handshake (see state diagram)
        Returns:
            bool - True for good handshake, False for bad
        """
        #Send SYN packet
        syn = self._packetize(SYN)
        self._send(syn[0])
        pkt_type = SYN | ACK | DATA
        eq_addr = False
        corr_pkt = False
        count = 0
        #Get SynAckData
        while not eq_addr and not corr_pkt:
            eq_addr = False
            corr_pkt = False
            if count == MAX_RETRIES:
                raise socket.timeout #Reset connection
            try:
                syn_ack_data = self._recv()
                #Check if packet is SynAckData
                if syn_ack_data.src_ip == self.other_addr[0]:
                    eq_addr = True
                if pkt_type == syn_ack_data.flg:
                    corr_pkt = True
                else:
                    raise socket.timeout #Reset connection
            except socket.timeout:
                self._send(self._packetize(RST)[0]) #send reset and kill
                return False
        addr_tup = self.sock.getsockname()
        to_hash = syn_ack_data.payload + bytearray(str(addr_tup[0], 'utf-8')) + bytearray(str(addr_tup[1]), 'utf-8')
        hashed = _make_hash(to_hash)
        self._send(self._packetize(SYN | ACK, bytearray(hashed))[0])
        count = 0
        while count < MAX_RETRIES:
            try:
                success = self._recv()
                if success.src_ip == other_addr:
                    if success.flg == ACK:
                        return True
                    elif success.flg == NACK:
                        return False
                    else:
                        raise socket.timeout
            except socket.timeout:
                self._send(self._packetize(RST)[0]) #send reset and kill
                return False
        self._send(self._packetize(RST)[0])
        return False

    def _server_handshake(self):
        """
        Server handshake (see state diagram)
        Returns:
            bool - True for good handshake, False for bad
        """
        #Assuming we have received a SYN packet from a client,
        #Send SynAckData with random key
        key = self._gen_key()
        pkt_type = SYN | ACK | DATA
        pkt = self._packetize(pkt_type, key)[0]
        self._send(pkt)
        #Get SynAck packet with hash
        corr_pkt = False
        pkt_type = SYN | ACK
        count = 0
        while not corr_pkt:
            if count == MAX_RETRIES:
                raise socket.timeout
            try:
                syn_ack = self._recv()
                if syn_ack.flg == pkt_type:
                    to_hash = bytearray(key) + bytearray(syn_ack.encode()[:4]) + bytearray(syn_ack.encode()[4:6])
                    serv_hash = _make_hash(to_hash)
                    if serv_hash == syn_ack.payload:
                        self._send(self.packetize(ACK)[0])
                        return True
                    else:
                        raise socket.timeout #NACK request
                else:
                    self._send(self._packetize(NACK)[0])
            except socket.timeout:
                self._send(self._packetize(NACK)[0]) #NACK and kill
                return False

    def _gen_key(self):
        """
        Generate key for server handshake
        Returns:
            key - random 256 byte key (cryptographically secure)
        """
        return os.urandom(256)

    def _make_hash(to_hash):
        """
        Generate md5 hash
        Params:
            to_hash - message to hashed
        Returns:
            hashed message as bytes
        """
        m = hashlib.md5()
        m.update(to_hash)
        return m.digest()

    def send(self, message):
        """
        Reliably sends a message across the connection.
        Will retry MAX_RETRIES times before reporting failure.
        Limits packets sent to 50 per second
        Params:
            message -- The message to send.
        Returns:
            True if the message was successfully sent, False otherwise.
        """
        msg_size = len(message)
        timestamp = time.time()
        if msg_size < 0:
            return False
        else:
            packets = self._packetize(DATA, message)
            try:
                need_ack = queue.Queue()
                nack_list = queue.Queue()
                num_pkts = [len(packets)] #Ugly, but only good way to pass integer b/w threads
                mutex = threading.Lock() #Lock for num_pkts. Probably not necessary, but safe.
                #Listens for ACKs on sent packets.
                ack_listener = _Ack_Listener(self, need_ack, nack_list, num_pkts, mutex)
                ack_listener.start()
                #While there are packets that need to be sent, or we are waiting on ACKs, loop
                while len(packets) > 0 or not need_ack.empty() or not nack_list.empty():
                    #If room in window, send a packet
                    if need_ack.qsize() < self.win_size:
                        if time.time() < timestamp + 0.020:
                            continue #Pass if not enough time has elapsed (0.020 seconds b/w packets)
                        if len(packets) == 0:
                            continue
                        to_send = packets.pop(0)
                        need_ack.put(to_send)
                        sent = self._send(to_send)
                        timestamp = time.time() #Update timestamp of last-sent packet
                        if not sent: #Packet failed to send
                            return False
                    #Check NACKed packets, resend them (Re-add to packets list).
                    if not nack_list.empty():
                        #Get packets in queue
                        q_list = list()
                        while not nack_list.empty():
                            q_list.append(nack_list.get())
                        for item in q_list:
                            nack_list.put(item)
                        for nacked in q_list:
                            packets.append(nacked) #Resend all NACKed packets
                #All packets should be sent and ACKed by now.
                return True
            except socket.error as e:
                print("Socket error")
                return False
            except Exception as e:
                print("Other exception")
                return False

    def _send(self, packet):
        """
        Sends a Packet to the other endpoint of this Connection.
        Params:
            packet - The Packet to send over the wire
        Returns:
            True if the Packet was successfully sent, False otherwise
        """
        bytes_sent = 0
        tries = 0
        pkt = packet.encode()
        while bytes_sent < len(pkt): #Make sure full packet is sent
            #Put data on the wire
            try:
                bytes_sent += self.sock.sendto(pkt[bytes_sent:], self.other_addr)
            except socket.timeout:
                #Retry a few times. Wait after each failure.
                if tries == MAX_RETRIES:
                    return False
                tries += 1
                time.sleep(0.1)
                continue
        #All data should be on wire
        return True

    def setWindow(self, win_size):
        """
        Sets the receiving window to the specified size (in packets).
        Params:
            win_size - an int specifying how large to make the receiving buffer.
        """
        self.win_size = win_size

    def getWindow(self):
        """
        Allows the user to get the current size of the receiving buffer.
        Returns:
            an int describing the length of the receiving buffer (in packets).
        """
        return self.win_size


    def _packetize(self, p_type, data = b''):
        """
        Creates a list of Packets for the provided data.
        If p_type has the DATA bit set, a list of DATA Packets is created which contains data.
        If p_type has other flag bits set, a single Packet is returned in a list with those flags set.
        Params:
            p_type -- The type of the packets, as defined in this module
            data -- Optionally, the data to inculde in the packets' payloads, as bytes.
        Returns:
            a list of packets
        """
        packets = []
        if len(data) > 0:
            payload = list((data[i:(MAX_PAYLOAD)+i] for i in range(0, len(data), MAX_PAYLOAD)))
        else:
            payload = [b'']
        num_seg = len(payload)
        for i in range(num_seg):
            p = _Packet()
            #Source IP and port
            my_ip, my_port = self.sock.getsockname()
            p.src_ip = my_ip
            p.src_port = int(my_port)
            #Destination IP and port
            p.dest_ip = self.other_addr[0]
            p.dest_port = self.other_addr[1]
            #Sequence number
            p.seq = i
            #Number of segments
            p.num_seg = num_seg
            #Window size
            p.win_size = self.win_size
            #Payload size
            p.pay_size = len(payload[i])
            #Flags
            p.flg = p_type
            #Payload
            p.payload = bytearray(payload[i])
            packet = self._checksum(p)
            packets.append(packet)
        return packets


    def recv(self, msg_size=MAX_PAYLOAD):
        """
        Receive msg_size bytes of data.
        Params:
            msg_size - size (in bytes) of message to receive
        Returns:
            The message as bytes.
        """
        if msg_size < 0:
            return b'' #If invalid, return empty bytes
        elif msg_size < MAX_PAYLOAD:
            msg_size = MAX_PAYLOAD
        numpackets = math.ceil(msg_size / MAX_PAYLOAD)
        payload_list = [None] * numpackets
        while None in payload_list: #Keep going until all packets received
            pkt = self._recv()
            if pkt == None:
                continue
            if pkt.flg == FIN:
                self._close()
            if numpackets != pkt.num_seg:
                continue #Skip this packet. It's not part of this message
            payload = pkt.payload[:pkt.pay_size]
            payload_list[pkt.seq] = payload
        return b''.join(payload_list)


    def _recv(self, pkt_size=PKT_SIZE):
        """
        Receive a single Packet
        Params:
            pkt_size - size of packet to receive (default PKT_SIZE)
        Returns:
            A Packet object (or None)
        """
        chunks = []
        tries = 0
        bytes_recd = 0
        checksum_match = False
        while bytes_recd < pkt_size:
            try:
                chunk = self.sock.recvfrom(pkt_size - bytes_recd)
            except socket.timeout: #No data (shouldn't happen if socket doesn't block)
                #Retry a few times. Wait after each failure.
                if tries == MAX_RETRIES:
                    print("Receive Timeout")
                    return None
                tries += 1
                time.sleep(0.1)
                continue
            if chunk[0] == b'': #No data (shouldn't happen if socket blocks.)
                print("no data")
                return None
            sender = chunk[1]
            if len(chunks) > 0:
                if chunks[0][1] == sender: #Check it's from the same sender.
                    chunks.append(chunk)
                    bytes_recd += len(chunk[0])
            else:
                chunks.append(chunk) #First chunk. Assume the rest should be from same sender.
                bytes_recd += len(chunk[0])
        data = [chk[0] for chk in chunks]
        pkt = b''.join(data)
        pkt_object = _Packet(pkt)
        if not pkt_object:
            print("Packet is none")
            return None
        checksum_match = self._validate(pkt_object)
        if not checksum_match: #Bad packet. Send NACK
            if pkt_object.flg & (ACK | NACK) == 0: 
                self._nack(pkt_object)
            print("bad packet")
            return None
        if pkt_object.flg & (ACK | NACK) == 0:
            self._ack(pkt_object)
        return pkt_object

    def _ack(self, packet):
        """
        Sends an ACK message for a received packet.
        Params:
            packet -- A Packet to ACKnowledge
        """
        #Construct ACK packet and set sequence number to equal packet's sequence number
        if self.other_addr == "":
            self.other_addr = (packet.src_ip, packet.src_port)
        ack = self._packetize(ACK)[0]
        ack.seq = packet.seq
        self._send(ack)
        print("Sent ACK")

    def _nack(self, packet):
        """
        Sends a NACK message for a received packet.
        Params:
            packet -- A Packet to NotACKnowledge
        """
        #Construct NACK packet and set sequence number to equal packet's sequence number
        nack = self._packetize(NACK)[0]
        nack.seq = packet.seq
        self._send(nack)
        print("Sent NACK")

    def _checksum(self, packet):
        """
        Generates the checksum for a packet. Then edits the packet
        to include the checksum in the correct field.
        Params:
            packet -- the packet to calculate the checksum for
        Returns:
            The same packet with an updated checksum
        """
        #Split packet into 2-byte words
        words = list((str(packet)[0+i:(4)+i] for i in range(0, 2*len(packet), 4)))
        words = [int(i, 16) for i in words]
        total = sum(words)
        total = bin(total)[2:]
        #Add words together. If too long, carry
        if len(total) > 16:
            total = '0'*(32-len(total)) + total
            hi = total[:16]
            lo = total[16:]
            hi = int(hi, 2)
            lo = int(lo, 2)
            total = hi + lo
            total = bin(total)[2:]
        total = '0'*(16-len(total)) + total
        checksum = ''.join('1' if x == '0' else '0' for x in total)
        #Edit packet to have new checksum
        packet.check = int(checksum,2)
        return packet


    def _validate(self, packet):
        """
        Validates a packet by calculating its checksum.
        Returns:
            True if valid, False otherwise.
        """
        check = packet.check
        packet = self._checksum(packet)
        valid = packet.check == 0
        packet.check = check #Restore checksum of the packet.
        return valid

    def close(self):
        """
        Close the connection
        Returns after the connection has been closed.
        """
        #Send FIN
        self._send(self._packetize(FIN))
        #Listen for FIN+ACK
        while True:
            pkt = self._recv()
            #Check if FIN+ACK
            if pkt == None:
                continue
            if pkt.flg != FIN | ACK:
                continue
            #Send ACK, then free everything
            self._send(ACK)
            self.sock.close()
            return

    def _close(self):
        """
        Called when a FIN packet is received.
        Negotiates a close and closes the socket.
        """
        #Send FIN + ACK
        self._send(self._packetize(ACK | FIN))
        while True:
            pkt = self._recv()
            if pkt == None:
                continue
            if pkt.flg != ACK:
                continue
            #Got ACK. Connection closed
            self.sock.close()
            #Notify user
            raise ConnectionClosedError(self)

class ConnectionClosedError(Exception):
    """
    Is raised when the connection is closed by the
    other endpoint.
    """
    def __init__(self, conn):
        conn.is_open = False

    def __str__(self):
        return "This connection has been closed."

class _Ack_Listener(threading.Thread):
    """
    Threadable inner class for handling ACKS and NACKS for a sliding window
    protocol
    """
    def __init__(self, conn, ack_list, nack_list, num_pkts, mutex):
        """
        Constructor for Ack_Listener object
        Params:
            conn - Connection to receive on
            ack_list - list of Packet objects that need ACKs
            nack_list - list of Packet objects which have been NACKed
            num_pkts - the number of packets that will need ACKs
            mutex - a threading lock for num_pkts
        """
        threading.Thread.__init__(self) #SUPAH
        self.ack_list = ack_list
        self.nack_list = nack_list
        self.conn = conn
        self.num_pkts = num_pkts
        self.mutex = mutex

    def run(self):
        while self.num_pkts[0] > 0: #If ==0, we know we've ACKed all packets
            pkt_object = self.conn._recv() #Grab a packet
            if pkt_object == None:
                continue #No packet, or corrupt.
            if pkt_object.flg == ACK: #Got ACK
                #Get packets in queue
                q_list = list()
                while not self.ack_list.empty():
                    q_list.append(self.ack_list.get())
                for item in q_list:
                    self.ack_list.put(item)
                for pakt in q_list:
                    if pakt.seq == pkt_object.seq:
                        self.ack_list.get(pakt) #Remove packet from ACK list
                        with self.mutex:
                            self.num_pkts[0] -= 1 #Decrement num_pkts
            elif pkt_object.flg == NACK:
                #Get packets in queue
                q_list = list()
                while not self.ack_list.empty():
                    q_list.append(self.ack_list.get())
                for item in q_list:
                    self.ack_list.put(item)
                for pakt in q_list:
                    if pakt.seq == pkt_object.seq:
                        self.nack_list.put(pakt) #Got NACK


class _Packet(object):
    """
    An inner class to help define packets.
    """
    def __init__(self, data = 512*b'\0'):
        self.src_ip = '.'.join([str(b) for b in data[:4]])
        self.src_port = int.from_bytes(data[4:6], "big")
        self.dest_ip = '.'.join([str(b) for b in data[6:10]])
        self.dest_port = int.from_bytes(data[10:12], "big")
        self.seq = int.from_bytes(data[12:16], "big")
        self.num_seg = int.from_bytes(data[16:20], "big")
        self.check = int.from_bytes(data[20:22], "big")
        self.win_size = int.from_bytes(data[22:24], "big")
        self.pay_size = (data[24] << 1) + ((data[25] & 0x80) >> 7)
        self.flg = (data[25] & 126) >> 1
        self.payload = bytearray([int(b) for b in data[26:]])

    def __len__(self):
        return int(len(str(self))/2)

    def __repr__(self):
        packet = ''
        #src IP
        ip = self.src_ip.split('.')
        ip = [hex(int(b))[2:] for b in ip]
        ip = ['0'*(2-len(b))+b for b in ip]
        packet += ''.join(ip)

        #src_port
        port = hex(self.src_port)[2:]
        packet += '0'*(4-len(port)) + port

        #dest IP
        ip = self.dest_ip.split('.')
        ip = [hex(int(b))[2:] for b in ip]
        ip = ['0'*(2-len(b))+b for b in ip]
        packet += ''.join(ip)

        #dest_port
        port = hex(self.dest_port)[2:]
        packet += '0'*(4-len(port)) + port

        #seq_num
        num = hex(self.seq)[2:]
        packet += '0'*(8-len(num)) + num

        #num_segs
        num = hex(self.num_seg)[2:]
        packet += '0'*(8-len(num)) + num

        #checksum
        checksum = hex(self.check)[2:]
        packet += '0'*(4-len(checksum)) + checksum

        #window size
        win_size = hex(self.win_size)[2:]
        packet += '0'*(4-len(win_size)) + win_size

        #payload size, flags, and unused bit
        part = str(bin(self.pay_size))[2:] + str(bin(self.flg))[2:] + '0'
        part = hex(int(part,2))[2:]
        packet += '0'*(4-len(part)) + part

        #payload
        payload = ''.join('%02x' % b for b in self.payload)
        packet += payload

        return packet

    def encode(self):
        """
        Encodes the packet as a bytes object.
        """
        packet = bytearray(0)
        #src IP
        ip = self.src_ip.split('.')
        ip = [int(b) for b in ip]
        for i in ip:
            packet.append(i)

        #src_port
        packet.append((self.src_port >> 8) & 0xff) #High byte
        packet.append(self.src_port & 0xff) #Low byte

        #dest IP
        ip = self.dest_ip.split('.')
        ip = [int(b) for b in ip]
        for i in ip:
            packet.append(i)

        #dest_port
        packet.append((self.dest_port >> 8) & 0xff) #High byte
        packet.append(self.dest_port & 0xff) #Low byte

        #seq_num
        b = [(self.seq >> i) & 0xff for i in (24,16,8,0)]
        for i in b:
            packet.append(i)

        #num_segs
        b = [(self.num_seg >> i) & 0xff for i in (24,16,8,0)]
        for i in b:
            packet.append(i)

        #checksum
        packet.append((self.check >> 8) & 0xff) #High byte
        packet.append(self.check & 0xff) #Low byte

        #window size
        packet.append((self.win_size >> 8) & 0xff) #High byte
        packet.append(self.win_size & 0xff) #Low byte

        #payload size, flags, and unused bit
        packet.append(self.pay_size >> 1) #High byte
        packet.append(((self.pay_size & 1) << 7) + (self.flg << 1)) #Low byte (pay_size[1] + flg + unused)

        #payload
        for b in self.payload:
            packet.append(b)

        #Buffer the end
        if len(packet) < 512:
            packet += bytearray([0]*(512-len(packet)))

        return bytes(packet)
