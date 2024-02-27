# Sidepit Protocol Information
Information regarding `sidepit public api` input and output protocol 

## Sidepit Client
Client are users/traders sending orders to Sidepit 

### Client Protocol 
Client sends messages using NNG `push` of the [Pipeline Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pipeline.html). 

### Client API 
client port# - 12121

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/spapi.proto)

Clients send signed `Transaction` messages

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

Protobuf Definitions: https://github.com/sidepit/Public-API/blob/main/spapi.proto 

### OrderId 
```
OrderId - microseconds since open 
Global Unique orderID = traderID + nanoseconds epoch since contract start
```

## Sidepit FEED Protocol 
Receiving MarketData from server using NNG `sub` of the [Pub/Sub Scalability Protocol](https://nanomsg.org/gettingstarted/nng/pubsub.html). 

### FEED API 
feed port# - 12122

[Protobuf messages](https://github.com/sidepit/Public-API/blob/main/ogcex.proto)

Feed Client subscribes by:
1. Opening as a `sub` socket - (with topic 0)
1. Dialing `tcp://feed.sidepit.com:12122`
1. Receiving messages 
1. Desterilizing into Protobuf


FEED Clients receive  `MarketData` protobuf messages

`MarketData`
```
version 
epoch
EpochBar
MarketQuote  
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

## Resources:
[NNG Docs](https://nng.nanomsg.org/man/tip/index.html)

[NNG NodeJS](https://github.com/reqshark/nodenng)

[NNG Python](codypiersall/pynng) 

[NNG manual](https://drive.google.com/file/d/1Wl_vcx86VnvClSC9pYytj9FVcveXjrjW/view?usp=sharing)
