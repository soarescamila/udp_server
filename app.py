import threading
import time
import sys
from server import start_server
from client import announce_local_files, sync_new_peer

def run():
    print("="* 20 + " STARTING UDP SERVER " + "="*20)

    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    time.sleep(1)

    announce_local_files()
    sync_new_peer()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("/n Ending UDP server...")
        sys.exit(0)

if __name__ == "__main__":
    run()