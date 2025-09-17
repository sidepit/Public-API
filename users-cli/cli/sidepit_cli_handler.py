import click
from time import sleep
import re
from id_manager import SidepitIDManager
from bitcoin_manager import BitcoinManager
from sidepit_manager import SidepitManager
from sidepit_api_client import SidepitApiClient
from pycoin.symbols.btc import network
import os
from tabulate import tabulate
from rich.console import Console
from rich.table import Table
from datetime import datetime
from rich.text import Text
from rich.panel import Panel

class SidepitCLIHandler:
    sidepit_id = "" 

    def __init__(self) -> None:
        self.console = Console()
        self.sidepit_id_manager = SidepitIDManager() 
        self.bitcoin_manager = BitcoinManager()
        self.sidepit_manager = SidepitManager()

    def balance_menu(self) -> None:
        self.sidepit_manager.print_last()
        click.secho("\nPlease choose an option:", fg="cyan")
        click.secho("'lock' bitcoin to trade on sidepit", fg="yellow")
        click.secho("'unlock' bitcoin from sidepit, back to this wallet", fg="green")
        click.secho("'sweep' all bitcoin to another wallet", fg="blue")
        click.secho("'export' private keys for this wallet", fg="magenta")
        click.secho("'manage' add or switch wallet", fg="magenta")
        if self.sidepit_manager.available_balance > 0:
            click.secho("'trade' ", fg="magenta")
        else:
            click.secho("'info' get Ssidepit exchange information", fg="magenta")

        click.secho("'quit'", fg="red")

    def setup_id(self) -> None:
        self.sidepit_manager.print_last()
        click.secho(f"Choose to create/import Sidepit_Id and store keys at: {self.sidepit_id_manager.wallet_file_path}", fg="cyan")
        click.secho("'create' New Sidepit Id on this computer", fg="green")
        click.secho("'import' Sidepit Id with 'wif' private keys", fg="magenta")
        click.secho("'manage' add or switch wallet", fg="magenta")
        click.secho("'quit'", fg="red")

    def trading_menu(self) -> None:
        self.sidepit_manager.print_last()
        click.secho("\n'new', 'cancel', 'quote','product','pos','open' orders,'closed' orders, 'all' orders, 'lock','quit',", fg="green")
        # click.secho("'sell'", fg="red")
        # click.secho("'cancel'", fg="blue")
        # click.secho("'quote'", fg="blue")
        # click.secho("'pos' get positions", fg="magenta")
        # click.secho("'open' get open orders", fg="magenta") 
        # click.secho("'closed' get closed orders", fg="magenta")
        # click.secho("'all' get all orders", fg="magenta")
        # click.secho("'lock' show lock/unlock menu", fg="red")
        # click.secho("'quit'", fg="red")

    def print_trading(self):
        # click.echo(f"Your Sidepit ID: {self.sidepit_manager.sidepit_id}")
        # click.echo(f"Available Balance (satoshis): {self.sidepit_manager.available_balance}")
        self.sidepit_manager.print_pos(True)

    def ask_user(self, prompt_text, default=None):
        return click.prompt(prompt_text, default=default)

    def do_neworder(self, side, price, size): 
        self.sidepit_api_trader.do_neworder(side, price, size)

    def do_cancel(self, oid): 
        return "orderid"

    def handle_trading_actions(self) -> None:
        self.sidepit_api_trader = SidepitApiClient(self.sidepit_manager.sidepit_id,self.sidepit_id_manager) 

        self.sidepit_manager.print_product()
        self.sidepit_manager.print_quote()
        self.print_trading()
        while True:

            self.trading_menu()
            action = click.prompt("\nEnter action") 
            if action == "quit":
                click.secho("Thank you for using the Sidepit CLI, Goodbye!", fg="cyan")
                return
            elif action == "new":
                side = 1
                sidebs = self.ask_user("side? b/s ")
                side = 1 if sidebs == 'b' else -1
                price = self.ask_user("price")
                size = self.ask_user("size")

                confirm = "Buy " if side == 1 else "Sell " 
                confirm += size + " @ " + price    

                yn = self.ask_user(confirm + " y/n")

                if yn == 'y': 
                    self.do_neworder(int(side), int(price), int(size))  
                continue

            elif action == "cancel":
                oid = self.ask_user("enter orderid to cancel")
                yn = self.ask_user("cancel " + oid + "? \n y/n")
                if yn == 'y':
                    self.do_cancel(oid) 
                continue
            elif action == "quote":
                self.sidepit_manager.print_product()
                self.sidepit_manager.print_quote()
                continue
            elif action == "product":
                self.sidepit_manager.print_product()
                continue
            elif action == "open":
                self.sidepit_manager.update_balance()
                self.print_trading()
                self.sidepit_manager.print_open()
                continue 
            elif action == "closed":
                self.sidepit_manager.update_balance()
                self.print_trading()
                self.sidepit_manager.print_filled()
                continue 
            elif action == "all":
                self.sidepit_manager.update_balance()
                self.print_trading()
                self.sidepit_manager.print_all()
                continue            
            elif action == "lock":
                self.handle_balance_actions()
            self.print_trading()

    def handle_balance_actions(self) -> None:
        while True:
            self.bitcoin_manager.update_balance()

            click.echo(f"Your Sidepit ID: {self.sidepit_manager.sidepit_id}")
            click.echo(f"Locked Balance: {self.sidepit_manager.net_locked / 1e8}")
            click.echo(f"Pending Locked Balance: {self.sidepit_manager.pnding_locked_balance} SATS (1/100,000,000 BTC)")
            click.echo(f"Unlocked Balance: {self.bitcoin_manager.utxo_balance}")
            click.echo(f"Available Balance (satoshis): {self.sidepit_manager.available_balance}")

            self.balance_menu()
            
            action = click.prompt("\nEnter action") 
            if action == "quit":
                click.secho("Thank you for using the Sidepit CLI, Goodbye!", fg="cyan")
                return
            elif action == "lock":
                self.lock()
            elif action == "sweep":
                self.sweep()
            elif action == "unlock":
                self.bitcoin_manager.unlock()
            elif action == "export key" or action == 'export':
                click.echo(f"\n\nYour WIF private key: {self.sidepit_id_manager.read_wif()} \n\n")
            elif action == "manage":
                self.manage_accounts()
            elif action == "trade":
                return 
            elif action == "info": 
                self.sidepit_manager.print_product()

    def handle_key_actions(self) -> None:
        while not self.sidepit_id_manager.have_id():
            self.setup_id()
            action = click.prompt("Enter action") 
            if action == "quit":
                click.secho("Thank you for using the Sidepit CLI, Goodbye!", fg="cyan")
                return
            elif action == "create":
                wallet_name=self.sidepit_id_manager.create_sidepit_id()
                click.echo(f"New Sidepit Id created with name: {wallet_name}")
            elif action == "import" or action == "wif":
                wif = click.prompt("Enter WIF private key")
                self.sidepit_id_manager.import_wif(wif)
        self.new_id()

    def have_folder(self) ->bool:
        if self.sidepit_id_manager.have_folder():
            return True
        return False
    def create_folder(self) -> None:
        self.sidepit_id_manager.create_folder()

    # def set_wallet_path(self) -> None:
    #     items = os.listdir(FOLDER_WALLETS_PATH)
    #     self.sidepit_id_manager.wallet_file_path = self.sidepit_id_manager.FOLDER_WALLETS_PATH + "/"
    #     pass

    def have_id(self) -> bool: 
        if self.sidepit_id != "": 
            return True 
        if not self.sidepit_id_manager.have_id(): 
            return False
        self.new_id()   

    def new_id(self): 
        hold_id = self.sidepit_id_manager.get_id()
        if hold_id == self.sidepit_id: 
            return
        self.sidepit_id = hold_id
        self.sidepit_manager.use_id(self.sidepit_id)
        self.bitcoin_manager.set_sidepit_id(self.sidepit_id)



    def get_banned_accounts(self):
        return []
    

    def is_valid_btc_address(self, address):
        # Check for basic address format
        if not re.match(r"^(1|3|bc1)[a-zA-HJ-NP-Z0-9]{25,90}$", address):
            return False
        try:
            # Use pycoin to parse the address
            network.parse.address(address)
            return True
        except ValueError:
            return False

    def check_address(self, user_address, address,bitcoin_manager):
        banned_account = self.get_banned_accounts()


        if not self.is_valid_btc_address(address):
            click.secho("invalid account type", fg="red")
            return True

        if address==user_address:
            click.secho("cant send to your own account", fg="red")
            return True
        if address==bitcoin_manager.SIDEPIT_WALLET:
            click.secho("cant send to the sidepit account", fg="red")
            return True
        if address in banned_account:
            click.secho("cant send to banned accounts", fg="red")
            return True
        return False

    def sweep(self) -> None:
        sidepit_id = self.sidepit_id_manager.get_id()
        recipient_address = click.prompt("enter recipient address")
        if (self.check_address(sidepit_id, recipient_address, self.bitcoin_manager) ):
            return
        
        send_amount = click.prompt("Enter amount to send in BTC (enter all for all of unlock balance)")

        if send_amount == "all":
            send_amount = (self.bitcoin_manager.utxo_balance() * 1e8 - 1000) / 1e8
        else:
            send_amount = float(send_amount)
        self.bitcoin_manager.sweep(self.sidepit_id_manager.wif(),sidepit_id, send_amount, recipient_address)

    def lock(self):
        while self.bitcoin_manager.utxo_balance == 0:
            self.sidepit_manager.print_last()
            click.echo("\nSend bitcoin from any wallet to your Sidepit ID address and we will lock it once its received.")
            num = 0
            while num < 30:
                num += 1
                print(".", end="", flush=True) 
                sleep(2)
            self.bitcoin_manager.update_balance()
            
        click.echo(f"Funds received! Total balance: {self.bitcoin_manager.utxo_balance} BTC")
        send_amount = click.prompt("Enter amount to send in BTC(enter all for all of unlock balance)")
        if send_amount == "all":
            send_amount = (self.bitcoin_manager.utxo_balance * 1e8 - 1000) / 1e8
        else:
            send_amount = float(send_amount)
        sent_amount = self.bitcoin_manager.send_bitcoin(self.sidepit_id_manager.wif(),self.sidepit_manager.sidepit_id,send_amount)
        if sent_amount:
            click.echo('\nBitcoin from sidepit ID have been forwarded to Sidepit deposit address.')
        return

    def unlock():
        pass

    def update_data(self,address):
        self.sidepit_manager.use_id(address)
        self.bitcoin_manager.set_sidepit_id(address)
        pass


    def manage_accounts(self):
        self.print_accounts()
        self.handle_accounts_actions()


    def print_accounts(self) -> None:
        # Create a table
        table = Table(title="Accounts")

        # Add columns
        table.add_column("Wallet Name", style="cyan", justify="center")
        table.add_column("Wallet Address", style="magenta", justify="center")
        table.add_column("Locked Balance", style="green", justify="center")
        table.add_column("Pending Locked Balance", style="red", justify="right")
        table.add_column("Unlocked Balance", style="green", justify="right")
        table.add_column("Available Balance (satoshis)", style="green", justify="right")


        try:
            # List all items in the folder
            items = os.listdir(self.sidepit_id_manager.FOLDER_WALLETS_PATH)
            original_address=self.sidepit_id_manager.load_sidepit_id()
            # Filter and print only files
            for item in items:
                item_path = os.path.join(self.sidepit_id_manager.FOLDER_WALLETS_PATH, item)
                if os.path.isfile(item_path):
                    self.sidepit_id_manager.wallet_file_path = item_path
                    address=self.sidepit_id_manager.load_sidepit_id()
                    self.update_data(address)
                    net_locked=str(self.sidepit_manager.net_locked / 1e8)
                    pnding_locked_balance = str(self.sidepit_manager.pnding_locked_balance)
                    utxo_balance = str(self.bitcoin_manager.utxo_balance)
                    available_balance = str(self.sidepit_manager.available_balance)

                    if item == self.sidepit_id_manager.active_wallet:
                        item = Text(item, style="bold red")

                    table.add_row(item[3:], address, net_locked, pnding_locked_balance, utxo_balance, available_balance)
            self.sidepit_id_manager.update_active_wallet_address(self.sidepit_id_manager.active_wallet)
            self.update_data(original_address)
        except FileNotFoundError:
            print(f"The folder '{self.sidepit_id_manager.FOLDER_WALLETS_PATH}' does not exist.")
        except Exception as e:
            print(f"An error occurred: {e}")

        # click.echo(f"Your Sidepit ID: {self.sidepit_manager.sidepit_id}")
        # click.echo(f"Locked Balance: {self.sidepit_manager.net_locked / 1e8}")
        # click.echo(f"Pending Locked Balance: {self.sidepit_manager.pnding_locked_balance} SATS (1/100,000,000 BTC)")
        # click.echo(f"Unlocked Balance: {self.bitcoin_manager.utxo_balance}")
        # click.echo(f"Available Balance (satoshis): {self.sidepit_manager.available_balance}")

        # Print the table
        self.sidepit_manager.print_last()
        self.console.print(table)

    def print_account_action_list(self):
        self.sidepit_manager.print_last()
        click.secho(f"'change name' Of a wallet", fg="cyan")
        click.secho("'switch' switch to a different wallet", fg="green")
        click.secho("'import' Sidepit Id with 'wif' private keys", fg="magenta")
        click.secho("'create' New Sidepit Id on this computer", fg="magenta")
        click.secho("'quit'", fg="red")

    def handle_accounts_actions(self):
        while True:

            self.print_account_action_list()
            
            action = click.prompt("\nEnter action") 
            if action == "quit":
                return
            elif action == "change name":
                old_name=click.prompt("\nEnter the name of the wallet you want to change")
                if not self.sidepit_id_manager.check_if_file_exists(old_name):
                    click.secho("You have enterd a wallet that does not exist", fg="red")
                    continue
                new_name=click.prompt("Enter new name")
                if new_name == old_name:
                    click.secho("You have enterd the same name", fg="red")
                    continue
                self.sidepit_id_manager.change_name(old_name,new_name)
            elif action == "switch":
                new_active_wallet_name=click.prompt("\nEnter the name of the wallet you want to switch too")
                if not self.sidepit_id_manager.check_if_file_exists(new_active_wallet_name):
                    click.secho("You have enterd a wallet that does not exist", fg="red")
                    continue
                new_active_wallet_name = ".sp" + new_active_wallet_name
                if new_active_wallet_name == self.sidepit_id_manager.active_wallet:
                    continue
                self.switch_wallet(new_active_wallet_name)
                continue
            elif action == "import":
                wif = click.prompt("Enter WIF private key")
                wallet_name=self.sidepit_id_manager.import_wif(wif)
                click.echo(f"New Sidepit Id created with name: {wallet_name}")
                new_active_wallet_name = ".sp" + wallet_name
                self.switch_wallet(new_active_wallet_name)
                click.echo("switched to new account")
            elif action == "create":
                wallet_name = self.sidepit_id_manager.create_sidepit_id()
                click.echo(f"New Sidepit Id created with name: {wallet_name}")
                new_active_wallet_name = ".sp" + wallet_name
                self.switch_wallet(new_active_wallet_name)
                click.echo("switched to new account")
    
    def switch_wallet(self, new_active_wallet_name):
        self.sidepit_id_manager.update_active_wallet_address(new_active_wallet_name)
        address=self.sidepit_id_manager.load_sidepit_id()
        self.update_data(address)

