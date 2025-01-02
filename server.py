import socket
import pickle
import threading
import time

UDP_PORT = 5005
sock = socket.socket(socket.AF_INET,
                     socket.SOCK_DGRAM)
sock.bind(("", UDP_PORT))

clients = {}
clients_lock = threading.Lock()

def HandleSend():
    global clients
    while True:
        with clients_lock:
            current_time = time.time()
            inactive_clients = [key for key, value in clients.items() if current_time - value[4] > 5]
            for key in inactive_clients:
                del clients[key]

        for key in clients:
            data_to_send = []
            for key1 in clients:
                if key1 != key:
                    data_to_send.append([
                        clients[key1][0],
                        clients[key1][1],
                        clients[key1][2],
                        clients[key1][3],
                        clients[key1][4]
                    ])
            data = pickle.dumps([1, data_to_send])
            sock.sendto(data, (key[0], key[1]))
        time.sleep(0.1)

def HandleReceive():
    global clients
    while True:
        data, addr = sock.recvfrom(1024)
        decoded_data = pickle.loads(data)
        if decoded_data[0] == 0:
            with clients_lock:
                if addr in clients:
                    if decoded_data[6] > clients[addr][5]:
                        clients[addr] = [
                            decoded_data[1],
                            decoded_data[2],
                            decoded_data[3],
                            decoded_data[4],
                            decoded_data[5],
                            decoded_data[6]
                        ]
                    else:
                        print("--- Packet rejected ---")
                        print(f"Received ID Packet : {decoded_data[6]}")
                        print(f"Current ID : {clients[addr][5]}")
                else:
                    clients[addr] = [
                        decoded_data[1],
                        decoded_data[2],
                        decoded_data[3],
                        decoded_data[4],
                        decoded_data[5],
                        decoded_data[6]
                    ]

threading.Thread(target=HandleReceive).start()
threading.Thread(target=HandleSend).start()