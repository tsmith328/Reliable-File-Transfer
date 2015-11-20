import socket
import hashlib
import random
import string
import math
import time

#Implementation constants

#Endpoint types
CLIENT = 0
SERVER = 1

MAX_RETRIES = 5
MAX_PAYLOAD = 486
PKT_SIZE = 512

#Packet p_types
ACK = 0b100000
NACK = 0b010000
SYN = 0b001000
FIN = 0b000100
DATA = 0b000010
RST = 0b000001

server_conn = None
connections = []

"""
Attempts to connect to the server located at address.
Params: address -- a tuple: (ip_address (str), port_number (str or int))
Returns: A Connection to this server, or None if it cannot connect.
"""
def connect(address):
    try:
        port = int(port)
        address = (address[0], int(address[1]))
    except ValueError:
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(address)
        conn = Connection(sock, CLIENT, address)
        return conn if conn._handshake() else None
    except socket.error:
        return None

"""
Initializes the server socket and starts listening for connections.
Params: port -- a str or int: the port to listen for connections on
Returns: True if the port has been initialized, False otherwise.
"""
def listen(port):
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
        #handshake
        #multithreaded loop to accept connections
        return True
    except socket.error:
        return False

"""
Accepts a connection from a client and starts the session.
Returns: A Connection to the client
"""
def accept():
    while len(connections) < 1:
        time.sleep(1)
    conn = connections.pop(0)
    conn.other_addr = conn.sock.getpeername()
    return conn

"""
A Connection object: equivalent to UNIX socket, but
with functionality that fits RxP
"""
class Connection(object):
    def __init__(self, sock, c_type, other_addr = ""):
        self.last_sent = 0
        self.win_size = 4
        self.sock = sock
        self.other_addr = other_addr

    """
    Returns True for good handshake, False for bad
    """
    def _handshake(self):
        return _client_handshake() if self.p_type == CLIENT else _server_handshake()

    def _client_handshake(self):
        self._send(SYN)
        eq_addr = False
        corr_pkt = False
        #Needs timeout
        while not eq_addr and not corr_pkt:
            try:
                syn_ack_data = self._recv()
                if syn_ack_data.src_ip == other_addr:
                    eq_addr = True
                pkt_type = SYN & ACK & DATA
                if pkt_type == syn_ack_data.flags:
                    corr_pkt = True
                else:
                    pass #nack
            except socket.timeout:
                return False
        addr_tup = socket.getsockname(self.sock)
        to_hash = syn_ack_data.data + str(addr_tup[0]) + str(addr_tup[1])
        hashed = self._make_hash(to_hash)
        #TODO-send syn+ack with hash
        valid = False
        while not eq_addr:
            try:
                success = self._recv()
                if success.src_ip == other_addr:
                    if success.flags == ACK:
                        valid = True
                        return True
                    elif success.flags == NACK:
                        valid = True
                        return False
                    else:
                        pass #nack
            except socket.timeout:
                return False

    def _make_hash(self, to_hash):
        m = hashlib.md5()
        m.update(to_hash.encode('utf-8'))
        return m.hexdigest()

    """
    Reliably sends a message across the connection.
    Will retry MAX_RETRIES times before reporting failure.
    Params: message -- The message to send.
    Returns: True if the message was successfully sent, False otherwise.
    """
    def send(self, message):
        pass

    """
    Sets the receiving window to the specified size (in packets).
    Params: win_size -- an int specifying how large to make the receiving buffer.
    """
    def setWindow(self, win_size):
        self.win_size = win_size

    """
    Allows the user to get the current size of the receiving buffer.
    Returns: an int describing the length of the receiving buffer (in packets).
    """
    def getWindow(self):
        return self.win_size

    """
    Internal method for sending non-data packets
    """
    def _send(self, p_type):
        packet = _packetize(p_type)
        #TODO: Error checking and retries and other stuff
        self.sock.send(packet)

    """
    Splits a data string into packets with payloads of MAX_PAYLOAD length.
    Returns a list of packets
    """
    def _packetize(self, p_type, data = ""):
        packets = []

        if len(data) > 0:
            payload = list((data[0+i:(MAX_PAYLOAD)+i] for i in range(0, len(data), MAX_PAYLOAD)))
        else:
            payload = [""]
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
            p.seq = i + last_sent + 1
            #Number of segments
            p.num_seg = num_seg
            #Window size
            p.win_size = self.win_size
            #Payload size
            p.pay_size = len(payload[i])
            #Flags
            p.flg = p_type
            #Payload
            p.payload = bytearray(payload[i], 'utf-8')
            if len(p.payload) < 486:
                p.payload.extend([0 for x in range(486 - len(p.payload))])
            packet = _checksum(packet)
            packets.append(packet)
        return packets

    """Receive data as a list of packets
    Params:
        msgsize - size of message to receive
    Returns:
        ret - message as bytes array encoded in hex
    """
    def recv(self, msgsize=MAX_PAYLOAD):
        #TODO - sequence number validation
        if msgsize < 0:
            return []
        elif msgsize < MAX_PAYLOAD:
            msgsize = MAX_PAYLOAD
        numpackets = msgsize / MAX_PAYLOAD
        payload_list = []
        for i in range(numpackets):
            pkt = self._recv()
            payload = pkt[26:]
            payload_list.append(payload)
        ret = b''.join(payload_list)
            # self._send(ACK)
        return ret


    """Internal method to receive a packet
    Params:
        pkt_size - size of packet to receive (default 512)
    Returns:
        pkt - packet as bytes array (None if socket connection broken)
    """
    def _recv(self, pkt_size=PKT_SIZE):
        chunks = []
        bytes_recd = 0
        checksum_match = False
        while not checksum_match:
            while bytes_recd < pkt_size:
                try:
                    chunktuple = s.recvfrom(pkt_size - bytes_recd)
                except socket.timeout as e:
                    raise e
                if len(chunktuple) > 0:
                    if chunktuple[0] == b'':
                        return None
                    sender = chunktuple[1]
                    if len(chunks) > 0:
                        if chunks[0][1] == sender:
                            chunks.append(chunktuple)
                            bytes_recd += len(chunktuple[0])
                    else:
                        chunks.append(chunktuple)
                        bytes_recd += len(chunktuple[0])
            byteslist = [byte[0] for byte in chunks]
            pkt = b''.join(byteslist)
            pkt_object = _Packet(pkt)
            checksum_match = _validate(pkt_object)
            if not checksum_match:
                self._send(NACK)
        return pkt_object


    """
    Generates the checksum for a packet. Then edits the packet
    to include the checksum in the correct field.
    Params: packet -- the packet to calculate the checksum for
    Returns: The same packet with an updated checksum
    """
    def _checksum(self, packet):
        #Split packet into 4-byte words
        words = list((str(packet)[0+i:(4)+i] for i in range(0, len(packet), 4)))
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

    """
    Validates a packet by calculating its checksum.
    Returns True if valid, False otherwise.
    """
    def _validate(packet):
        packet = _checksum(packet)
        return True if int(packet.check,16) == 0 else False

