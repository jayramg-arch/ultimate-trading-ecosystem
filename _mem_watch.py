"""Background memory-leak watcher. Samples nonpaged pool (total + NtFC tag),
available RAM, and commit every 60s; appends to _mem_watch_log.csv and prints.
Lets us SEE the leak climb and prove which app/driver drives it (stop a suspect,
watch the slope flatten). Read-only. Ctrl-C or kill to stop."""
import ctypes, struct, time, datetime, csv, os
from ctypes import wintypes

ntdll = ctypes.WinDLL("ntdll")
NtQuerySystemInformation = ntdll.NtQuerySystemInformation
NtQuerySystemInformation.restype = ctypes.c_long
SystemPoolTagInformation = 22
MISMATCH = -1073741820

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

def mem_status():
    m = MEMORYSTATUSEX(); m.dwLength = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m

def pool_snapshot():
    length = 4 * 1024 * 1024
    ret = ctypes.c_ulong(0); buf = ctypes.create_string_buffer(length)
    status = NtQuerySystemInformation(SystemPoolTagInformation, buf, length, ctypes.byref(ret))
    tries = 0
    while status == MISMATCH and tries < 10:
        length = ret.value + 65536; buf = ctypes.create_string_buffer(length)
        status = NtQuerySystemInformation(SystemPoolTagInformation, buf, length, ctypes.byref(ret))
        tries += 1
    if status != 0:
        return 0.0, 0.0
    count = struct.unpack_from("<I", buf, 0)[0]
    total = 0; ntfc = 0
    for i in range(count):
        off = 8 + i * 40
        tag = buf.raw[off:off+4]
        np_used = struct.unpack_from("<Q", buf, off + 32)[0]
        total += np_used
        if tag == b"NtFC":
            ntfc = np_used
    return total / 1024**3, ntfc / 1024**3

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mem_watch_log.csv")
new = not os.path.exists(LOG)
with open(LOG, "a", newline="") as fh:
    w = csv.writer(fh)
    if new:
        w.writerow(["time", "nonpaged_GB", "NtFC_GB", "avail_GB", "mem_load_pct"])
    print(f"{'time':19} {'nonpaged':>9} {'NtFC':>8} {'avail':>8} {'load':>5}")
    while True:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        np_gb, ntfc_gb = pool_snapshot()
        m = mem_status()
        avail = m.ullAvailPhys / 1024**3
        line = f"{ts:19} {np_gb:8.2f}G {ntfc_gb:7.2f}G {avail:7.1f}G {m.dwMemoryLoad:4d}%"
        print(line, flush=True)
        w.writerow([ts, f"{np_gb:.3f}", f"{ntfc_gb:.3f}", f"{avail:.2f}", m.dwMemoryLoad])
        fh.flush()
        time.sleep(60)
