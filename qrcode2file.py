import sys, gzip, base64, re
import zxingcpp
from PIL import Image

def decode(path):
    results = zxingcpp.read_barcodes(Image.open(path).convert("RGB"))
    return results[0].text if results else ""

files = sys.argv[1:]
parts = {}
total = None

for f in files:
    data = decode(f)
    m = re.match(r'^PART:(\d+)/(\d+):(.+)$', data, re.DOTALL)
    if m:
        parts[int(m.group(1))] = m.group(3)
        total = int(m.group(2))
    else:
        parts[1] = data
        total = 1

combined = "".join(parts[i] for i in range(1, total + 1))
raw = gzip.decompress(base64.b64decode(combined))

with open("output.txt", "wb") as f:
    f.write(raw)