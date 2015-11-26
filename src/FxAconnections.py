import threading
import RxP
import queue

#Endpoint types
CLIENT = 0
SERVER = 1

class Command_Parser(object):
    """
    Object to handle parsing of commands from FxA-server and FxA-client
    """
    def __init__(self, X, A, P, conn=None):
        self.type = SERVER if conn else CLIENT
        self.X = X #arguments passed in through CLI
        self.P = P
        self.A = A
        self.conn = conn
        self.cmd_queue = queue.Queue()
        self.thread = None if self.type == CLIENT else server_thread(self.conn, self.cmd_queue)

    def start_conn_thread(self, conn=None):
        """Starts a thread for the connection"""
        if conn:
            self.thread = client_thread(conn, self.cmd_queue)
        self.thread.start()

    def parse_command(self, inp):
        """Parses a command
        Params:
            inp - command input (string)
        """
        inp_list = inp.split(' ')
        if len(inp_list) > 2:
            print("Invalid syntax")
        cmd = inp_list[0].lower()
        param = inp_list[1] if len(inp_list) > 1 else None
        if self.type == CLIENT:
            cmds = ["get", "post", "connect", "window", "disconnect"]
            if cmd != "connect" and not self.conn and cmd != "disconnect":
                print("You need to connect first!")
            elif cmd == "connect":
                print("Connecting...")
                self.conn = RxP.connect((self.A, self.P), self.X)
                if self.conn:
                    print("Connected!")
                    self.start_conn_thread()
                else:
                    print("Connection Failed")
            elif cmd == "window":
                try:
                    win = int(param)
                    self.cmd_queue.put(inp)
                except:
                    print("Invalid window size!")
            elif cmd == "disconnect":
                print("Attempting to close the connection")
                self.cmd_queue.put(inp)
                for i in range(5):
                    if not self.cmd_queue.empty():
                        time.sleep(1)
                if not self.cmd_queue.empty():
                    print("Server took too long to close gracefully, exiting...")
                return False
            elif cmd == "get" or cmd == "post":
                print(cmd + " for file: " + param)
                msg = cmd + " " + param
                self.cmd_queue.put(msg)
            else:
                print("Invalid command: " + cmd)
                print("Valid commands: ")
                for c in cmds:
                    print(c, end=' ')
                print("")
            return True
        elif self.type == SERVER:
            cmds = ["window", "terminate"]
            if cmd == "window":
                try:
                    win = int(param)
                    self.cmd_queue.put(inp)
                except:
                    print("Invalid window size!")
            elif cmd == "terminate":
                print("Attempting to close the connection")
                self.cmd_queue.put(inp)
                for i in range(5):
                    if not self.cmd_queue.empty():
                        time.sleep(1)
                if not self.cmd_queue.empty():
                    print("Client took too long to close gracefully, exiting...")
                return False
            return True

class server_thread(threading.Thread):
    """Thread for file transfer server"""
    def __init__(self, conn, cmd_queue):
        threading.Thread.__init__(self)
        self.conn = conn
        self.cmd_queue = cmd_queue

    def run(self):
        while True:
            ext_cmd = self.cmd_queue.get()
            if ext_cmd:
                cmdlist = ext_cmd.split(' ')
                cmd = cmdlist[0]
                if cmd == "window":
                    self.conn.setWindow(cmdlist[1])
                    print("Window size set to " + str(cmdlist[1]))
                    self.cmd_queue.task_done()
                elif cmd == "terminate":
                    self.conn.close()
                    self.cmd_queue.task_done()
                    break
            else:
                bmsg = conn.recv()
                msg = bmsg.decode('utf-8').split(' ')
                cmd = msg[0]
                param1 = msg[1]
                if len(msg > 2):
                    param2 = msg[2].strip()
                if cmd == "get":
                    try:
                        with open(param, 'rb') as sendfile:
                            self.conn.send(len(sendfile.read()).encode('utf-8'))
                            self.conn.send(sendfile.read())
                    except Exception as e:
                        print("Error: " + e)
                    self.cmd_queue.task_done()
                elif cmd == "post":
                    try:
                        with open(param, 'wb') as recfile:
                            self.conn.send("ACK".encode('utf-8'))
                            recfile.write(self.conn.recv(int(param2)))
                    except Exception as e:
                        print("Error: " + e)
                    self.cmd_queue.task_done()

class client_thread(threading.Thread):
    """Thread for client file transfer"""
    def __init__(self, conn, cmd_queue):
        threading.Thread.__init__(self)
        self.conn = conn
        self.cmd_queue = cmd_queue

    def run(self):
        while True:
            ext_cmd = self.cmd_queue.get()
            if ext_cmd:
                cmdlist = ext_cmd.split(' ')
                cmd = cmdlist[0]
                if cmd == "window":
                    self.conn.setWindow(cmdlist[1])
                    print("Window size set to " + str(cmdlist[1]))
                    self.cmd_queue.task_done()
                elif cmd == "disconnect":
                    self.conn.close()
                    self.cmd_queue.task_done()
                    break
                elif cmd == "get":
                    self.conn.send(ext_cmd.encode('utf-8'))
                    size = self.conn.recv()
                    try:
                        size = int(size.decode('utf-8'))
                        with open(cmdlist[1], 'wb') as recfile:
                            recfile.write(self.conn.recv(size))
                    except Exception as e:
                        print("Error: " + e)
                    self.cmd_queue.task_done()
                elif cmd == "post":
                    self.conn.send(ext_cmd.encode('utf-8'))
                    ack = self.conn.recv()
                    ack = ack.decode('utf-8')
                    if ack == "ACK":
                        try:
                            with open(cmdlist[1], 'wb') as recfile:
                                recfile.write(self.conn.recv(size))
                        except Exception as e:
                            print("Error: " + e)
                    else:
                        print("Server refused file")
                    self.cmd_queue.task_done()
