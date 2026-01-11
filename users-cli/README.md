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
### Proto compile:

```bash
./api/users-cli$ protoc --proto_path=../../proto/ --python_out=./cli/ sidepit_api.proto
```
### Run Client Cli:
```bash
./api/users-cli$ pyhton3 cli/main.py
```

<img width="2034" height="1003" alt="{47A93F62-BAFC-4BD4-99B8-3ECE3D3EFE64}" src="https://github.com/user-attachments/assets/f1bdc278-23a9-4c7c-b05c-dbfcb01a91be" />
<img width="2000" height="1070" alt="image" src="https://github.com/user-attachments/assets/5ee7528b-e777-430a-8932-736b7d338131" />



