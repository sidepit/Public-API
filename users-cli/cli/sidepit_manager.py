import requests
import click
from secp256k1 import PrivateKey
from tabulate import tabulate
from datetime import datetime
from sidepit_quote import SidepitQuote
from sidepit_position import SidepitTrader
from rich.console import Console
from rich.table import Table
from constants import SIDEPIT_API_URL
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../python-client'))
from req_client import SidepitReqClient

class SidepitManager:
    DEBUG=False
    def __init__(self) -> None:
        self.quotron = SidepitQuote()
        self.terminal = SidepitTrader()
        self.available_balance = 0
        self.net_locked = 0 
        self.pnding_locked_balance = 0
        self.positions = None
        self.req_client = None
        self._init_req_client()

    def _init_req_client(self):
        """Initialize the request client for protobuf communication"""
        try:
            from constants import SIDEPIT_REQ_HOST, SIDEPIT_REQ_PORT, SIDEPIT_REQ_PROTOCOL
            self.req_client = SidepitReqClient(
                protocol=SIDEPIT_REQ_PROTOCOL,
                host=SIDEPIT_REQ_HOST,
                port=SIDEPIT_REQ_PORT
            )
        except Exception as e:
            click.secho(f"Warning: Could not connect to request server: {e}", fg='yellow')
            self.req_client = None
    
    def use_id(self, sidepit_id) -> None:
        self.sidepit_id = sidepit_id
        # print("using id", sidepit_id)
        self.update_balance()
   
    def update_balance(self):
        try:
            # Use protobuf client - store protobuf object
            self.positions_data = self.req_client.get_positions(self.sidepit_id)
            # For compatibility with existing code that needs JSON
            from google.protobuf.json_format import MessageToDict
            self.get_positions_json = MessageToDict(self.positions_data, 
                                                    preserving_proto_field_name=True,
                                                    including_default_value_fields=True)
            self.terminal.new_data(self.get_positions_json)

            tx_arr=[int(tx['lock_sats']) for tx in self.get_positions_json['locks'] if tx['is_pending']]
            self.pnding_locked_balance=sum(tx_arr)

            self.accountstate = self.get_positions_json.get("accountstate", None)
            if self.accountstate is not None: 
                self.available_balance = int(self.accountstate['available_balance'])
                self.net_locked = int(self.accountstate['net_locked'])
                self.positions = self.accountstate['positions']


                if self.DEBUG:
                    for key in self.get_positions_json.keys():
                        print(f"'{key}' with length {len(key)}")

                    print("Keys in response_json:", list(self.get_positions_json.keys()))
                    print(type(next(iter(self.get_positions_json.keys()))))
                    print(type(self.get_positions_json))
                    print(self.get_positions_json["orderfills"])
            else:
                self.available_balance = 0
                self.net_locked = 0
                self.positions = None

            self.orderfills = self.get_positions_json.get("orderfills", None)
            if self.orderfills is not None: 
                self.open_orders = [ 
                    value["order"] 
                    for key, value in self.orderfills.items()
                    if int(value["order"]["remaining_qty"]) > 0
                ]
            else:
                print("none")
                self.open_orders = []

        except Exception as ex:
            self.get_positions_json = None 
            accountstate = None 
            return

    def print_pos(self, pretty: bool = False ):
        if pretty:
            self.terminal.display_trader_info()
            self.terminal.create_account_table()
            self.terminal.display_positions()
            return

        print("Positions:")
        if self.positions is None: 
            print(f"  No Position Data ")
            return

        for ticker, details in self.positions.items():
            print(f"  {ticker}: Position = {details['position']}, Avg Price = {details['avg_price']}")

    def print_open(self, pretty = False): 
        if pretty:
            self.terminal.display_order_details("open")
            return

        rows = []
        for key, data in self.orderfills.items():
            if int(data["order"]["remaining_qty"]) == 0:
                continue
             
            order = data["order"]
            fills = data["fills"]

            # Add main order row
            rows.append([
                order["ticker"],
                "Buy" if order["side"] == 1 else "Sell",
                order["price"],
                order["open_qty"],
                order["remaining_qty"],
                order["filled_qty"] if order["filled_qty"] != 0 else None,
                order["avg_price"] if order["filled_qty"] != 0 else None,
                order["canceled_qty"] if order["canceled_qty"] != 0 else None,
                order["pass_fill_qty"] if order["pass_fill_qty"] != 0 else None,
                order["agres_fill_qty"] if order["agres_fill_qty"] != 0 else None,
                order["agres_avg_price"] if order["agres_avg_price"] != 0 else None,
                order["orderid"],
                datetime.fromtimestamp(int(order["update_time"])/1000)
            ])

            # Add fill rows for the order
            for fill in fills:
                rows.append([
                    "",
                    "",
                    "",
                    "",
                    f" fill",
                    fill["qty"],
                    fill["price"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    datetime.fromtimestamp(int(fill["microtime"])/1000000)
                ])

        headers = ["Ticker", "Side", "Price", "Size", "Remaining", "Filled", "Avg Price", "Canceled", "Pass Fills", "Agres Fills", "Agres Avg", "Order ID", "Time"]

        # Identify columns to keep (i.e., columns with at least one non-empty value)
        columns_to_keep = [i for i in range(len(headers)) if any(row[i] for row in rows)]

        # Filter headers and rows to keep only non-empty columns
        filtered_headers = [headers[i] for i in columns_to_keep]
        filtered_rows = [[row[i] for i in columns_to_keep] for row in rows]

        print(tabulate(filtered_rows, headers=filtered_headers, tablefmt="pretty"))

    def print_filled(self, pretty = False): 
        if pretty:
            self.terminal.display_order_details("filled")
            return

        rows = []
        for key, data in self.orderfills.items():
            if int(data["order"]["filled_qty"]) == 0:
                continue
                
            order = data["order"]
            fills = data["fills"]

            # Add main order row
            rows.append([
                order["ticker"],
                "Buy" if order["side"] == 1 else "Sell",
                order["price"],
                order["open_qty"],
                order["remaining_qty"],
                order["filled_qty"] if order["filled_qty"] != 0 else None,
                order["avg_price"] if order["filled_qty"] != 0 else None,
                order["canceled_qty"] if order["canceled_qty"] != 0 else None,
                order["pass_fill_qty"] if order["pass_fill_qty"] != 0 else None,
                order["agres_fill_qty"] if order["agres_fill_qty"] != 0 else None,
                order["agres_avg_price"] if order["agres_avg_price"] != 0 else None,
                order["orderid"],
                datetime.fromtimestamp(int(order["update_time"])/1000)
            ])

            # Add fill rows for the order
            for fill in fills:
                rows.append([
                    "",
                    "",
                    "",
                    "",
                    f" fill",
                    fill["qty"],
                    fill["price"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    datetime.fromtimestamp(int(fill["microtime"])/1000000)
                ])

        headers = ["Ticker", "Side", "Price", "Size", "Remaining", "Filled", "Avg Price", "Canceled", "Pass Fills", "Agres Fills", "Agres Avg", "Order ID", "Time"]

        # Identify columns to keep (i.e., columns with at least one non-empty value)
        columns_to_keep = [i for i in range(len(headers)) if any(row[i] for row in rows)]

        # Filter headers and rows to keep only non-empty columns
        filtered_headers = [headers[i] for i in columns_to_keep]
        filtered_rows = [[row[i] for i in columns_to_keep] for row in rows]

        print(tabulate(filtered_rows, headers=filtered_headers, tablefmt="pretty"))

    def print_all(self, pretty = False): 
        if pretty:
            self.terminal.display_order_details("filled")
            return

        ####
        table = Table(title="All Orders", header_style="bold cyan")
        ####
        rows = []
        for key, data in self.orderfills.items():
             
            order = data["order"]
            fills = data["fills"]

            # Add main order row
            rows.append([
                order["ticker"],
                "Buy" if order["side"] == 1 else "Sell",
                order["price"],
                order["open_qty"],
                order["remaining_qty"],
                order["filled_qty"] if order["filled_qty"] != 0 else None,
                order["avg_price"] if order["filled_qty"] != 0 else None,
                order["canceled_qty"] if order["canceled_qty"] != 0 else None,
                order["pass_fill_qty"] if order["pass_fill_qty"] != 0 else None,
                order["agres_fill_qty"] if order["agres_fill_qty"] != 0 else None,
                order["agres_avg_price"] if order["agres_avg_price"] != 0 else None,
                order["orderid"],
                datetime.fromtimestamp(int(order["update_time"])/1000)
            ])

            # Add fill rows for the order
            for fill in fills:
                rows.append([
                    "",
                    "",
                    "",
                    "",
                    f"fill",
                    fill["qty"],
                    fill["price"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    datetime.fromtimestamp(int(fill["microtime"])/1000000)
                ])

        headers = [
            "Ticker", "Side", "Price", "Size", "Remaining", "Filled", "Avg Price", 
            "Canceled", "Pass Fills", "Agres Fills", "Agres Avg", "Order ID", "Time"
        ]

        ######
        new_to_keep = []
        for i in range(len(headers)):
            for row in rows:
                if row[i]:
                    new_to_keep.append(i) 
                    break 
        ######
        # Identify columns to keep (i.e., columns with at least one non-empty value)
        columns_to_keep = [i for i in range(len(headers)) if any(row[i] for row in rows)]


        ##########
        for i in columns_to_keep:
            table.add_column(headers[i], style="yellow", overflow="fold")
        #########
        # Filter headers and rows to keep only non-empty columns
        filtered_headers = [headers[i] for i in columns_to_keep]

        #############
        for row in rows:
            filtered_row = []
            for i in columns_to_keep:
                filtered_row.append(str(row[i]))
            table.add_row(*filtered_row)
        #############
        Console().print(table)

        #######
        # click.secho('OLD:', fg="red")
        # filtered_rows = [[row[i] for i in columns_to_keep] for row in rows]
        # print(tabulate(filtered_rows, headers=filtered_headers, tablefmt="pretty"))

    def print_quote(self):
        quote_pb = self.req_client.get_quote()
        self.quotron.display(quote_pb)

    def print_last(self):
        quote_pb = self.req_client.get_quote()
        self.quotron.display(quote_pb, last_only=True)

    def print_product(self):
        product_pb = self.req_client.get_active_product()
        self.quotron.display_product(product_pb)

    def active(self) -> bool:
        return self.pnding_locked_balance > 0 or self.available_balance != 0 or self.net_locked > 0 
    