"""
An inner class to help define packets.
"""
class _Packet(object):
    def __init__(self, data = 512*b'\0'):
        self.src_ip = '.'.join([int(b) for b in data[:4]])
        self.src_port = int(data[4:5])
        self.dest_ip = '.'.join([int(b) for b in data[5:9]])
        self.dest_port = int(data[9:10])
        self.seq = int(data[10:14])
        self.num_seg = int(data[14:18])
        self.check = int(data[18:20])
        self.win_size = int(data[20:22])
        self.pay_size = 2*int(data[22]) + int((data[23] & 128) >> 7)
        self.flg = int((data[23] & 126) >> 1)
        self.payload = bytearray([int(b) for b in data[24:]])

    def __len__(self):
        return len(str(self)) / 2

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
        win_sze = hex(self.win_size)[2:]
        packet += '0'*(4-len(win_sze)) + win_sze

        #payload size, flags, and unused bit
        part = str(bin(self.pay_size))[2:] + str(bin(self.flg))[2:] + '0'
        part = hex(int(part,2))[2:]
        packet += '0'*(4-len(part)) + part

        #payload
        payload = ''.join('%02x' % b for b in self.payload)
        packet += payload

        return packet

    """
    Encodes the packet as a bytes object.
    """
    def encode(self):
        packet = bytearray(0)
        #src IP
        ip = self.src_ip.split('.')
        ip = int(b) for b in ip]
        packet.extend(i) for i in ip

        #src_port
        packet.extend((self.src_port >> 8) & 0xff) #High byte
        packet.extend(self.src_port & 0xff) #Low byte

        #dest IP
        ip = self.dest_ip.split('.')
        ip = int(b) for b in ip]
        packet.extend(i) for i in ip

        #dest_port
        packet.extend((self.dest_port >> 1) & 0xff) #High byte
        packet.extend(self.dest_port & 0xff) #Low byte

        #seq_num
        b = [(self.seq >> i) & 0xff for i in (24,16,8,0)]
        packet.extend(i) for i in b

        #num_segs
        b = [(self.num_seg >> i) & 0xff for i in (24,16,8,0)]
        packet.extend(i) for i in b

        #checksum
        packet.extend((self.check >> 1) & 0xff) #High byte
        packet.extend(self.check & 0xff) #Low byte

        #window size
        packet.extend((self.win_size >> 1) & 0xff) #High byte
        packet.extend(self.win_size & 0xff) #Low byte

        #payload size, flags, and unused bit
        packet.extend(self.pay_size >> 1) #High byte
        packet.extend(((self.pay_size & 1) << 7) + (self.flg << 1)) #Low byte (pay_size[1] + flg + unused)

        #payload
        packet.extend(b) for b in payload

        return bytes(packet)
