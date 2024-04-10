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

## Sidepit PRICE FEED Protocol 
Receiving MarketData from server using NNG `sub` of the [Pub/Sub Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pubsub.html). 

### PRICE FEED API 
price feed port# - 12122

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/nng-client/proto/ogcex.proto)

Price Feed Client subscribes by:
1. Opening as a `sub` socket - (with topic 0)
1. Dialing `tcp://api.sidepit.com:12122`
1. Receiving messages 
1. Desterilizing into Protobuf

PRICE FEED Clients receive  `MarketData` protobuf messages

`MarketData`
```
version 
epoch
EpochBar
MarketQuote
DepthItem (x10)  
```

`EpochBar`
```
symbol
epoch
open
high
low
close 
volume
``` 

`MarketQuote`
```
bidsize
bid
ask
asksize
last
lastsize
upordown
symbol
epoch
```

`DepthItem`
```
level
b
a
bs
as
```

## Sidepit ORDER-FEED Protocol 
Receiving MarketData from server using NNG `sub` of the [Pub/Sub Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pubsub.html). 

### ORDER FEED API 
order feed port# - 12124

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/nng-client/proto/ogcex.proto)

Order Feed Client subscribes by:
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
side 
price 
open_qty
filled_qty
remaining_qty
canceled_qty
agres_fill_qty
agres_avg_price
pass_fill_qty
avg_price
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
agressive_side // -1 for agressive sell, 1 for buy 
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
## Sidepit POSITION Protocol 
Receiving positions and order status per `traderid` from server using NNG `REQ` of the [Request/Reply (I ask, you answer), Scalability Protocol](https://nanomsg.org/gettingstarted/nng/reqrep.html). 

### POS API 
pos port# - 12125

[Protobuf messages](https://github.com/sidepit/Public-API-Data/blob/main/ogcex.proto)

POS Client sends Request and receives Reply  
1. Opening as a `req` socket 
1. Dialing `tcp://api.sidepit.com:12125`
1. Serialize request into Protobuf 
1. Send Request message
1. Receive Reply message  
1. Desterilizing reply into Protobuf

Request: POS Clients sends `RequestPositions` protobuf messages

`RequestPositions`
```
traderid 
symbol 
```

Reply: POS Clients receive `TraderPositionOrders` protobuf messages

`TraderPositionOrders` 
```
traderid 
symbol 
Position 
map<string, OrderFills> // OrderFills keyed on `orderid` 
```

`Position`
```
position // -1 for short 1, 1 for long 1
avg_price 
```

`OrderFills`
```
BookOrder 
FillData [0+]
```

`BookOrder`
```
side 
price 
open_qty
filled_qty
remaining_qty
canceled_qty
agres_fill_qty
agres_avg_price
pass_fill_qty
avg_price
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
agressive_side // -1 for agressive sell, 1 for buy 
``` 

## Resources:
[NNG Docs](https://nng.nanomsg.org/man/tip/index.html)

[NNG NodeJS](https://github.com/reqshark/nodenng)

[NNG Python](codypiersall/pynng) 

[NNG manual](https://drive.google.com/file/d/1Wl_vcx86VnvClSC9pYytj9FVcveXjrjW/view?usp=sharing)
