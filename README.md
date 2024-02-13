# Sidepit Protocol Information
Information regarding `sidepit public api` input and output protocol 

## Input Protocol 
Server listens for incoming messages from clients 

Server - NNG Pull from multiple client 

### Clients 
Clients are public users sending signed messages contain orders into sidepit 

Clients send messages using NNG Push 

## Output Protocol 
Server echos incoming messages to outbound `auction` clients 

Included in these messages are special `epoch` messages on 1 second intervals 

## API
https://github.com/sidepit/Public-API/blob/main/spapi.proto 

### Incoming orders 
new order from user:
```
timestamp (nano seconds) 
side
price 
symbol
user_ref
``` 
cancel order from user: 
```
timestamp
orderid ( nanoseconds since contract start )
```
auction bid from user: 
```
epoch
hash
nonce 
bid ( sats )
```
all messages signed
```
public_key
sig
```

### Outgoing Messages  
Out to auction servers - broadcast 
user messages: 
```
epoch 
user tx
seq# 
```
Server messages: 
[end of epoch]

```
epoch+1
hash of block ( proof of history)
epoch start seq#
epoch end seq# 
seq# 
```

### Other services  
[rep/req service]
```
req - seq# 
rep - tx 
```

## OrderId 
```
OrderId - microseconds since open 
Global Unique orderID = traderID + nanoseconds epoch since contract start
```
