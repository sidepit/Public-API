from bit import PrivateKey
from bit.network import NetworkAPI
import qrcode
import click
from id_manager import SidepitIDManager
from bitcoinlib.wallets import Wallet, wallet_delete_if_exists
from bitcoinlib.keys import Key
from bitcoinlib.transactions import Transaction
from bitcoinlib.scripts import Script
import click
import requests
import sys
import traceback
from time import sleep
from constants import SIDEPIT_WALLET, BLOCKSTREAM_API_URL, MEMPOOL_API_URL



class BitcoinManager():

    # SIDEPIT_WALLET="bc1qessxlswl00aymezl68a69vxfu00mntmcsn6y6u"
    # BLOCKSTREAM_API_URL="https://blockstream.info/api/"
    # MEMPOOL_API_URL="https://mempool.space/api/v1/fees/recommended"

    sidepit_id = ""
    # "LOCK":
    # 1. Send Bitcoin from an external wallet (Coinbase) and transferring it to the Sidepit wallet.| SIDEPIT API
    # 2. Periodically keep checking for funds in external source

    # ---------------- Ignore this for now ------------------
    # 1. IF there is a balance send it to sidepit address
    # 2. If no balance get balance by asking to send bitcoin
    # -------------------------------------------------------

    # "UNLOCK" (withdraw): 
    # 1. Generate (external - ????) wallet address for the user (and check funds - ??).
    # 2. By default we dont want any coins attached to this address
    # 3. Call bitcoin network for transaction (unspent funds - locked balance) to be moved -
    # 3. from Sidepit address to (new address ora users existing address -???)


    def send_bitcoin(self, wif, sender_address, send_amount, recipient_address = SIDEPIT_WALLET):
        # Transaction constants
        # wif=self.wif()
        
        try:
            tx_hash = self.create_and_broadcast_transaction(
                wif,
                sender_address,
                recipient_address,
                send_amount
            )
            if not tx_hash:
                return 0
            click.echo(f"\nTransaction Hash: {tx_hash}")
            click.echo("\n=== Transaction Complete ===")
            sleep(2)
            return send_amount
        except Exception as e:
            click.secho(f"\nFinal Error: {str(e)}", fg='red')
            click.echo("Stack trace:")
            traceback.print_exc()
            return 0

    def btc_to_satoshi(self,btc):
        return int(btc * 100000000)

    def satoshi_to_btc(self,satoshi):
        return satoshi / 100000000

    def get_utxos_from_blockstream(self,address):
        try:
            url =  BLOCKSTREAM_API_URL + "address/" + address + "/utxo"
            response = requests.get(url)
            if response.status_code == 200:
                utxos = response.json()
                total_balance = sum(utxo['value'] for utxo in utxos)
                return utxos, total_balance
            else:
                click.secho(f"Error getting UTXOs: {response.text}", fg='red')
                return [], 0
        except Exception as e:
            click.secho(f"Error getting UTXOs: {str(e)}", fg='red')
            return [], 0

    def get_minimum_fee_rate(self):
        try:
            response = requests.get(MEMPOOL_API_URL)
            if response.status_code == 200:
                fees = response.json()
                return fees.get('economyFee', 10)  # fallback to 10 sat/vB if API fails
            else:
                return 10  # fallback fee rate
        except Exception as e:
            click.secho(f"Error fetching minimum fee: {str(e)}", fg='red')
            return 10  # fallback fee rate

    def get_actual_tx_size(self, t):
        # Get the actual transaction virtual size (vsize)
        t.sign()  # Sign first to get accurate size including signatures
        return len(t.raw_hex()) // 2 #// 4   Convert hex string length to bytes, then to virtual size (vBytes)

    def create_and_broadcast_transaction(self,sender_private_key, sender_address, recipient_address, amount_btc):
        try:
            utxos, total_balance = self.get_utxos_from_blockstream(sender_address)
             
            if not utxos:
                click.echo("No UTXOs found for this address")
                return
            
            amount_satoshi = self.btc_to_satoshi(amount_btc)
            
            # Create transaction first to get actual size
            key = Key(sender_private_key)
            t = Transaction(network='bitcoin')
            
            for utxo in utxos:
                t.add_input(
                    prev_txid=utxo['txid'],  
                    output_n=utxo['vout'],  
                    keys=key,
                    script_type='sig_pubkey',
                    value=utxo['value'],
                    address=sender_address,
                    sequence=0xffffffff,
                    witnesses=None
                )
            
            t.add_output(amount_satoshi, recipient_address)
            
            # Calculate fee based on actual transaction size
            fee_rate = self.get_minimum_fee_rate()
            tx_size = self.get_actual_tx_size(t)
            fee = tx_size * fee_rate

            # Reset transaction with proper amounts including fee
            t = Transaction(network='bitcoin')
            
            for utxo in utxos:
                t.add_input(
                    prev_txid=utxo['txid'],  
                    output_n=utxo['vout'],  
                    keys=key,
                    script_type='sig_pubkey',
                    value=utxo['value'],
                    address=sender_address,
                    sequence=0xffffffff,
                    witnesses=None
                )
            
            total_needed = amount_satoshi + fee
            if total_balance < total_needed:
                click.secho(f"\nInsufficient balance. Have {self.satoshi_to_btc(total_balance)} BTC, need {self.satoshi_to_btc(total_needed)} BTC (including {self.satoshi_to_btc(fee)} BTC fee)" , fg="red")
                return 
            
            t.add_output(amount_satoshi, recipient_address)
            
            change_amount = total_balance - amount_satoshi - fee
            if change_amount > 546:
                t.add_output(change_amount, sender_address)
            
            t.sign()
            raw_tx = t.raw_hex()
            
            try:
                response = requests.post(BLOCKSTREAM_API_URL + 'tx', data=raw_tx)
                if response.status_code == 200:
                    return response.text.strip()
                else:
                    click.echo(f"Failed to broadcast: {response.text}")
                    return 
            except Exception as e:
                click.secho(f"Error broadcasting transaction: {str(e)}", fg='red')
                return 
                
        except Exception as e:
            click.secho(f"\nError: {str(e)}", fg='red')
            click.echo("Stack trace:")
            traceback.print_exc()
            return 

    def set_sidepit_id(self, sidepit_id): 
        self.sidepit_id = sidepit_id
        self.update_balance() 

    def update_balance(self):
        # 2. If no balance get balance by asking to send bitcoin
        utxos = NetworkAPI.get_unspent(self.sidepit_id) # THIS IS YOUR UNLOCK BALANCE
        self.utxo_balance=sum(utxo.amount for utxo in utxos) / 1e8  # Convert satoshis to BTC
     
        

    # https://blockstream.info/api/address/bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4/utxo
    # https://github.com/blockstream/esplora/blob/master/API.md 
    # address = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    # url = f"https://blockstream.info/api/address/{address}/utxo"
    
    def unlock(self):
        pass

    def sweep(self, wif, sender_address, send_amount, recipient_address):
        self.send_bitcoin(wif, sender_address, send_amount, recipient_address)
        return