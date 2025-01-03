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
        if current_time - value[-1] > 5:
            to_remove.append(key)
    for key in to_remove:
        del clients[key]


def HandleReceive():
    global clients
    while running:
        data, addr = sock.recvfrom(1024)
        decoded_data = pickle.loads(data)
        current_time = time.time()

        if decoded_data[0] == 0:
            with clients_lock:
                if addr in clients:
                    if decoded_data[-2] > clients[addr][-2]:
                        clients[addr] = [
                            decoded_data[1],  # x position
                            decoded_data[2],  # y position
                            decoded_data[3],  # z position
                            decoded_data[4],  # x rotation
                            decoded_data[5],  # y rotation
                            decoded_data[6],  # z rotation
                            decoded_data[7],  # send_id
                            current_time  # timestamp
                        ]
                else:
                    clients[addr] = [
                        decoded_data[1],  # x position
                        decoded_data[2],  # y position
                        decoded_data[3],  # z position
                        decoded_data[4],  # x rotation
                        decoded_data[5],  # y rotation
                        decoded_data[6],  # z rotation
                        decoded_data[7],  # send_id
                        current_time  # timestamp
                    ]


def HandleSend():
    while running:
        with clients_lock:
            clean_inactive_clients()
            for client_addr in clients:
                data_to_send = []
                for other_client, client_data in clients.items():
                    if other_client != client_addr:
                        data = [
                            client_data[0], # x position
                            client_data[1], # y position
                            client_data[2], # z position
                            client_data[3], # x rotation
                            client_data[4], # y rotation
                            client_data[5], # z rotation
                            client_data[6], # send_id
                            time.time() # timestamp
                        ]
                        data_to_send.append(data)
                data = pickle.dumps([1, data_to_send])
                sock.sendto(data, client_addr)
        time.sleep(1 / 60)

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