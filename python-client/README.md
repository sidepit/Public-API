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

### Proto compile:

```bash
./Public-API/python-client$ protoc --proto_path=../Public-API-Data/ --python_out=./proto/ sidepit_api.proto
```

### Feed Demo 
```bash
./Public-API/python-client$ python3 feed_demo.py 
```

# Client Data Sample 
http://localhost:8000/active_product/ 

```
active_contract_product {
  contract {
    symbol: "USDBTC"
    unit_size: 500
    unit: "USD"
    price_quote: "SAT"
    price_quote_units: 1
    tic_min: 1
    tic_value: 500
    price_limit_percent: 25
    initial_margin: 2000
    maint_margin: 1000
    position_limits: 200
    trading_open_time: 46800000
    trading_close_time: 3600000
    trading_open_time_zone: "06:00:00 America/Los_Angeles"
    trading_close_time_zone: "18:00:00 America/Los_Angeles"
  }
  product {
    ticker: "USDBTCH26"
    contract_symbol: "USDBTC"
    expiration_date: 1767419700000
    start_trading_date: 1767370500000
    is_active: true
  }
  schedule {
    date: 1767379500000
    trading_open_time: 1767379200000
    trading_close_time: 1767379500000
    product: "USDBTCH26"
    product: "USDBTCM26"
  }
}
exchange_status {
  session {
    session_id: "1767379500000"
    schedule {
      date: 1767379500000
      trading_open_time: 1767379200000
      trading_close_time: 1767379500000
      product: "USDBTCH26"
      product: "USDBTCM26"
    }
    prev_session_id: "1704067200000"
  }
  status {
    estate: EXCHANGE_OPEN
    session_id: "1767379500000"
  }
}
contractbar {
  day_open: 1105
  day_high: 1111
  day_low: 1101
  day_close: 1101
  day_volume: 26
  high: 1111
  low: 1101
  volume: 26
  open_interest: 26
}
```

## Price Feed 
http://localhost::8000/quote 
wss::localhost::8000/feed 

```
epoch: 1767379375000
ticker: "USDBTCH26"
bar {
  open: 1101
  high: 1101
  low: 1101
  close: 1101
}
quote {
  bidsize: 1
  bid: 1106
  ask: 1111
  asksize: 1
  last: 1101
  lastsize: 1
  ticker: "USDBTCH26"
}
depth {
  b: 1106
  a: 1111
  bs: 1
  as: 1
}
depth {
  level: 1
  b: 1099
  a: 1112
  bs: 3
  as: 2
}
depth {
  level: 2
  b: 1098
  a: 1113
  bs: 7
  as: 4
}
depth {
  level: 3
  b: 1097
  a: 1115
  bs: 4
  as: 1
}
```
## Order Feed 
ws://localhost::8000/order  

```
epoch: 1767561656871
bookorders {
  side: -1
  price: 1084
  open_qty: 1
  canceled_qty: 1
  ticker: "USDBTCH25"
  update_time: "1767561657875"
  orderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8:1767561654754830848"
  traderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8"
}
bookorders {
  side: -1
  price: 1084
  open_qty: 1
  remaining_qty: 1
  ticker: "USDBTCH25"
  update_time: "1767561657875"
  orderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8:1767561655868600576"
  traderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8"
}

[2026-01-04 13:20:58.397 -08:00] [thread 2431538] [info] [client.h:140] *** orderdata test bs 623 ss 623
epoch: 1767561657874
bookorders {
  side: 1
  price: 1083
  open_qty: 1
  canceled_qty: 1
  ticker: "USDBTCH25"
  update_time: "1767561658878"
  orderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8:1767561655866952960"
  traderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8"
}
bookorders {
  side: -1
  price: 1084
  open_qty: 1
  canceled_qty: 1
  ticker: "USDBTCH25"
  update_time: "1767561658878"
  orderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8:1767561655868600576"
  traderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8"
}
bookorders {
  side: 1
  price: 1083
  open_qty: 1
  remaining_qty: 1
  ticker: "USDBTCH25"
  update_time: "1767561658878"
  orderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8:1767561657008092672"
  traderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8"
}
bookorders {
  side: -1
  price: 1084
  open_qty: 1
  remaining_qty: 1
  ticker: "USDBTCH25"
  update_time: "1767561658878"
  orderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8:1767561657009142784"
  traderid: "bc1q86ckzqru5wa77trszhw4asyhwtg5q4at5jkkx8"
}
```
## Trader Positions 

https://localhost/request_position/bc1qafzt9puf4vrcg7gzqvrvcffprpck2uf80p0vw6

