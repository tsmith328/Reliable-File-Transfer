import socket
import argparse
import hashlib
import random
import string
import math

"""
Attemps to connect to the server located at address.
Params: address -- a tuple: (ip_address, port_number)
Returns: A Connection to this server, or None if it cannot connect.
"""
def connect(address):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

"""

"""
def listen(port):
    pass

"""

"""
def accept():
    pass

"""
A Connection object: equivalent to UNIX socket, but 
with functionality that fits RxP
"""
class Connection(Object):
