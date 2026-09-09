"""One-off diagnostic: list nonpaged-pool usage by tag (to name a leaking driver).
Calls NtQuerySystemInformation(SystemPoolTagInformation). Read-only."""
import ctypes, struct
from ctypes import wintypes

ntdll = ctypes.WinDLL("ntdll")
NtQuerySystemInformation = ntdll.NtQuerySystemInformation
NtQuerySystemInformation.restype = ctypes.c_long
SystemPoolTagInformation = 22
STATUS_INFO_LENGTH_MISMATCH = -1073741820  # 0xC0000004 as signed

length = 4 * 1024 * 1024
ret = ctypes.c_ulong(0)
buf = ctypes.create_string_buffer(length)
status = NtQuerySystemInformation(SystemPoolTagInformation, buf, length, ctypes.byref(ret))
tries = 0
while status == STATUS_INFO_LENGTH_MISMATCH and tries < 8:
    length = ret.value + 65536
    buf = ctypes.create_string_buffer(length)
    status = NtQuerySystemInformation(SystemPoolTagInformation, buf, length, ctypes.byref(ret))
    tries += 1

if status != 0:
    print(f"NtQuerySystemInformation failed: status={status:#x}")
    raise SystemExit(1)

count = struct.unpack_from("<I", buf, 0)[0]
rows = []
base = 8                      # ULONG Count + 4 pad, array is 8-aligned
for i in range(count):
    off = base + i * 40       # sizeof(SYSTEM_POOLTAG) on x64 = 40
    tag = buf.raw[off:off + 4]
    np_used = struct.unpack_from("<Q", buf, off + 32)[0]   # NonPagedUsed at +32
    rows.append((np_used, tag.decode("latin1").rstrip("\x00")))

rows.sort(reverse=True)
total = sum(r[0] for r in rows)
print(f"Total nonpaged (by tag): {total/1024/1024/1024:.2f} GB across {count} tags")
print("Top nonpaged-pool tags by bytes:")
for np_used, tag in rows[:15]:
    print(f"  {np_used/1024/1024:9.0f} MB   tag={tag!r}")
