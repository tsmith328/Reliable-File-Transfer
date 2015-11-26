import socket
import RxP
from RxP import Connection, _Packet, SERVER, PKT_SIZE

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("localhost", 5001))

c = Connection(s, SERVER, ('127.0.0.1', 5000))
c.win_size = 1

while True:

    #Test send and recv
    print("Waiting for message.")
    m = c.recv(len("Lorem ipsum dolor set."*40))
    print("Got a message")
    print(str(m))
    print(len(m))
    print("Echoing to client")
    sent = c.send(m)
    print("Message echoed:", str(sent))