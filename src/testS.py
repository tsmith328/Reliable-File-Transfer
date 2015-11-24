import socket
import RxP
from RxP import Connection, _Packet, SERVER, PKT_SIZE

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("localhost", 5001))

c = Connection(s, SERVER, '')

while True:
    #Test _send
    print("Waiting for packets...")
    msg, addr = s.recvfrom(PKT_SIZE)
    print("Got a packet!")
    pkt = _Packet(msg)
    b = bytearray("Hello, World!", 'utf-8') + bytearray(b'\0'*(486-len(bytearray("Hello, World!",'utf-8'))))
    b1 = bytearray("Hello, World!", 'utf-8')
    good = b == pkt.payload
    if good:
        print("Good packet. Sending ok.")
        s.sendto(b'1', addr)
    else:
        print("Bad packet. Sending no.")
        s.sendto(b'0', addr)

    #Test _recv
    print("Sending a packet...")
    p = _Packet()
    p.src_ip = '127.0.0.1'
    p.src_port = 5001
    p.dest_ip = addr[0]
    p.dest_port = int(addr[1])
    p.pay_size = len(b1)
    p.payload = b1
    p = c._checksum(p)
    print(p)
    s.sendto(p.encode(), addr)
    print("Packet sent!")

    #Test _recv bad checksum
    p.check += 30
    s.sendto(p.encode(), addr)