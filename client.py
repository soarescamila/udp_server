import socket
import os
import base64
import math
from config import PEERS, BUFFER_SIZE, FOLDER, CHUNK_SIZE

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
        print("[CLIENT] Corrupted packet received (checksum mismatch). Discarding...")
        return None, None

    return msg_type, payload

def send_packet(ip, port, msg_type, payload=""):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(2.0)
    packet = create_packet(msg_type, payload)

    try:
        client_socket.sendto(packet.encode('utf-8'), (ip, port))
        data, addr = client_socket.recvfrom(BUFFER_SIZE)
        message = data.decode('utf-8').strip()
        return parse_packet(message)
    
    except socket.timeout:
        print(f"[CLIENT] Timeout waiting for response to '{msg_type} from {ip}:{port}'")
        return None, None

    except Exception as e:
        print(f"[CLIENT] Error sending to {ip}:{port}: {e}")
        return None, None
    finally:
        client_socket.close()


def announce_local_files():
    if not os.path.exists(FOLDER):
        return

    for fname in os.listdir(FOLDER):
        fpath = os.path.join(FOLDER, fname)
        if os.path.isfile(fpath):
            fsize = os.path.getsize(fpath)
            for peer_ip, peer_port in PEERS:
                print(f"[CLIENT] Announcing '{fname} ({fsize} bytes) to {peer_ip}:{peer_port}'")
                resp_type, resp_payload = send_packet(peer_ip, peer_port, "ANNOUNCE",f"{fname} {fsize}")
                if resp_type == "ACK":
                    print(f"[CLIENT] Announcement acknowledged by {peer_ip}:{peer_port}")


def list_files(ip, port):
    resp_type, resp_payload = send_packet(ip, port, "LIST", "")

    if resp_type == "LIST_RESPONSE":
        if resp_payload == "EMPTY" or not resp_payload:
            print(f"[CLIENT] Peer {ip}:{port} has no available files")
            return []

        print(f"[CLIENT] Available files at {ip}:{port}:")
        files = []
        for item in resp_payload.split(','):
            fname, fsize = item.split(':')
            print(f"- {fname} ({fsize} bytes)")
            files.append((fname, fsize))
        return files
    return []

def request_file(ip, port, filename):
    os.makedirs(FOLDER, exist_ok=True)
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(5.0)

    request_packet = create_packet("REQUEST_FILE", filename)
    output_filepath = os.path.join(FOLDER, f"downloaded_{filename}")

    try:
        print(f"[CLIENT] Requesting file '{filename}' from {ip}:{port}")
        client_socket.sendto(request_packet.encode('utf-8'), (ip, port))

        file_handle = None
        receiving = True
        received_chunks = set()
        total_chunks = 0

        while receiving:
            data, addr = client_socket.recvfrom(BUFFER_SIZE)
            message = data.decode('utf-8').strip()
            msg_type, payload = parse_packet(message)

            if msg_type is None:
                continue

            if msg_type == "FILE_START":
                parts = payload.split(' ')
                fname = parts[0]
                file_size = int(parts[1]) if len(parts) > 1 else 0

                total_chunks = math.ceil(file_size / CHUNK_SIZE) if file_size > 0 else 1
                received_chunks.clear()

                print(f"[CLIENT] Starting reception of '{fname}' ({file_size}) bytes, {total_chunks} total chunks")
                file_handle = open(output_filepath, 'wb')

            elif msg_type == "FILE_DATA":
                parts = payload.split(' ')
                chunk_idx = int(parts[0])
                encoded_data = parts[1] if len(parts) > 1 else ""
                chunk_bytes = base64.b64decode(encoded_data.encode('utf-8'))

                if file_handle:
                    offset = chunk_idx * CHUNK_SIZE
                    file_handle.seek(offset)
                    file_handle.write(chunk_bytes)
                    received_chunks.add(chunk_idx)

                    ack_packet = create_packet("ACK", str(chunk_idx))
                    client_socket.sendto(ack_packet.encode('utf-8'), (ip, port))

            elif msg_type == "FILE_END":
                fname = payload
                if len(received_chunks) == total_chunks:
                    print(f"[CLIENT] Transfer completed for '{fname}'! ({len(received_chunks)}/{total_chunks} chunks)")
                else:
                    missing = set(range(total_chunks)) - received_chunks
                    print(f"[CLIENT] Transfer incomplete. Missing chunks: {sorted(list(missing))}")
                receiving = False

            elif msg_type == "ERROR":
                print(f"[CLIENT] Error from server: {payload}")
                receiving = False

    except socket.timeout:
        print(f"[CLIENT] Timeout waiting for file transfer from {ip}:{port}")
    except Exception as e:
        print(f"[CLIENT] Error during file transfer: {e}")
    finally:
        if file_handle:
            file_handle.close()
        client_socket.close()

def delete_and_sync_file(fname):
        file_path = os.path.join(FOLDER, fname)

        delete_local = False

        if os.path.exists(file_path):
            os.remove(file_path)
            delete_local = True

        if delete_local:
            print(f"[CLIENT] Local file '{fname}' removed")
        else:
            print(f"[CLIENT] File '{fname}' not found locally")

        for peer_ip, peer_port in PEERS:
            print(f"[CLIENT] Announcing deletion of '{fname}' to {peer_ip}:{peer_port}")
            resp_type, resp_payload = send_packet(peer_ip, peer_port, "DELETE", fname)
            if resp_type == "ACK":
                print(f"[CLIENT] Deletion of '{fname}' acknowledged by {peer_ip}:{peer_port}")


if __name__ == "__main__":
    print("--- 1. Announcing local files in temp/ ---")
    announce_local_files()

    print("\n--- 2. Syncing file deletion across network ---")
    delete_and_sync_file("sample.txt")

    print("\n--- 3. Verifying updated file list ---")
    list_files("127.0.0.1", 5000)