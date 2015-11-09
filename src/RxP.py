import socket
import hashlib
import random
import string
import math
import time

CLIENT = 0
SERVER = 1
MAX_PAYLOAD = 498

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
    return conn

"""
A Connection object: equivalent to UNIX socket, but 
with functionality that fits RxP
"""
class Connection(object):
    def __init__(self, sock, p_type, other_addr = ""):
        self.last_sent = 0
    """
    Returns True for good handshake, False for bad
    """
    def _handshake(self):
        return _client_handshake() if self.p_type == CLIENT else _server_handshake()

    def _client_handshake(self):
        self._send(SYN)

    def send(self, message):
        pass

    def _send(self, p_type):
        packet = _packetize(p_type)
        #Error checking and retries and other stuff
        self.sock.send(packet)

    def _packetize(self, p_type, data = ""):
        packets = []

        #segment payload
        payload = [""]
        if len(data) > 0:
            data = data.encode('utf-8')
            d = ''.join(str(hex(i))[2:] for i in data)
            payload = list((d[0+i:(MAX_PAYLOAD*2)+i] for i in range(0, len(d), MAX_PAYLOAD*2)))
        num_seg = len(payload)
        for i in range(num_seg):
            #header
            header = ""
            fields = []
            my_ip, my_port = self.sock.getsockname()
            my_ip = my_ip.split('.')
            for b in my_ip:
                fields.append((b, 1*8)) #src ip
            fields.append((my_port, 2*8)) #src port
            o_ip = self.other_addr[0].split('.')
            for b in o_ip:
                fields.append((b, 1*8)) #dest ip
            fields.append((self.other_addr[1], 2*8)) #dest port
            fields.append((last_sent + 1 + i, 4*8)) #seq
            fields.append((num_seg, 4*8)) #num seg
            fields.append((0, 2*8)) #checksum
            fields.append((1, 2*8)) #win size
            fields.append((len(payload[i]), 9)) #payload size
            fields.append((p_type, 6)) #flags
            fields.append((0, 1)) #unused

            for field in fields:
                bin_field = str(bin(int(field[0])))[2:]
                header += '0'*(field[1] - len(bin_field)) + bin_field
            header = hex(int(header,2))[2:0]
            packet = header + payload[i]
            _checksum(packet)

    def _checksum(self, packet):
        words = list((packet[0+i:(4)+i] for i in range(0, len(packet), 4)))
        words = [int(i, 16) for i in words]
        total = sum(words)
        total = bin(total)[2:]
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
        return checksum #change