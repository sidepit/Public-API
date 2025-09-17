#!/usr/bin/env python3
import click
from sidepit_cli_handler import SidepitCLIHandler

@click.command()
def run_sidepit_cli() -> None:
    """
    Sidepit Command-Line Interface (CLI).
    """
    handler = SidepitCLIHandler()
    
    click.secho("Welcome to the Sidepid CLI!\n", fg="cyan")

    if not handler.have_folder():
        handler.create_folder()

    if not handler.have_id():
        handler.handle_key_actions()

    if not handler.have_id(): 
        return 

    if not handler.sidepit_manager.active():  
        handler.handle_balance_actions()

    if not handler.sidepit_manager.active():
        return 
    
    handler.handle_trading_actions()

    return

if __name__ == '__main__':
    run_sidepit_cli()