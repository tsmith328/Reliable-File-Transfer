import socket
import RxP
from RxP import Connection, _Packet
from difflib import Differ

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("localhost", 5000))
c = Connection(s, RxP.CLIENT, ('127.0.0.1', 5001))
p = RxP._Packet()
c.win_size = 1

#Script to test functionality of various methods
#Set up packet
p.src_ip = '192.168.1.1'
p.dest_ip = '192.168.1.4'
p.src_port = 6554
p.dest_port = 6555
p.seq = 400
p.num_seg = 403
p.win_size = 30
p.pay_size = len(bytearray("Hello, World!", 'utf-8'))
p.flg = RxP.ACK | RxP.DATA
p.payload = bytearray("Hello, World!", 'utf-8') + bytearray(b'\0'*(486-len(bytearray("Hello, World!",'utf-8'))))

#Test checksum and validate
p = c._checksum(p)
val = c._validate(p)
print("Checksum and Validate Passed!" if val else "Checksum and Validate failed!")

#Test Packet constructor, encode, __len__, and __repr__
q = _Packet(p.encode())
print("Init, str, len Passed!" if len(q) == len(p) and str(q)==str(p) else "Init, str, len Failed!")

#Tests get and set window
win = 500
c.setWindow(500)
print("Get/Set Window Passed!" if c.getWindow() == win else "Get/Set Window Failed!")

#Testing _send
c._send(p)
msg, addr = s.recvfrom(1)
print("_send Passed!" if msg == b'1' else "_send Failed!")

#Testing _recv
pkt = c._recv()
if not pkt:
    print("_recv Failed! (None)")
else:
    print("_recv Passed!" if pkt.payload[:13] == bytearray("Hello, World!", 'utf-8') else "_recv Failed!")

#Testing _recv with bad checksum
pkt = c._recv()
if pkt == None:
    print("_recv corruption test Passed!")
else:
    print("_recv corruption test Failed!")

#Testing send and receive
print("Testing send and recv")
message = "Lorem ipsum dolor set."*40
mess = message.encode()
sent = c.send(mess)
print("Sent message:", str(sent))
mess2 = c.recv(len(mess))
print("Got message")
print(mess)
print(mess2)
print("Send and recv passed!" if sent and mess == mess2 else "Send and recv failed!")
