import sys
from smartcard.System import readers
from smartcard.util import toHexString

def fetch_uid():
    r = readers()
    if not r:
        return "No card readers found."

    reader = r[0]
    connection = reader.createConnection()
    connection.connect()

    command = [0xFF, 0xCA, 0x00, 0x00, 0x00]

    try:
        response, sw1, sw2 = connection.transmit(command)
        if sw1 == 0x90 and sw2 == 0x00:
            uid = toHexString(response).replace(" ", "")  
            return uid  
        else:
            return "Failed to read UID"
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    print(fetch_uid())  
