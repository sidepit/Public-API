# Sidepit CLI

Sidepit Command Line Interface for managing Bitcoin transactions.

## Getting Started

### 1. Clone the repository and navigate into it

```sh
git clone https://github.com/sidepit/users-cli.git
cd users-cli
```

### 2. Create a virtual environment

```sh
python -m venv .env
```

### 3. Activate the virtual environment

**Windows:**
```sh
.env\Scripts\activate
```

**Mac/Linux:**
```sh
source .env/bin/activate
```

### 4. Dependencies

```sh
pip install -r requirements.txt 
```

The bitcoinlib package depends on fastecdsa which requires (the gmp.h from the) GNU Multiple Precision Arithmetic Library (GMP), so install that before installing bitcoinlib e.g.
```
sudo apt-get install libgmp-dev 
sudo apt-get install python-dev-is-python3 
```
# Proto compile:

```bash
./api/users-cli$ protoc --proto_path=../../proto/ --python_out=./cli/ sidepit_api.proto
```
