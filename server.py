import socket
import os
import base64
from config import IP, PORT, BUFFER_SIZE, CHUNK_SIZE, FOLDER, ACK_TIMEOUT, MAX_RETRIES

files_list = {}

def calculate_checksum(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    b = data if len(data) % 2 == 0 else data + b"\x00"
    s = sum((b[i] << 8) | b[i+1] for i in range(0, len(b), 2))
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return (~s) & 0xFFFF

def create_packet(msg_type, payload=""):
    body = f"{msg_type} {payload}".strip() if payload else msg_type
    chk = calculate_checksum(body)
    return f"{chk} {body}"

def parse_packet(data):
    parts = data.strip().split(' ', 2)
    if len(parts) < 2:
        return None, None
    try:
        recv_chk = int(parts[0])
    except ValueError:
        return None, None

    msg_type = parts[1]
    payload = parts[2] if len(parts) > 2 else ""

    body = f"{msg_type} {payload}".strip() if payload else msg_type
    if calculate_checksum(body) != recv_chk:
        print("[SERVER] Corrupted packet received (checksum mismatch). Discarding...")
        return None, None

    return msg_type, payload

def get_local_files():
    files = []
    if os.path.exists(FOLDER):
        for fname in os.listdir(FOLDER):
            fpath = os.path.join(FOLDER, fname)
            if os.path.isfile(fpath):
                files.append(f"{fname}: {os.path.getsize(fpath)}")
    return ",".join(files)

def handle_request_file(filename, addr, server_socket):
    file_path = os.path.join(FOLDER, filename)

    if not os.path.exists(file_path):
        error_packet = create_packet("ERROR", f"File '{filename}'not found")
        server_socket.sendto(error_packet.encode('utf-8'), addr)
        print(f"[SERVER] File '{filename}' not found.")
        return

    file_size = os.path.getsize(file_path)

    # FILE_START
    file_start = create_packet("FILE_START", f"{filename} {file_size}")
    server_socket.sendto(file_start.encode('utf-8'), addr)
    print(f"[SERVER] Sent 'FILE_START' for {filename}' ({file_size} bytes)")

    # FILE_DATA chunks
    chunck_idx = 0
    with open(file_path, 'rb') as f:
        while True:
            chunk_data = f.read(CHUNK_SIZE)
            if not chunk_data:
                break

            encoded_data = base64.b64encode(chunk_data).decode('utf-8')
            file_data_packet = create_packet("FILE_DATA", f"{chunck_idx} {encoded_data}")
            
            # Stop-and-Wait
            ack_received = False
            retries = 0

            while not ack_received and retries < MAX_RETRIES:
                server_socket.sendto(file_data_packet.encode('utf-8'), addr)
                
                try:
                    server_socket.settimeout(ACK_TIMEOUT)
                    data, addr = server_socket.recvfrom(BUFFER_SIZE)
                    message = data.decode('utf-8').strip()
                    msg_type, payload = parse_packet(message)

                    if msg_type == "ACK" and payload == str(chunck_idx):
                        ack_received = True
                
                except socket.timeout:
                    retries += 1
                    print(f"[SERVER] Timeout waiting for ACK {chunck_idx}, retrying...")

            if not ack_received:
                print(f"[SERVER] Transfer failed: MAX_RETRIES reached for chunk {chunck_idx}.")
                server_socket.settimeout(None)
                return
                
            chunck_idx += 1

    server_socket.settimeout(None)

    # FILE_END
    file_end_packet = create_packet("FILE_END", filename)
    server_socket.sendto(file_end_packet.encode('utf-8'), addr)
    print(f"[SERVER] Sent 'FILE_END' for '{filename}'")


def start_server():
    os.makedirs(FOLDER, exist_ok=True)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((IP, PORT))
    print(f"[SERVER] Server listening on {IP}:{PORT}")

    while True:
        data, addr = server_socket.recvfrom(BUFFER_SIZE)
        message = data.decode('utf-8').strip()

        if not message:
            continue

        msg_type, payload = parse_packet(message)
        
        if msg_type is None:
            continue

        if msg_type == "ANNOUNCE":
            parts = payload.split(' ')
            if len(parts) >= 2:
                fname, fsize = parts[0], parts[1]
                files_list[fname] = {'size': fsize, 'peer': addr}
                print(f"[SERVER] Registered announced file '{fname}' ({fsize}) bytes")
                ack_response = create_packet("ACK", f"ANNOUNCE {fname}")
                server_socket.sendto(ack_response.encode('utf-8'), addr)

        elif msg_type == "LIST":
            local_list = get_local_files()
            response = create_packet("LIST_RESPONSE", local_list if local_list else "EMPTY")
            server_socket.sendto(response.encode('utf-8'), addr)
            print(f"[SERVER] Sent local file list to {addr}")

        elif msg_type == "REQUEST_FILE":
            filename = payload.strip()
            handle_request_file(filename, addr, server_socket)

        
        elif msg_type == "DELETE":
            fname = payload.strip()
            if fname in files_list:
                del files_list[fname]

            file_path = os.path.join(FOLDER, fname)

            deleted = False
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted = True
            
            if deleted:
                print(f"[SERVER] File '{fname} deleted locally'")
            else:
                print(f"[SERVER] Delete request received for '{fname}', but file was not found.")

            ack_response = create_packet("ACK", f"DELETE {fname}")
            server_socket.sendto(ack_response.encode('utf-8'), addr)
        
        
        elif msg_type == "ERROR":
            print(f"[SERVER] Received ERROR report from {addr}: {payload}")
        

if __name__ == "__main__":
    start_server()