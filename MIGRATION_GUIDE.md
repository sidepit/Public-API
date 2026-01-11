# Sidepit API Migration Guide: Multiple Products & New Protocol

## Overview
This guide documents the migration from single-ticker API to multi-product trading system with nested account structures.

---

## 1. API Structure Changes

### Old Structure (Single Ticker)
```
AccountState (flat):
  - sidepit_id
  - net_locked
  - available_balance
  - positions: map<ticker, Position>  // Flat map
  - realized_pnl (single value)
  - margin_required (single value)
```

### New Structure (Multi-Product)
```
AccountMarginState (nested by contract):
  - sidepit_id
  - net_locked  
  - available_balance
  - contract_margins: map<symbol, ContractMargin>
      ContractMargin:
        - symbol (e.g., "USDBTC")
        - margin: PositionMargin
            - realized_pnl
            - margin_required
            - reduce_only
        - positions: map<ticker, AccountTickerPosition>
            AccountTickerPosition:
              - ticker (e.g., "USDBTCH26")
              - position: Position
                  - position (qty)
                  - avg_price
              - margin: PositionMargin
              - open_bids/open_asks
```

**Key Change**: Positions are now grouped by contract symbol, then by ticker within each contract.

---

## 2. Multiple Tickers Per Session

### Schedule Structure
```protobuf
message Schedule {
    uint64 date = 10;
    uint64 trading_open_time = 20;
    uint64 trading_close_time = 30;
    repeated string product = 40;  // Multiple tickers: ["USDBTCH26", "USDBTCM26"]
}
```

### Product Response
```protobuf
message ActiveProduct {
    string ticker = 2;  // Current ticker
    ActiveContractProduct active_contract_product = 10;
        product {
            ticker: "USDBTCH26"
            is_active: true  // Official active ticker
        }
        schedule {
            product: "USDBTCH26"
            product: "USDBTCM26"  // All available tickers
        }
    ExchangeStatus exchange_status = 20;
    ContractBar contractbar = 30;
}
```

**Implementation Pattern**:
```python
# Extract active ticker from product
active_ticker = product_pb.active_contract_product.product.ticker

# Extract all available tickers from schedule
available_tickers = list(product_pb.exchange_status.session.schedule.product)
```

---

## 3. Request/Reply API Changes

### Get Active Product (supports ticker parameter)
```python
# Old: Always returned single active product
product = req_client.get_active_product()

# New: Can request specific ticker or get default active
product = req_client.get_active_product(ticker=None)  # Active ticker
product = req_client.get_active_product(ticker="USDBTCM26")  # Specific ticker
```

### Get Quote (supports ticker parameter)
```python
# Old: Single quote
quote = req_client.get_quote()

# New: Quote for specific ticker
quote = req_client.get_quote(ticker="USDBTCH26")
quote = req_client.get_quote(ticker=None)  # Default active
```

### Get Positions (unchanged parameter, changed structure)
```python
positions_data = req_client.get_positions(trader_id)
# Now returns AccountMarginState with nested structure
```

---

## 4. Extracting Position Data

### Old Method (Flat)
```python
accountstate = data.get("accountstate")
positions = accountstate.get("positions")  # Direct access
for ticker, position in positions.items():
    qty = position["position"]
    price = position["avg_price"]
```

### New Method (Nested)
```python
accountstate = data.get("accountstate")
positions = {}
contract_margins = accountstate.get('contract_margins', {})

# Flatten positions from all contracts
for symbol, contract_margin in contract_margins.items():
    ticker_positions = contract_margin.get('positions', {})
    for ticker, ticker_pos_data in ticker_positions.items():
        position_data = ticker_pos_data.get('position', {})
        positions[ticker] = {
            'position': position_data.get('position', 0),
            'avg_price': position_data.get('avg_price', 0.0)
        }
```

**Protobuf Direct Access**:
```python
# Access nested protobuf
for symbol, contract_margin in accountstate.contract_margins.items():
    for ticker, ticker_pos in contract_margin.positions.items():
        qty = ticker_pos.position.position
        price = ticker_pos.position.avg_price
```

---

## 5. Account Metrics Display

### Old Metrics (Flat)
```python
ACCOUNT_METRICS = [
    ("Net Locked", "net_locked"),
    ("Realized PnL", "realized_pnl"),
    ("Margin Required", "margin_required"),
    ("Available Balance", "available_balance"),
]
```

### New Metrics (Global + Per-Contract)
```python
ACCOUNT_METRICS = [
    ("Net Locked", "net_locked"),
    ("Available Balance", "available_balance"),
    ("Available Margin", "available_margin"),
]

# Then iterate contract_margins for per-contract data
for symbol, contract_margin in contract_margins.items():
    margin = contract_margin.margin
    display(f"{symbol} Margin Required", margin.margin_required)
    display(f"{symbol} Realized PnL", margin.realized_pnl)
```

---

