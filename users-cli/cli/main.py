#!/usr/bin/env python3
import click
from sidepit_cli_handler import SidepitCLIHandler

@click.command()
@click.option('--watch-only', default=None, help='Monitor a trader_id in read-only mode (e.g., bc1...)')
def run_sidepit_cli(watch_only) -> None:
    """
    Sidepit Command-Line Interface (CLI).
    """
    handler = SidepitCLIHandler()
    
    # If watch-only trader_id is provided via command line, set it immediately
    if watch_only:
        try:
            handler.sidepit_id_manager.set_watch_only_id(watch_only)
            click.secho(f"Watching trader: {watch_only} (read-only mode)", fg="yellow")
        except ValueError as e:
            click.secho(f"Error: {e}", fg="red")
            return
    
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