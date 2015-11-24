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

#Packet p_types
ACK = 0b100000
NACK = 0b010000
SYN = 0b001000
FIN = 0b000100
DATA = 0b000010
RST = 0b000001

server_conn = None
connections = queue.Queue()


def connect(address):
    """
    Attempts to connect to the server located at address.
    Params:
        address -- a tuple: (ip_address (str), port_number (str or int))
    Returns:
        A Connection to this server, or None if it cannot connect.
    """
    try:
        port = int(address[1])
        address = (address[0], port)
    except ValueError:
        return None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(address)
        conn = Connection(sock, CLIENT, address)
        return conn if conn._handshake() else None
    except socket.error:
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
    except socket.error as e:
        print(e)
        return False

class _Listener(threading.Thread):
    def __init__(self, connection, connection_list):
        self.connection = connection
        self.connection_list = connection_list

    def run(self):
        while True:
            pkt = self.connection._recv()
            if pkt.flags == SYN:
                self.connection.other_addr = pkt.src_ip #Necessary?
                if self.connection._handshake():
                    c = Connection(s, SERVER)
                    connection_list.put(c)

def accept():
    """
    Accepts a connection from a client and starts the session.
    Returns:
        a Connection to the client
    """
    while len(connections) < 1:
        time.sleep(1)
    conn = connections.get(0)
    conn.other_addr = conn.sock.getpeername()
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


    def _handshake(self):
        """
        Returns True for good handshake, False for bad
        """
        return _client_handshake() if self.p_type == CLIENT else _server_handshake()

    def _client_handshake(self):
        """
        Client handshake (see state diagram)
        Returns:
            bool - True for good handshake, False for bad
        """
        self._send(SYN) #Send SYN
        eq_addr = False
        corr_pkt = False
        pkt_type = SYN | ACK | DATA
        count = 0
        while not eq_addr and not corr_pkt and count < MAX_RETRIES:
            try:
                syn_ack_data = self._recv()
                if syn_ack_data.src_ip == other_addr:
                    eq_addr = True
                if pkt_type == syn_ack_data.flags:
                    corr_pkt = True
                else:
                    pass #nack
            except socket.timeout:
                return False
        addr_tup = self.sock.getsockname()
        to_hash = syn_ack_data.data + str(addr_tup[0]) + str(addr_tup[1])
        hashed = _make_hash(to_hash)
        #TODO-send syn+ack with hash
        count = 0
        while count < MAX_RETRIES:
            try:
                success = self._recv()
                if success.src_ip == other_addr:
                    if success.flags == ACK:
                        return True
                    elif success.flags == NACK:
                        return False
                    else:
                        pass #nack
            except socket.timeout:
                return False

    def _server_handshake(self):
        """
        Server handshake (see state diagram)
        Returns:
            bool - True for good handshake, False for bad
        """
        #Assuming we have received a SYN packet from a client
        key = self._gen_key()
        pkt_type = SYN | ACK | DATA
        #send syn ack data packet with key

        corr_pkt = False
        pkt_type = SYN | ACK
        count = 0
        while not corr_pkt and count < MAX_RETRIES:
            try:
                syn_ack = self._recv()
                if syn_ack.flags == pkt_type:
                    to_hash = key + syn_ack.src_ip + syn_ack.src_port
                    serv_hash = _make_hash(to_hash)
                    if serv_hash == syn_ack.payload:
                        self._send(ACK)
                        return True
                    else:
                        self._send(NACK)
                        return False
                else:
                    self._send(NACK)
            except socket.timeout:
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
            hashed - hashed Message
        """
        m = hashlib.md5()
        m.update(to_hash.encode('utf-8'))
        return m.hexdigest()

    def send(self, message):
        """
        Reliably sends a message across the connection.
        Will retry MAX_RETRIES times before reporting failure.
        Params:
            message -- The message to send.
        Returns:
            True if the message was successfully sent, False otherwise.
        """
        msgsize = len(message)
        if msgsize < 0:
            return False
        else:
            packets = self._packetize(DATA, message)
            try:
                need_ack = queue.Queue()
                nack_list = queue.Queue()
                #curr_window = []
                ack_listener = _Ack_Listener(self.sock, need_ack, nack_list)
                ack_listener.start()
                while len(packets) > 0:
                    if len(need_ack) < win_size:
                        to_send = packets.pop(0)
                        need_ack.put(to_send)
                        self._send(to_send.encode(), to_send.dest_ip)
                    if len(nack_list > 0):
                        for nacked in nack_list:
                            if nacked in need_ack:
                                self._send(nacked.encode(), nacked.dest_ip)
                return True
            except socket.error as e:
                print("Socket error: " + e)
                return False
            except Exception as e:
                print("Exception: " + e)
                return False


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


    def _send(self, packet, dest, seq_num=None, p_type=DATA, data=""):
        """
        Internal method for sending non-data packets
        """
        if p_type == DATA:
            self.sock.sendto(packet.encode(), dest)
        else:
            packet = _packetize(p_type, data)
            if seq_num:
                packet[0].seq = seq_num
            self.sock.sendto(packet[0], dest)


    def _packetize(self, p_type, data = ""):
        """
        Splits a data string into packets with payloads of MAX_PAYLOAD length.
        Returns:
            a list of packets
        """
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


    def recv(self, msgsize=MAX_PAYLOAD):
        """Receive data as a list of packets
        Params:
            msgsize - size of message to receive
        Returns:
            ret - message as bytes array encoded in hex
        """
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



    def _recv(self, pkt_size=PKT_SIZE):
        """Internal method to receive a packet
        Params:
            pkt_size - size of packet to receive (default PKT_SIZE)
        Returns:
            pkt - A Packet object (None if socket connection broken)
        """
        chunks = []
        bytes_recd = 0
        checksum_match = False
        while not checksum_match:
            while bytes_recd < pkt_size:
                try:
                    chunktuple = self.sock.recvfrom(pkt_size - bytes_recd)
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
            checksum_match = self._validate(pkt_object)
            if not checksum_match:
                self._send(NACK)
                return None
        return pkt_object



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
        packet = self._checksum(packet)
        return True if packet.check == 0 else False

    def close(self):
        """
        Close the connection
        """
        pass

class _Ack_Listener(threading.Thread):
    """
    Threadable inner class for handling ACKS and NACKS for a sliding window
    protocol
    """
    def __init__(self, conn, ack_list, nack_list):
        """
        Constructor for Ack_Listener object
        Params:
            conn - Connection to receive on
            ack_list - list of packet objects that need acks
            nack_list - list of packet objects which have been nacked
        """
        self.ack_list = ack_list
        self.nack_list = nack_list
        self.conn = conn

    def run(self):
        pkt_object = conn._recv()
        if pkt_object.flags == ACK:
            for pakt in need_ack:
                if pakt.seq == pkt_object.seq:
                    need_ack.get(pakt)
        elif pkt_object.flags == NACK:
            for pakt in need_ack:
                if pakt.seq == pkt_object.seq:
                    nack_list.put(pakt)
        else:
            pass
            #TODO: give to correct connection

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
        return len(self.encode())

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

        return bytes(packet)