## 6. Exchange State Handling

### Exchange States (Enum)
```
0: EXCHANGE_UNKNOWN
1: EXCHANGE_PENDING_OPEN
2: EXCHANGE_OPEN       ← Trading allowed
3: EXCHANGE_RECOVERING
4: EXCHANGE_CLOSING
5: EXCHANGE_SETTLED
6: EXCHANGE_CLOSED     ← Trading blocked
```

### Getting Status String
```python
# Protobuf enum returns integer
status = api_data.exchange_status.status.estate  # Returns 6

# Convert to string name
from sidepit_api_pb2 import ExchangeState
status_str = ExchangeState.Name(status)  # Returns "EXCHANGE_CLOSED"
```

### Implementation Pattern
```python
# Store exchange status
exchange_status = product_pb.exchange_status.status.estate

# Check if trading allowed
def is_exchange_open():
    return exchange_status == 2  # EXCHANGE_OPEN

# Use for UI feedback
menu_color = "green" if is_exchange_open() else "red"
```

---

## 7. Ticker Management

### Tracking Active Ticker
```python
class Manager:
    def __init__(self):
        self.active_ticker = None  # Currently selected
        self.available_tickers = []  # All available in session
        self.exchange_status = None
    
    def update_from_product(self, product_pb):
        # Extract active ticker
        if product_pb.active_contract_product.product.ticker:
            self.active_ticker = product_pb.active_contract_product.product.ticker
        
        # Extract available tickers from schedule
        if product_pb.exchange_status.session.schedule.product:
            self.available_tickers = list(
                product_pb.exchange_status.session.schedule.product
            )
        
        # Store exchange status
        self.exchange_status = product_pb.exchange_status.status.estate
```

### Switching Tickers
```python
def switch_ticker(self, ticker_or_index):
    # Support numeric selection
    try:
        index = int(ticker_or_index) - 1
        if 0 <= index < len(self.available_tickers):
            ticker = self.available_tickers[index]
        else:
            return False
    except ValueError:
        ticker = ticker_or_index
    
    if ticker not in self.available_tickers:
        return False
    
    self.active_ticker = ticker
    return True
```

### Displaying Available Tickers
```python
def list_tickers(self):
    for i, ticker in enumerate(self.available_tickers, 1):
        marker = "[CURRENT]" if ticker == self.active_ticker else ""
        print(f"{i}. {ticker} {marker}")
```

---

## 8. Dynamic Values in Transactions

### Problem: Stale Ticker/ID
When users switch tickers or wallets, transactions must use current values.

### Solution: Store Manager References
```python
# Bad: Store static values
class ApiClient:
    def __init__(self, ticker, sidepit_id):
        self.ticker = ticker  # Stale after switch
        self.sidepit_id = sidepit_id  # Stale after wallet switch

# Good: Store manager reference
class ApiClient:
    def __init__(self, manager, id_manager):
        self.manager = manager
        self.id_manager = id_manager
    
    def create_order(self):
        # Always get current values
        ticker = self.manager.active_ticker
        sidepit_id = self.manager.sidepit_id
```

---

## 9. Position Filtering

### Show Relevant Positions Only
```python
def display_positions(self, active_ticker=None):
    filtered_positions = {}
    for ticker, details in self.positions.items():
        position_size = details.get("position", 0)
        # Show if active ticker OR has non-zero position
        if ticker == active_ticker or position_size != 0:
            filtered_positions[ticker] = details
```

**Rationale**: Users typically care about:
- Current ticker they're trading
- Other tickers where they have open positions

---

## 10. Direct Protobuf Communication

### Old: REST + JSON
```python
# Convert to JSON
json_message = MessageToJson(stx)
# POST to REST API
response = requests.post(api_url, json=json_message)
```

### New: NNG Push Socket
```python
import pynng

# Initialize once
socket = pynng.Push0()
socket.dial("tcp://localhost:12126")

# Send protobuf directly
serialized_msg = stx.SerializeToString()
socket.send(serialized_msg)
```

**Benefits**:
- No JSON conversion overhead
- Direct binary protocol
- Lower latency
- Fewer serialization errors

---

## 11. Reserved Keyword Handling

### Protobuf Field Name Collision
```protobuf
message DepthItem {
    int32 as = 60;  // "as" is Python keyword
}
```

### Access Pattern
```python
# Option 1: Use underscore suffix
value = level.as_

# Option 2: Use getattr
value = getattr(level, 'as', 0)

# Option 3: Dict access (after MessageToDict)
value = level_dict.get('as', 0)
```

---

## 12. Display Updates

### Session Info with Tickers
```python
ticker_list = ", ".join(session.schedule.product)
active_marker = f" (Current: {product.ticker})"

session_info = f"""
Exchange Status: {exchange_status_name}
Available Tickers: {ticker_list}{active_marker}
Session Times: 
    Start - {start_time}
    End - {end_time}
"""
```

