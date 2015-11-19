import socket
import RxP
from RxP import Connection

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('www.google.com',80))
c = Connection(s, RxP.CLIENT)
p = RxP._Packet()
p.src_ip = '192.168.1.1'
p.dest_ip = '192.168.1.4'
p.src_port = 6554
p.dest_port = 6555
p = c._checksum(p)

print s.getsockname()

print len(str(p))
print p