import socket
import pickle
import threading
import time

UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", UDP_PORT))

clients = {}
clients_lock = threading.Lock()
running = True

def clean_inactive_clients():
    current_time = time.time()
    to_remove = []
    for key, value in clients.items():
        if current_time - value[5] > 5:
            to_remove.append(key)
    for key in to_remove:
        del clients[key]

def HandleSend():
    while running:
        with clients_lock:
            clean_inactive_clients()
            for client_addr in clients:
                data_to_send = []
                for other_client, client_data in clients.items():
                    if other_client != client_addr:
                        data_to_send.append([
                            client_data[0],
                            client_data[1],
                            client_data[2],
                            client_data[3],
                            client_data[4],
                            0.0,
                            client_data[5],
                        ])
                data = pickle.dumps([1, data_to_send])
                sock.sendto(data, client_addr)
        time.sleep(1 / 60)


def HandleReceive():
    global clients
    while running:
        data, addr = sock.recvfrom(1024)
        decoded_data = pickle.loads(data)
        if decoded_data[0] == 0:
            with clients_lock:
                if addr in clients:
                    if decoded_data[7] > clients[addr][6]:
                        clients[addr] = [
                            decoded_data[1],
                            decoded_data[2],
                            decoded_data[3],
                            decoded_data[4],
                            decoded_data[5],
                            time.time(),
                            decoded_data[7]
                        ]
                else:
                    clients[addr] = [
                        decoded_data[1],
                        decoded_data[2],
                        decoded_data[3],
                        decoded_data[4],
                        decoded_data[5],
                        time.time(),
                        decoded_data[7]
                    ]

send_thread = threading.Thread(target=HandleSend)
receive_thread = threading.Thread(target=HandleReceive)
send_thread.start()
receive_thread.start()


print("Server running...")
try:
    while running:
        time.sleep(1/60)
except KeyboardInterrupt:
    running = False
    send_thread.join()
    receive_thread.join()
    sock.close()