import threading
import time
import sys
import os
from udp.server import start_server
from udp.client import announce_local_files, sync_new_peer, show_dashboard, delete_and_sync_file
from udp.config import FOLDER

def folder_monitor():
    os.makedirs(FOLDER, exist_ok=True)
    known_files = set(os.listdir(FOLDER))

    while True:
        time.sleep(2)
        if not os.path.exists(FOLDER):
            continue

        current_files = set(os.listdir(FOLDER))

        added_files = current_files - known_files
        if added_files:
            announce_local_files()
            show_dashboard()
            known_files = current_files

        deleted_files = known_files - current_files
        if deleted_files:
            for fname in deleted_files:
                delete_and_sync_file(fname)
            show_dashboard()
            known_files = current_files


def run():
    print("STARTING UDP SERVER")

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    time.sleep(1)

    announce_local_files()
    sync_new_peer()

    monitor_thread = threading.Thread(target=folder_monitor, daemon=True)
    monitor_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("/n Ending UDP server...")
        sys.exit(0)

if __name__ == "__main__":
    run()