https://api.sidepit.com/request_position/bc1qa29486m9azmwer9hdf0rdc6yx9c7mdpsl4hn6m

```
traderid: "bc1qafzt9puf4vrcg7gzqvrvcffprpck2uf80p0vw6"
accountstate {
  sidepit_id: "bc1qafzt9puf4vrcg7gzqvrvcffprpck2uf80p0vw6"
  pubkey: "03b3520e97435c6f800481770a6b32230a6ae9a37c77b34b9bbb8945794d0146ca"
  net_locked: 97868
  available_balance: 97868
  available_margin: 97868
  contract_margins {
    key: "USDBTC"
    value {
      symbol: "USDBTC"
      margin {
      }
      positions {
        key: "USDBTCH26"
        value {
          ticker: "USDBTCH26"
          position {
          }
          margin {
          }
        }
      }
      positions {
        key: "USDBTCM26"
        value {
          ticker: "USDBTCM26"
          position {
          }
          margin {
          }
        }
      }
    }
  }
}
locks {
  txid: "d2dafecf0c38062b06c02e1ec24dca112e92825e7f167163aa758e4bbc5f48b7"
  pubkey: "03b3520e97435c6f800481770a6b32230a6ae9a37c77b34b9bbb8945794d0146ca"
  btc_address: "bc1qafzt9puf4vrcg7gzqvrvcffprpck2uf80p0vw6"
  lock_sats: 97868
}
```

#### BetaV1
https://api.sidepit.com/request_position/bc1qjd9mdr5z3utkder362fhmnrh2m0lujln7a4ku7 
```
{
  "traderid": "bc1qjd9mdr5z3utkder362fhmnrh2m0lujln7a4ku7",
  "accountstate": {
    "sidepit_id": "bc1qjd9mdr5z3utkder362fhmnrh2m0lujln7a4ku7",
    "pubkey": "02de4119288861e6a88a7a81307998f5420ca740cba769110785d6fc656692f0c0",
    "net_locked": "469670",
    "available_balance": "469670",
    "available_margin": "469670",
    "pending_unlock": "0",
    "realized_pnl": "0",
    "unrealized_pnl": "0",
    "margin_required": "0",
    "is_restricted": false,
    "reduce_only": 0,
    "positions": {

    },
    "carried_position": 0,
    "new_position": 0,
    "open_bids": 0,
    "open_asks": 0
  },
  "locks": [
    {
      "txid": "dcb350058b7918ef4af7a1e702117517594827dfc5180bbc5ce535d29fd58ad5",
      "pubkey": "02de4119288861e6a88a7a81307998f5420ca740cba769110785d6fc656692f0c0",
      "btc_address": "bc1qjd9mdr5z3utkder362fhmnrh2m0lujln7a4ku7",
      "lock_sats": "469670",
      "unlock_sats": "0",
      "is_pending": false
    }
  ],
  "symbol": "",
  "orderfills": {

  }
}

``` 
## Sidepit_Id Order Entry 

NNG tcp://api.sidepit.com:12121

```
// input 
message Transaction {
    int32 version = 1;
    uint64 timestamp = 10; 
    oneof tx {
        NewOrder new_order = 20;
        string cancel_orderid = 30;
        AuctionBid auction_bid = 40;
    }
    string id = 100;
    bytes signature = 110;   
}

// Protobuf Serialized - New Order  
stx {
  transaction {
    version: 1
    timestamp: 1767395841878
    new_order {
      side: -1
      size: 2
      price: 1098
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "155668c5b3730ccb0e7123a7d3b8c53cab4fac64de7f8810eb57d9f8cb4db16a7d0d4eddb4f69677bdcb88e4edff9743f3459fe8204e2bab68068b3b37593ce0"
} 

// Protobuf Serialized - Auction Bid  

stx {
  transaction {
    version: 1
    timestamp: 1767395842029
    auction_bid {
      ordering_salt: "rwZ2dBk"
      bid: 2
    }
    sidepit_id: "bc1qzzy7gyq8n8zen4zed90vtg2a0zmp4rv0expepc"
  }
  signature: "81a647b1bca3546df43386585a18a7f349c79305258d9c93773e4b1b2e81afc807a0299410b49a69ad3fa7fce2ec2858f9d3590667432f1acfdd27b80ea40c5c"
}


// Protobuf Serialized - Cancel Order   
stx {
  transaction {
    version: 1
    timestamp: 1767395842331
    cancel_orderid: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5:1767395841878"
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "b13788009775aafeea2488cfdb88b6bdf3e9ff7ed3a9df7f384aae280534261133e634690ae5c22538ebd89799ed2e7f0a429f29fbb1159f47ee69e2f8c4ab8f"
}

```