---

## 13. Complete Migration Checklist

### Data Model
- [ ] Update AccountState to AccountMarginState
- [ ] Handle nested contract_margins structure
- [ ] Update position extraction to iterate contracts
- [ ] Update account metrics to show per-contract data

### Multi-Ticker Support
- [ ] Track active_ticker and available_tickers
- [ ] Extract tickers from schedule.product array
- [ ] Implement ticker switching functionality
- [ ] Pass ticker parameter to quote/product requests
- [ ] Update transaction creation to use current ticker

### Exchange Status
- [ ] Track exchange_status from product response
- [ ] Convert enum to string name for display
- [ ] Implement is_exchange_open() check
- [ ] Add visual feedback based on status

### Dynamic Values
- [ ] Store manager references instead of static values
- [ ] Get current ticker from manager on each transaction
- [ ] Get current sidepit_id from manager on each transaction

### Communication
- [ ] Switch from REST/JSON to NNG/Protobuf
- [ ] Initialize Push0 socket for transactions
- [ ] Initialize Req0 socket for queries
- [ ] Send serialized protobuf directly

### Display
- [ ] Update position filtering (active + non-zero)
- [ ] Show available tickers in session info
- [ ] Highlight current ticker
- [ ] Show per-contract margin data
- [ ] Handle exchange state colors

---

## 14. Code Examples

### Complete Position Display
```python
def display_positions(self, active_ticker=None):
    if not self.account_state:
        return
    
    # Extract all positions
    all_positions = {}
    contract_margins = self.account_state.get('contract_margins', {})
    
    for symbol, contract_margin in contract_margins.items():
        ticker_positions = contract_margin.get('positions', {})
        for ticker, ticker_pos_data in ticker_positions.items():
            position_data = ticker_pos_data.get('position', {})
            qty = position_data.get('position', 0)
            price = position_data.get('avg_price', 0.0)
            
            # Filter: show active ticker or non-zero positions
            if ticker == active_ticker or qty != 0:
                all_positions[ticker] = {
                    'position': qty,
                    'avg_price': price
                }
    
    # Display filtered positions
    for ticker, pos in all_positions.items():
        print(f"{ticker}: {pos['position']} @ {pos['avg_price']}")
```

### Complete Manager with Ticker Tracking
```python
class TradingManager:
    def __init__(self):
        self.active_ticker = None
        self.available_tickers = []
        self.exchange_status = None
        self.sidepit_id = None
        self.req_client = ReqClient()
    
    def update_product_info(self):
        product_pb = self.req_client.get_active_product(self.active_ticker)
        
        # Extract active ticker
        self.active_ticker = product_pb.active_contract_product.product.ticker
        
        # Extract available tickers
        self.available_tickers = list(
            product_pb.exchange_status.session.schedule.product
        )
        
        # Extract exchange status
        self.exchange_status = product_pb.exchange_status.status.estate
        
        return product_pb
    
    def is_exchange_open(self):
        return self.exchange_status == 2
    
    def switch_ticker(self, ticker_or_index):
        try:
            index = int(ticker_or_index) - 1
            if 0 <= index < len(self.available_tickers):
                ticker = self.available_tickers[index]
            else:
                return False
        except ValueError:
            ticker = ticker_or_index
        
        if ticker in self.available_tickers:
            self.active_ticker = ticker
            return True
        return False
```

---

## 15. Testing Migration

### Verification Steps
1. **Positions Load**: Verify positions display for multiple tickers
2. **Ticker Switch**: Switch between available tickers, verify quotes update
3. **Order Placement**: Place order, verify correct ticker in transaction
4. **Wallet Switch**: Switch wallet, verify correct sidepit_id in transaction
5. **Exchange Status**: Verify UI updates when exchange opens/closes
6. **Contract Margins**: Verify per-contract margin data displays correctly

### Common Issues
- **Stale ticker**: Order goes to wrong ticker → Use manager.active_ticker dynamically
- **Stale ID**: Order signed with wrong key → Use manager.sidepit_id dynamically
- **Empty positions**: Can't find positions → Check contract_margins nesting
- **Enum display**: Shows "6" not "CLOSED" → Use ExchangeState.Name()
- **Reserved keywords**: Error on "as" field → Use as_ or getattr()

---

## Summary

**Core Changes**:
1. Nested structure: `contract_margins[symbol].positions[ticker]`
2. Multiple tickers per session via `schedule.product` array
3. Ticker parameter in requests: `get_quote(ticker)`, `get_active_product(ticker)`
4. Exchange status tracking for UI feedback
5. Dynamic ticker/ID retrieval from managers
6. Direct protobuf via NNG instead of REST/JSON

**Migration Pattern**:
- Track `active_ticker` and `available_tickers`
- Store manager references, not static values
- Extract positions by iterating `contract_margins`
- Convert exchange status enum to string
- Filter positions to show active + non-zero only
