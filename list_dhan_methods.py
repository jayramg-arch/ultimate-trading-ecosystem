import os
from dotenv import load_dotenv
from dhanhq import dhanhq

load_dotenv()
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

dhan = dhanhq(CLIENT_ID, ACCESS_TOKEN)
print("Methods in dhanhq object:")
for method in dir(dhan):
    if not method.startswith("__"):
        print(method)