## Echo - real time low latency stream 
[ws://localhost:13123](ws://localhost:13123) 

nng: [tcp://localhost:12123](tcp://localhost:12123)

[ws:/api.sidepit.com/echo](ws:/api.sidepit.com/echo)

[ws:/api.sidepit.com:13123](ws:/api.sidepit.com:13123)

```
---
epoch: 1767396791000
estate: EXCHANGE_OPEN
epoch_event {
  epoch: 1767396791000
}

======================
stx {
  transaction {
    version: 1
    timestamp: 1767395841878
    new_order {
      side: -1
      size: 2
      price: 1098
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "155668c5b3730ccb0e7123a7d3b8c53cab4fac64de7f8810eb57d9f8cb4db16a7d0d4eddb4f69677bdcb88e4edff9743f3459fe8204e2bab68068b3b37593ce0"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395842029
    auction_bid {
      ordering_salt: "rwZ2dBk"
      bid: 2
    }
    sidepit_id: "bc1qzzy7gyq8n8zen4zed90vtg2a0zmp4rv0expepc"
  }
  signature: "81a647b1bca3546df43386585a18a7f349c79305258d9c93773e4b1b2e81afc807a0299410b49a69ad3fa7fce2ec2858f9d3590667432f1acfdd27b80ea40c5c"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395842180
    auction_bid {
      ordering_salt: "BBjs3BG"
      bid: 1
    }
    sidepit_id: "bc1qp0j9t53xcp6j6jrreakjezlxme9a5tdzh5unk3"
  }
  signature: "6efcbe579dbb1f6556808b661f51a3f1a5de05501851487eca297cd95f35c6421d85bc0ba6d8aaa7e7a6859b5efd8f282cc43650fe77260e4ab08a0de6888efd"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395842331
    cancel_orderid: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5:1767395841878"
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "b13788009775aafeea2488cfdb88b6bdf3e9ff7ed3a9df7f384aae280534261133e634690ae5c22538ebd89799ed2e7f0a429f29fbb1159f47ee69e2f8c4ab8f"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395842582
    cancel_orderid: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5:1767394457389"
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "a3ad43e9b08203c10e77b9a4924c701c650f60aebe32f7e5f4a931b746711ada2e562f31579f417cd078fdd73e354aa93aae335610a31392a1e1918396e4b789"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395842742
    cancel_orderid: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln:1767395573635"
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "323fb4c4401658a1e11dd8546091fb5c678d8182d12d2eb7df8cfe31def5eeaf7a2dd17db909b9d7979b1a2ed155c336115d721079db763a58ab185d4976da16"
}

---
epoch: 1767396792000
estate: EXCHANGE_OPEN
epoch_event {
  epoch: 1767396792000
}

======================
stx {
  transaction {
    version: 1
    timestamp: 1767395842903
    new_order {
      side: 1
      size: 2
      price: 1106
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qyf9txm2wrp52tclchlszmav3q0txq7yrgplzhu"
  }
  signature: "1a62ece2eca9853c5bd9631c95ce1bed629d2b729957c6e5690d20bcde90076c429e11649b8c235375aa0de0611afa1de9c11d751a6b8e012f01f8e1a0719511"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395843054
    new_order {
      side: -1
      size: 1
      price: 1114
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "4d1d79062e606833a6c99a9f5371befa969f1dac401ed5e96dd66e1f19328cb044d80152d8d206128dbe3f71d4682233556e1602093daac78a763f00877adf1b"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395843205
    new_order {
      side: -1
      size: 1
      price: 1110
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "73fb07cc6e46472ce9bc8ee441fc0e1970aab1038c3fe20773dde20ab572c6c01faf4b6cfe6c0a3e1e315ece3f7a82bdca8e1f3790c6288c487c6fb2220b6747"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395843356
    auction_bid {
      ordering_salt: "EDteTIA"
      bid: 1
    }
    sidepit_id: "bc1qzzy7gyq8n8zen4zed90vtg2a0zmp4rv0expepc"
  }
  signature: "853bb90611034d9ef1a272741a70471f910bbd7f6d5e58d3c56ef3a473bcb1f21c5a9935059703b345e7399e080d24e63deb8525bb47ec59aa863925cbe64ced"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395843506
    cancel_orderid: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5:1767395843205"
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "1c1e5bc66c3fa2956b0401d5940a6654aa1b4466b6cebbde5e97768bda003a3e50cb342e00d9ff69fdc46777a06a88d013aea04d8849ac6f04d8223834c8f6f9"
}

---
epoch: 1767396793000
estate: EXCHANGE_OPEN
epoch_event {
  epoch: 1767396793000
}

======================
stx {
  transaction {
    version: 1
    timestamp: 1767395843757
    cancel_orderid: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln:1767394088358"
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "cae6d622e495a8267e594d8222f4b3ccdfde555c7dbb5eb22ac7dcf34553d4230c2d185863e8bb50a98ae61ef9fd54fac45c11813e1a563333216e7e767607f6"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395843918
    cancel_orderid: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln:1767393921951"
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "d336661d837180eb66abcffc31087d1bd037ca50205bd9d77f58accf68914e330f04de68e45c30fa253b336823126ebd0dd9dc35263009804752539029d2d7a4"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395844079
    new_order {
      side: 1
      size: 1
      price: 1102
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qyf9txm2wrp52tclchlszmav3q0txq7yrgplzhu"
  }
  signature: "b18216a3385be06059bed8f0f4c7fad6e0d4ec6e1c127bdbdc97b33551aee5a87d05ed1edf241cbaed388fbc6123e9450ad6f0fd28dfe90d273566b9dcc99bf0"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395844230
    new_order {
      side: 1
      size: 1
      price: 1113
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qxzz2k7s7eyrvelwmndsfv05y3rllqu5tnh22ca"
  }
  signature: "54a9326cbe5cf8a0212022b238cfa0b1781c1d03059cdd65e2106adae17603a46129d47cf17b90a33260e2ae69fcf3706d1a9f9219e6de73aecb6d52b46a09bc"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395844380
    new_order {
      side: -1
      size: 2
      price: 1099
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "6d9ee2c02de79173b750473613a36d7d79185725a6486906d44ad97a74f2881d3ce0747c33a34c1f3c8e0c3396f79b0ac686e5424f8ec2f37e93b07d2411abce"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395844531
    auction_bid {
      ordering_salt: "2nZnzwD"
      bid: 1
    }
    sidepit_id: "bc1qzzy7gyq8n8zen4zed90vtg2a0zmp4rv0expepc"
  }
  signature: "d2912ff44738115adafe8dfe1d1cb4080ff4a71ce6af6a932062968017057c931fa5829ec380783104adf8edf7e3fdae9eb17275bd0213c77df97f1cc682bc5d"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395844682
    auction_bid {
      ordering_salt: "TmtUNDl"
      bid: 1
    }
    sidepit_id: "bc1qp0j9t53xcp6j6jrreakjezlxme9a5tdzh5unk3"
  }
  signature: "af19b918895b5550025f509df1e6c6ac5fe29ebc3831d77a7bf8f21ff664b1c11a545fce860a0e36aefac1d1462767e292ed7dbd1fc475b0696402f2df75270e"
}

---
epoch: 1767396794000
estate: EXCHANGE_OPEN
epoch_event {
  epoch: 1767396794000
}

======================
stx {
  transaction {
    version: 1
    timestamp: 1767395844832
    cancel_orderid: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln:1767395844380"
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "b0d23c1c328011c3a24df9647d60ed4f6a58484ba45bf4588b358bc2f28d779e32f0083e80f1a425a01700816a26cf2119891e466a72040af76493d8cadfb784"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395845083
    cancel_orderid: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln:1767395294261"
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "ca3ce24bac781ccf7ba84522d01a7574e02029eacf11021625448b370e1627340b28b601a871ee2bd3250fecca6c14c73576b6f0d83e6fa27fa9a03daa2180e0"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395845244
    new_order {
      side: 1
      size: 2
      price: 1112
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qyf9txm2wrp52tclchlszmav3q0txq7yrgplzhu"
  }
  signature: "403da83a8624274ca92bc49257c4cdc5315178457ee6bb93f5d44e973ac2bd947908c0b92df453af3344cf32825ae6a53eef8ac30abb457d79b79aee6f5083c8"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395845395
    new_order {
      side: 1
      size: 2
      price: 1106
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qxzz2k7s7eyrvelwmndsfv05y3rllqu5tnh22ca"
  }
  signature: "baccbb9f401413ee9e4d6fd245d31d084e2991b4f2b1bb62c54d900851cc46e12e12cf17ad3ccca2fbcf925c1d27f60fbf57670a38b0b51708f64afac6437688"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395845546
    new_order {
      side: -1
      size: 1
      price: 1102
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "25fdd71305e09bce16c5641e1199ac25d8b35442ab0d0f4a995b8aa30f58d303274664d2c79836db104c822323af17a019bdca1bacef477723ffe6bbe1d4e3a2"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395845696
    new_order {
      side: -1
      size: 2
      price: 1115
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "4d1e2515dce4da8c89f9d6a70b74c0170c727a89f126a559c68e5a4b1520bc142b9443bd398d4492dc1cdc5230cda5841920bd0f43c70a4a033dea25247c7381"
}

---
epoch: 1767396795000
estate: EXCHANGE_OPEN
epoch_event {
  epoch: 1767396795000
}

======================
stx {
  transaction {
    version: 1
    timestamp: 1767395845847
    new_order {
      side: 1
      size: 1
      price: 1098
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qyf9txm2wrp52tclchlszmav3q0txq7yrgplzhu"
  }
  signature: "dcb1d5da7b53e9244a7c970e120b280936aa0cda8c4fc60f421ae773eb5b88666514a764b2d386eab643327fccca4b5c5cdacf006822d1e2ce7c609cc884abda"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395845998
    new_order {
      side: -1
      size: 2
      price: 1107
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "88542927189b6d31be8f1c7c813aed968c893a0533170c4af3d02a75099f998a577e3195fd15604d2e59ea9000112b806c0dc9cd2cddb549e34d098c238b0f45"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395846149
    new_order {
      side: -1
      size: 1
      price: 1115
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "d03070da8fd05b206073f9b9065cc69dbe363d27a4e49b32c55664c3307fe8eb12ca6c110ab206df75e67ac4b135ea921faf7c01d594fc227bd7b1d0968820d0"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395846300
    auction_bid {
      ordering_salt: "MC6b8Du"
      bid: 1
    }
    sidepit_id: "bc1qzzy7gyq8n8zen4zed90vtg2a0zmp4rv0expepc"
  }
  signature: "5eac957b1f8a39ecce32784466e7b4b7e182d20359a8a9ee0599dbdd80d8a7ab51c646c8e06b6b0984b14edfaba665744dca0270124d63298069e00091bd37b3"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395846450
    auction_bid {
      ordering_salt: "D6LFNj3"
      bid: 2
    }
    sidepit_id: "bc1qp0j9t53xcp6j6jrreakjezlxme9a5tdzh5unk3"
  }
  signature: "529b4e054530aea11d817b1b032f778d22b2507b23637fb01ceb41be511e81d3236adb85170dcb3ae23d7e09cd7d0688b9fdce972f9e5e3c6663910566361a39"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395846601
    cancel_orderid: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5:1767395846149"
    sidepit_id: "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"
  }
  signature: "4ee5b74bb7c1f76147960e518b017f7d625d80a4baa044002d2b897d81a9902807e83d3a3176d6dbb5c8989ff00f55fb07f2fe26a64668d513c4531fd61679b0"
}

---
epoch: 1767396796000
estate: EXCHANGE_OPEN
epoch_event {
  epoch: 1767396796000
}

======================
stx {
  transaction {
    version: 1
    timestamp: 1767395846852
    cancel_orderid: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln:1767394812166"
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "544a1d970647d65e9e77b608c6899ad52f3b891d8bb1b055f21bb0553140c98b5da8db0174cb880fb8768994cad237462fe71256705bd35a10cfbae8aafda9c8"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395847013
    new_order {
      side: 1
      size: 1
      price: 1114
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qyf9txm2wrp52tclchlszmav3q0txq7yrgplzhu"
  }
  signature: "00819ef9d097c3be6cef9ee0ce5c2f803041e9e603fff81b6e1fefdac58a140c6c02e3273a8bd5990ccb79cabb37795971a6460e4e470cbcf9867dd576b52590"
}

---
stx {
  transaction {
    version: 1
    timestamp: 1767395847164
    new_order {
      side: -1
      size: 1
      price: 1108
      ticker: "USDBTCH26"
    }
    sidepit_id: "bc1qa4k32j4k609uh2z05k65de48hmgx74gl04gkln"
  }
  signature: "82f8edb0175c433773408a1fe8e79264a328aed4ba74b96bcde9076e09d555fe37804c3e2df9f37e734d80b66af784b6a94970ee187b55c981fd4904c9b1d090"
}

---

```

## Epoch Time Converter 
https://www.epochconverter.com/?q=1767396794000 

Assuming that this timestamp is in milliseconds:
GMT: Fri, 02 Jan 2026 23:33:14 GMT
Your time zone: Fri Jan 02 2026 15:33:14 GMT-0800 (Pacific Standard Time)