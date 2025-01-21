# Sidepit Cryptography Tutorial - OpenSSL

## Overview

### What is OpenSSL?

OpenSSL is a cryptographic library and command-line tool that helps secure 
communications over computer networks. It's used by many applications to 
encrypt and decrypt data, and generate private keys.

### Generate a key pair

```sh
openssl genrsa -out private_key.pem 2048
openssl rsa -in private_key.pem -pubout -out public_key.pem
```

### Create and sign a message

*Create a file named `message.txt` in the root directory, add your message, and then run:*

```sh
openssl dgst -sha256 -sign private_key.pem -out signature.bin message.txt
```

### Verify a signature

```sh
openssl dgst -sha256 -verify public_key.pem -signature signature.bin message.txt
```

### Hash a message

```sh
openssl dgst -sha256 message.txt
```

### Generate a secure password

```sh
openssl rand -base64 16
```

For more info on OpenSSL, please visit the [official OpenSSL documentation](https://docs.openssl.org/master/).