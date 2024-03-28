# Sidepit Protocol Information
Information regarding `sidepit public api` input and output protocol 

## Sidepit Client
Client are users/traders sending orders to Sidepit 

### Client Protocol 
Client sends messages using NNG `push` of the [Pipeline Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pipeline.html). 

### Client API 
client port# - 12121

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/nng-client/proto/spapi.proto)

Clients sends signed `Transaction` messages

1. Opening a `push` socket 
1. Dialing `tcp://api.sidepit.com:12121`
1. Serializing into protobuf
1. Sending message 


`Transaction`
```
version 
timestamp (nano seconds) 
oneof - New, Cancel, Auction
id - ordinals address / pubkey
signature - signed ecdsa (bitcoin curve) 
```

Each Transaction can be `oneof` 
```
NewOrder
cancel_orderid
AuctionBid
```

`NewOrder`
```
side
price 
symbol
user_ref
``` 

`cancel_orderid`
```
orderid ( nanoseconds since contract start )
```

`AuctionBid` 
```
epoch
hash
ordering_salt  
bid ( in satoshis )
```

Protobuf Definitions: https://github.com/sidepit/Public-API/blob/main/nng-client/proto/spapi.proto

### OrderId 
```
OrderId - microseconds since open 
Global Unique orderID = traderID + nanoseconds epoch since contract start
```

## Sidepit PRICE-FEED Protocol 
Receiving MarketData from server using NNG `sub` of the [Pub/Sub Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pubsub.html). 

### FEED API 
feed port# - 12122

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/nng-client/proto/ogcex.proto)

Feed Client subscribes by:
1. Opening as a `sub` socket - (with topic 0)
1. Dialing `tcp://api.sidepit.com:12122`
1. Receiving messages 
1. Desterilizing into Protobuf

## Sidepit ORDER-FEED Protocol 
Receiving MarketData from server using NNG `sub` of the [Pub/Sub Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pubsub.html). 

### ORDER FEED API 
order feed port# - 12124

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/nng-client/proto/ogcex.proto)

Feed Client subscribes by:
1. Opening as a `sub` socket - (with topic 0)
2. future topics will contain `traderid` 
1. Dialing `tcp://api.sidepit.com:12124`
1. Receiving messages 
1. Desterilizing into Protobuf

ORDER FEED Clients receive  `OrderData` protobuf messages

`OrderData`
```
version 
epoch (nano seconds) 
BookOrder [0+]
FillData [0+]
```

`BookOrder`
```
price 
open_qty
filled_qty
remaining_qty
canceled_qty
symbol
update_time
orderid
traderid  
```

`FillData`
```
agressiveid
passiveid
price
qty
```

## Sidepit ECHO Protocol 
Receiving live exchange data from server using NNG `sub` of the [Pub/Sub Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pubsub.html). 

### ECHO API 
echo port# - 12123

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/nng-client/proto/spapi.proto)

ECHO Client subscribes by:
1. Opening as a `sub` socket - (with topic 0)
1. Dialing `tcp://api.sidepit.com:12123`
1. Receiving messages 
1. Desterilizing into Protobuf

ECHO Clients receive streaming `TxBlockStream` protobuf messages
`TxBlockStream `
```
epoch 
txepoch 
```

Each txepoch can be `oneof` 
```
EpochEvent 
Transaction 
```

`EpochEvent`
```
epoch 
hash
id
signature
```

`Transaction`
```
version 
timestamp (nano seconds) 
oneof - New, Cancel, Auction
id - ordinals address / pubkey
signature - signed ecdsa (bitcoin curve) 
```

Each Transaction can be `oneof` 
```
NewOrder
cancel_orderid
AuctionBid
```

`NewOrder`
```
side
price 
symbol
user_ref
``` 

`cancel_orderid`
```
orderid ( nanoseconds since contract start )
```

`AuctionBid` 
```
epoch
hash
ordering_salt  
bid ( in satoshis )
```

## Resources:
[NNG Docs](https://nng.nanomsg.org/man/tip/index.html)

[NNG NodeJS](https://github.com/reqshark/nodenng)

[NNG Python](codypiersall/pynng) 

[NNG manual](https://drive.google.com/file/d/1Wl_vcx86VnvClSC9pYytj9FVcveXjrjW/view?usp=sharing)
