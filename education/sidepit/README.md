# Connect to Sidepit's APIs

Now that you've gone through all the education, you're ready to connect to Sidepit's endpoints!

## Getting Started

### 1. Navigate to `python-client`

```sh
cd python-client
```

### 2. Create a Virtual Environment

```sh
python -m venv .env
```

### 3. Activate the Virtual Environment

**Windows:**
```sh
.env\Scripts\activate
```

**Mac/Linux:**
```sh
source .env/bin/activate
```

### 4. Install `pynng` and `protobuf`

```sh
pip install pynng
pip install protobuf==3.20.1
```

### 5. Inspect the Example File

Open the file at `python-client/run/sidepit.py` and you should see:

```python
from proto import sidepit_api_pb2
from google.protobuf.json_format import MessageToJson
import pynng

with pynng.Sub0() as sub:
    sub.dial("tcp://api.sidepit.com:12123")
    sub.subscribe(b"")
    while True:
        message = sub.recv()
        obj = sidepit_api_pb2.TxBlockStream()
        obj.ParseFromString(message)
        print(MessageToJson(obj, preserving_proto_field_name=True))
```

This code creates a subscription to Sidepit’s **echo port** (port `12123`).

### 6. Run the file

```sh
python -m run.sidepit
```

### 7. Congratulations — You're Connected!

You've successfully connected to Sidepit's **echo port** (port `12123`).  
To connect to the **feed port**, change the port to `12122` in the `sub.dial(...)` line.