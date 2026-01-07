from tabulate import tabulate
from rich.console import Console
from rich.table import Table
from datetime import datetime, timezone
from rich.text import Text
from rich.panel import Panel
import time

class SidepitQuote:

# Sample JSON data
    data = {
        "epoch": "1733459829167",
        "bar": {
            "ticker": "",
            "epoch": "0",
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0
        },
        "quote": {
            "bidsize": 1,
            "bid": 1008,
            "ask": 1010,
            "asksize": 1,
            "last": 1010,
            "lastsize": 2,
            "upordown": True,
            "ticker": "",
            "epoch": "0"
        },
        "depth": [
            {"b": 1008, "a": 1010, "bs": 1, "as": 1, "level": 0},
            {"level": 1, "b": 1007, "bs": 1, "a": 0, "as": 0},
            {"level": 2, "b": 1000, "bs": 1, "a": 0, "as": 0}
        ],
        "version": 0
    }

    def __init__(self) -> None:
        # Initialize Rich Console
        self.console = Console()
        self.local_timezone = str(datetime.now(timezone.utc).astimezone().tzinfo)


    def display(self, data, last_only=False): 
        # Convert epoch to datetime
        epoch_time = datetime.fromtimestamp(data.epoch / 1000)

        # Get quote data
        quote = data.quote
        if not quote.ticker and not quote.bid:  # Empty quote
            return
        
        arrow = "↑" if quote.upordown else "↓"
        arrow_color = "green" if quote.upordown else "red"
        print("\n")
        last_price = Text("USDBTC ") + Text(f"{quote.last} {arrow}", style=arrow_color) + Text(" SATS/$   ") +  Text(f"{epoch_time}")

        last_price.stylize("bold")
        if not last_only:
            self.console.rule("[bold blue]Exchange Summary")
            self.console.print(last_price)
            
        if last_only:
            self.console.rule(last_price)

        # Display quote info
        quote_table = Table(show_header=True, header_style="bold yellow")
        quote_table.add_column("Bid Size")
        quote_table.add_column("Bid")
        quote_table.add_column("Ask")
        quote_table.add_column("Ask Size")
        quote_table.add_row(
            str(quote.bidsize),
            str(quote.bid),
            str(quote.ask),
            str(quote.asksize),
        )

        if not last_only:
            self.console.rule("[bold green]Quote Info")
            self.console.print(quote_table)

        # Display depth
        depth_table = Table(show_header=True, header_style="bold white")
        depth_table.add_column("Bid Size")
        depth_table.add_column("Bid")
        depth_table.add_column("Ask")
        depth_table.add_column("Ask Size")

        for level in data.depth:
            depth_table.add_row(
                str(level.bs) if level.bs != 0 else "N/A",
                str(level.b) if level.b != 0 else "N/A",
                str(level.a) if level.a != 0 else "N/A",
                str(getattr(level, 'as', 0) if getattr(level, 'as', 0) != 0 else "N/A"),
            )

        if not last_only:
            self.console.rule("[bold cyan]Order Book Depth")
            self.console.print(depth_table)

    product_data = {
        "active_contract_product": {
            "contract": {
                "symbol": "USDBTC",
                "unit_size": 500,
                "unit": "USD",
                "price_quote": "SAT",
                "price_quote_units": 1,
                "tic_min": 1,
                "tic_value": 500,
                "price_limit_percent": 25,
                "initial_margin": "200000",
                "maint_margin": "100000",
                "position_limits": 200,
                "trading_open_time": "50400000",
                "trading_close_time": "7200000",
                "trading_open_time_zone": "03:00:00 America/Los_Angeles",
                "trading_close_time_zone": "00:00:00 America/Los_Angeles"
            },
            "product": {
                "ticker": "USDBTCH26",
                "contract_symbol": "USDBTC",
                "expiration_date": "1774569600000",
                "start_trading_date": "1758844800000",
                "is_active": True
            },
            "schedule": {
                "date": "1767744000000",
                "trading_open_time": "1767697200000",
                "trading_close_time": "1767772800000",
                "product": ["USDBTCH26", "USDBTCM26"]
            }
        },
        "exchange_status": {
            "session": {
                "session_id": "1767744000000",
                "schedule": {
                    "date": "1767744000000",
                    "trading_open_time": "1767697200000",
                    "trading_close_time": "1767772800000",
                    "product": ["USDBTCH26", "USDBTCM26"]
                },
                "prev_session_id": "1767657600000"
            },
            "status": {
                "estate": "EXCHANGE_CLOSED",
                "session_id": "1767744000000"
            }
        },
        "contractbar": {
            "day_open": 1115,
            "day_high": 1115,
            "day_low": 1104,
            "day_close": 1104,
            "day_volume": 29,
            "high": 1115,
            "low": 999,
            "volume": 90,
            "open_interest": 90,
            "previous_close": 1111,
            "ticker": "",
            "epoch": "0"
        }
    }

    def convert_timestamp(self,ts,strfmt = "%Y-%m-%d %H:%M:%S "):
        return datetime.fromtimestamp(int(ts) / 1000).strftime(strfmt) + self.local_timezone

    def display_product(self, api_data): 
        # Extract protobuf objects
        contract = api_data.active_contract_product.contract
        product = api_data.active_contract_product.product
        status = api_data.exchange_status.status
        session = api_data.exchange_status.session
        contractbar = api_data.contractbar
        
        contract_info = f"""
        [bold cyan]Symbol[/bold cyan]: {contract.symbol} ({product.ticker})
        [bold cyan]Expiration[/bold cyan]: {self.convert_timestamp(product.expiration_date)}
        [bold cyan]Unit[/bold cyan]: {contract.unit} ({contract.unit_size} {contract.unit})
        [bold cyan]Quote[/bold cyan]: {contract.price_quote} per {contract.price_quote_units} {contract.unit}
        [bold cyan]Minimum Tic[/bold cyan]: {contract.tic_min} 
        [bold cyan]Tic Value[/bold cyan]: {contract.tic_value} {contract.price_quote}S
        [bold cyan]Margins (BTC)[/bold cyan]: Initial - {int(contract.initial_margin or 0)/1e8} / Maintenance - {int(contract.maint_margin or 0)/1e8}
        [bold cyan]Position Limits[/bold cyan]: {contract.position_limits}
        [bold cyan]Trading Times[/bold cyan]: 
            Start - {self.convert_timestamp(contract.trading_open_time,"%H:%M:%S ")}
            End - {self.convert_timestamp(contract.trading_close_time,"%H:%M:%S ")}
        """

        contract_panel = Panel(contract_info, title="Contract Details", border_style="green")

        # Session and Status Information
        session_info = f"""
        [bold cyan]Exchange Status[/bold cyan]: {status.estate}
        [bold cyan]Session ID[/bold cyan]: {session.session_id}
        [bold cyan]Session Times[/bold cyan]: 
            Start - {self.convert_timestamp(session.schedule.trading_open_time)}
            End - {self.convert_timestamp(session.schedule.trading_close_time)}
        """

        session_panel = Panel(session_info, title="Session Information", border_style="blue")

        # Market Data Bar
        market_data_table = Table(title="Market Data", show_header=True, header_style="bold magenta")
        market_data_table.add_column("Metric", style="cyan")
        market_data_table.add_column("Value", style="bold yellow")

        market_data_table.add_row("Day Open", str(contractbar.day_open))
        market_data_table.add_row("Day High", str(contractbar.day_high))
        market_data_table.add_row("Day Low", str(contractbar.day_low))
        market_data_table.add_row("Day Close", str(contractbar.day_close))
        market_data_table.add_row("Day Volume", str(contractbar.day_volume))
        market_data_table.add_row("High", str(contractbar.high))
        market_data_table.add_row("Low", str(contractbar.low))
        market_data_table.add_row("Volume", str(contractbar.volume))
        market_data_table.add_row("Open Interest", str(contractbar.open_interest))
        market_data_table.add_row("Previous Close", str(contractbar.previous_close))

        # Display Panels
        self.console.print(contract_panel)
        self.console.print(session_panel)
        self.console.print(market_data_table)

if __name__ == '__main__':
    quote = SidepitQuote() 
    quote.display_product(quote.product_data)
    quote.display(quote.data)
