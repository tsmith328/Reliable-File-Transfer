import threading
import RxP
import queue

#Endpoint types
CLIENT = 0
SERVER = 1

class Command_Parser(object):
    def __init__(self, X, A, P, conn=None):
        self.type = SERVER if conn else CLIENT
        self.X = X
        self.P = P
        self.A = A
        self.conn = conn
        self.cmd_queue = queue.Queue()
        self.thread = client_thread(self.conn, self.cmd_queue) if self.type == CLIENT else server_thread(self.conn, self.cmd_queue)
        self.thread_started = False

    def start_conn_thread(self):
        self.thread.start()
        self.thread_started = True

    def parse_command(self, inp):
        inp_list = inp.split(' ')
        if len(inp) > 2:
            print("Invalid syntax")
        cmd = inp_list[0].lower()
        param = inp_list[1]
        if self.type == CLIENT:
            cmds = ["get", "post", "connect", "window", "disconnect"]
            if cmd != "connect" and not self.conn:
                print("You need to connect first!")
            elif cmd == connect:
                print("Connecting...")
                self.conn = RxP.connect((A, P), X)
                if self.conn:
                    print("Connected!")
                    self.start_conn_thread()
                else:
                    print("Connection Failed")
            elif cmd == "window":
                try:
                    win = int(param)
                    self.cmd_queue.put(inp)
                    print("Window set to: " + param)
                except:
                    print("Invalid window size!")
            elif cmd == "disconnect":
                print("Attempting to close the connection")
                self.cmd_queue.put(inp)
            elif cmd == "get" or cmd == "post":
                print(cmd + " for file: " + param)
                msg = cmd + " " + param
                #spawn thread for sending
            else:
                print("Invalid command: " + cmd)
                print("Valid commands: ")
                for c in cmds:
                    print(c, end=' ')
                print("")
        elif self.type == SERVER:
            cmds = ["window", "terminate"]
            if cmd == "window":
                try:
                    win = int(param)
                    self.conn.setWindow(win)
                    print("Window set to: " + param)
                except:
                    print("Invalid window size!")
            elif cmd == "terminate":
                print("Attempting to close the connection")
                self.conn.close()
                print("Connection closed")

class server_thread(threading.thread):
    def __init__(self, conn, cmd_queue):
        threading.thread.__init__()
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
                            self.conn.send(sendfile.read())
                    except Exception as e:
                        print("Error: " + e)
                elif cmd == "post":
                    try:
                        with open(param, 'wb') as recfile:
                            recfile.write(self.conn.recv(int(param2)))
                    except Exception as e:
                        print("Error: " + e)

class client_thread(threading.thread)
    def __init__(self, conn, cmd_queue):
        threading.thread.__init__()
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
                    size = self.conn.recv()
                    try:
                        size = int(size.decode('utf-8'))
                        with open(cmdlist[1], 'wb') as recfile:
                            recfile.write(self.conn.recv(size))
                    except Exception as e:
                        print("Error: " + e)
