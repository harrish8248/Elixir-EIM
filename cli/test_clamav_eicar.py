import socket
import struct

EICAR_STRING = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def connect_clamav(host: str = "localhost", port: int = 3310) -> socket.socket:
    # Resolve using getaddrinfo to support both IPv6 and IPv4
    addrinfo = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    last_err = None
    for family, socktype, proto, canonname, sockaddr in addrinfo:
        try:
            s = socket.socket(family, socktype, proto)
            s.settimeout(5)
            s.connect(sockaddr)
            return s
        except Exception as e:  # noqa: BLE001 — intentional: try each addrinfo entry
            last_err = e
            continue
    raise last_err or RuntimeError(f"Could not connect to {host}:{port}")


def ping_clamav() -> str:
    s = connect_clamav()
    with s:
        s.sendall(b"PING\n")
        res = s.recv(1024)
        return res.decode("utf-8", errors="replace").strip()


def scan_buffer(payload: bytes) -> str:
    s = connect_clamav()
    with s:
        s.sendall(b"zINSTREAM\0")
        chunk_len = struct.pack(">I", len(payload))
        s.sendall(chunk_len + payload)
        s.sendall(struct.pack(">I", 0))

        response = b""
        while True:
            data = s.recv(1024)
            if not data:
                break
            response += data
            if b"\0" in response or b"\n" in response:
                break
        return response.decode("utf-8", errors="replace").strip("\0\n\r ")


def main() -> None:

    print("=== CLAMAV ANTIVIRUS & MALWARE SCANNER VERIFICATION ===")

    # 1. PING test
    pong = ping_clamav()
    print(f"[OK] ClamAV PING response: '{pong}' (Expected: 'PONG')")
    assert pong == "PONG", f"Unexpected response: {pong}"

    # 2. Clean business document payload scan
    clean_text = b"Confidential Contract - AcroCorp 2026. This file is clean."
    clean_res = scan_buffer(clean_text)
    print(f"[OK] Clean payload scan result: '{clean_res}'")
    assert "OK" in clean_res, f"Clean payload check failed: {clean_res}"

    # 3. EICAR virus test string scan
    eicar_res = scan_buffer(EICAR_STRING)
    print(f"[OK] EICAR payload scan result: '{eicar_res}'")
    assert "FOUND" in eicar_res, f"EICAR detection failed: {eicar_res}"

    print(
        "\n[SUCCESS] ClamAV daemon is live, responding on port 3310, and successfully caught the EICAR test signature."
    )


if __name__ == "__main__":
    main()
