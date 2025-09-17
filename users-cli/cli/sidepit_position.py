from rich.console import Console
from rich.table import Table
from rich.panel import Panel
# from datetime import datetime

class SidepitTrader:
    ACCOUNT_METRICS = [
        ("Net Locked", "net_locked"),
        ("Margin Required", "margin_required"),
        ("Available Balance", "available_balance"),
        ("Available Margin", "available_margin"),
        ("Realized PnL", "realized_pnl"),
        ("Unrealized PnL", "unrealized_pnl")
    ]

    def __init__(self) -> None:
        self.console = Console()
        self.data = None 
        self.account_state = None
        self.positions = None
        self.orderfills = None
        self.locks = None

    # Example JSON data
    # data = {
    #     "traderid": "bc1qyf9txm2wrp52tclchlszmav3q0txq7yrgplzhu",
    #     # Truncated data; assume the rest follows the given structure
    # }
    # Convert timestamps to human-readable datetime
    # def convert_timestamp(ts):
    #     return datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    
    def display_trader_info(self) -> None:
        if not self.account_state:
            return

        trader_info = f"""
        [bold cyan]Trader ID[/bold cyan]: {self.data['traderid']}
        [bold cyan]Sidepit ID[/bold cyan]: {self.account_state['sidepit_id']}
        [bold cyan]Public Key[/bold cyan]: {self.account_state['pubkey']}
        """
        panel = Panel(trader_info, title="Trader Information", border_style="cyan")
        self.console.print(panel)


    def create_account_table(self) -> None:
        if not self.account_state: 
            return 
        
        # Table
        table = Table(title="Account State", header_style="bold magenta")
        # Columns
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold yellow")
        # Rows
        for label, key in self.ACCOUNT_METRICS:
            table.add_row(label, self.account_state[key])
        # Print  
        self.console.print(table)


    def display_order_details(self, type = "all") -> None:
        if not self.orderfills:
            return 
                   
        for order_id, order_data in self.orderfills.items():
            if type == "open" and int(order_data["order"]["remaining_qty"]) == 0:
                continue

            if type == "filled" and int(order_data["order"]["filled_qty"]) == 0:
                continue

            order = order_data["order"]
            fills = order_data["fills"]
            
            order_info = f"""
            [bold cyan]Order ID[/bold cyan]: {order['orderid']}
            [bold cyan]Ticker[/bold cyan]: {order['ticker']}
            [bold cyan]Side[/bold cyan]: {"Buy" if order['side'] == 1 else "Sell"}
            [bold cyan]Price[/bold cyan]: {order['price']}
            [bold cyan]Filled Qty[/bold cyan]: {order['filled_qty']}
            [bold cyan]Avg Price[/bold cyan]: {order['avg_price']}
            """
            panel = Panel(order_info, title="Order Details", border_style="blue")
            self.console.print(panel)
            self.display_fills(fills)

    def display_fills(self, fills) -> None:
        if fills:          
            # Table
            table = Table(title="Fills", header_style="bold cyan")
            # Columns
            table.add_column("Aggressive ID", style="cyan")
            table.add_column("Price", style="bold yellow")
            table.add_column("Quantity", style="bold yellow")
            table.add_column("Microtime", style="magenta")
            # Rows
            for fill in fills:
                aggressive_id = fill["agressiveid"]
                price = str(fill["price"])
                qty = str(fill["qty"])
                microtime = str(fill["microtime"])
                table.add_row(aggressive_id, price, qty, microtime)
            # Print
            self.console.print(table)
        # else:
        #     panel = Panel("[bold red]No fills for this order.[/bold red]", border_style="red")
        #     self.console.print(panel)

     
    def display_positions(self) -> None:
        if self.positions:
            # Table
            table = Table(title="Open Positions", header_style="bold green")
            # Columns
            table.add_column("Ticker", style="cyan")
            table.add_column("Position Size", style="bold yellow")
            table.add_column("Average Price", style="bold yellow")
            # Rows
            for ticker, details in self.positions.items():
                position = str(details["position"])
                avg_price = str(details["avg_price"])
                table.add_row(ticker, position, avg_price)
            # Print
            self.console.print(table)
        # else:
        #     panel = Panel("[bold red]No open positions.[/bold red]", border_style="red")
        #     self.console.print(panel)


    def display_locks(self) -> None:
        if self.locks:
            # Table
            table = Table(title="Locks", header_style="bold cyan")
            # Columns
            table.add_column("TxID", style="cyan")
            table.add_column("BTC Address", style="bold yellow")
            table.add_column("Locked Sats", style="bold yellow")
            table.add_column("Is Pending", style="bold magenta")
            # Rows
            for lock in self.locks:
                txid = lock["txid"] 
                btc_address = lock["btc_address"]
                lock_sats = lock["lock_sats"]
                is_pending = str(lock["is_pending"])
                table.add_row(txid, btc_address, lock_sats, is_pending)
            # Print
            self.console.print(table)
        else:
            panel = Panel("[bold red]No locks available.[/bold red]", border_style="red")
            self.console.print(panel)

    def new_data(self, data): 
        try: 
            self.data = data
            self.account_state = self.data.get("accountstate", None)
            self.positions = self.account_state.get("positions", None)
            self.orderfills = self.data.get("orderfills", None)
            self.locks =  self.data.get("locks", None)
        except Exception as e:
            return


    def display(self) -> None: 
        self.display_trader_info()
        # Display Account State
        if not self.account_state: 
            print(f"No Account state - wait for next open type: product in your sidepit terminal.")
            return

        self.create_account_table()
        # Display Open Positions
        self.display_positions()
        # Display Order Fills
        self.display_order_details()
        # Display Locks
        self.display_locks() 
