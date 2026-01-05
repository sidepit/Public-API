# Sidepit Python Client 

Sidepit Python Client Interface for Trading on Sidepit Exchange 

## Getting Started

### 1. Clone the repository and navigate into it

```sh
git clone https://github.com/sidepit/Public-API.git
cd python-client
```

### 2. Create a virtual environment

```sh
python3 -m venv .venv
```

### 3. Activate the virtual environment

**Windows:**
```sh
.venv\Scripts\activate
```

**Mac/Linux:**
```sh
source .venv/bin/activate
```

### 4. Dependencies

```sh
pip install -r requirements.txt 
```

# Proto compile:

```bash
./Public-API/python-client$ protoc --proto_path=../Public-API-Data/ --python_out=./proto/ sidepit_api.proto
```

