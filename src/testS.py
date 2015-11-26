import socket
import RxP
from RxP import Connection, _Packet, SERVER, PKT_SIZE

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("localhost", 5001))

c = Connection(s, SERVER, ('127.0.0.1', 5000))
c.win_size = 1

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
    p.pay_size = len(b)
    p.payload = b
    p = c._checksum(p)
    c._send(p)
    print("Packet sent!")
    s.recvfrom(RxP.PKT_SIZE)

    #Test _recv bad checksum
    p.check += 30
    c._send(p)
    s.recvfrom(RxP.PKT_SIZE)


    #Test send and recv
    print("Got a message")
    m = c.recv(len("Lorem ipsum dolor set."*20))
    print(str(m))
    print(len(m))
    print("Echoing to client")
    sent = c.send(m)
    print("Message echoed:", str(sent))