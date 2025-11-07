from web3 import Web3
from eth_account import Account
import random
import time
from pathlib import Path
from rich.console import Console
from rich.prompt import IntPrompt

console = Console()

CHAIN_NAME = "Somnia Testnet"
RPC_URL = "https://dream-rpc.somnia.network/"
web3 = Web3(Web3.HTTPProvider(RPC_URL))

ROUTER = Web3.to_checksum_address("0x6AAC14f090A35EeA150705f72D90E4CDC4a49b2C")

TOKENS = {
    "PING": "0x33E7fAB0a8a5da1A923180989bD617c9c2D1C493",
    "PONG": "0x9beaA0016c22B646Ac311Ab171270B0ECf23098F",
    "WSTT": "0x4A3BC48C156384f9564Fd65A53a2f3D534D8f2b7"
}

# ABI untuk WSTT (Wrapped STT)
WSTT_ABI = [
    {
        "constant": False,
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "payable": True,
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "wad", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

EXACT_INPUT_SINGLE_ABI = [{
    "name": "exactInputSingle",
    "type": "function",
    "stateMutability": "payable",
    "inputs": [{
        "components": [
            {"name": "tokenIn", "type": "address"},
            {"name": "tokenOut", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "recipient", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMinimum", "type": "uint256"},
            {"name": "sqrtPriceLimitX96", "type": "uint160"}
        ],
        "name": "params",
        "type": "tuple"
    }],
    "outputs": [{"name": "amountOut", "type": "uint256"}]
}]

# ERC20 ABI
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

def get_current_gas_price():
    return web3.eth.gas_price

def estimate_gas_cost(gas_limit=200000):
    return Web3.from_wei(get_current_gas_price() * gas_limit, 'ether')

def check_enough_gas(account, gas_limit=200000):
    balance = Web3.from_wei(web3.eth.get_balance(account.address), 'ether')
    return balance >= estimate_gas_cost(gas_limit)

def get_nonce(account_address):
    """Get nonce with retry mechanism for pending transactions"""
    try:
        # Get pending nonce first (includes pending transactions)
        pending_nonce = web3.eth.get_transaction_count(account_address, 'pending')
        latest_nonce = web3.eth.get_transaction_count(account_address, 'latest')
        
        # Use the higher nonce to avoid NONCE_TOO_SMALL
        nonce = max(pending_nonce, latest_nonce)
        return nonce
    except:
        # Fallback to latest nonce
        return web3.eth.get_transaction_count(account_address)

def get_token_balance(w3, token_address, wallet_address):
    abi = [{"constant": True,"inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf","outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function"}]
    contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=abi)
    balance = contract.functions.balanceOf(wallet_address).call()
    return round(balance / 1e18, 4)

def get_balances(account):
    stt = Web3.from_wei(web3.eth.get_balance(account.address), 'ether')
    ping = get_token_balance(web3, TOKENS["PING"], account.address)
    pong = get_token_balance(web3, TOKENS["PONG"], account.address)
    wstt = get_token_balance(web3, TOKENS["WSTT"], account.address)
    return round(stt, 4), ping, pong, wstt

def load_wallets():
    path = Path("private_keys.txt")
    if not path.exists():
        console.print("[red]❌ File private_keys.txt tidak ditemukan![/red]")
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def prompt_total_loops():
    return IntPrompt.ask("Berapa kali proses farming per wallet?", default=1)

def log_result(title, sender, target, tx_hash, status):
    with open("farming_log.txt", "a") as log:
        log.write(f"{time.ctime()} | {title} | {sender[-6:]} -> {target[-6:]} | {status} | {tx_hash}\n")

def approve_token_if_needed(private_key, token_address, spender_address, amount):
    """Check and approve token if needed"""
    try:
        account = Account.from_key(private_key)
        token_contract = web3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        
        # Check current allowance
        current_allowance = token_contract.functions.allowance(account.address, spender_address).call()
        
        if current_allowance >= amount:
            return True
        
        # Need to approve
        approve_tx = token_contract.functions.approve(spender_address, Web3.to_wei(1000000, 'ether')).build_transaction({
            'from': account.address,
            'nonce': get_nonce(account.address),
            'gas': 100000,
            'gasPrice': get_current_gas_price()
        })
        
        signed_approve = web3.eth.account.sign_transaction(approve_tx, private_key)
        approve_hash = web3.eth.send_raw_transaction(signed_approve.rawTransaction)
        web3.eth.wait_for_transaction_receipt(approve_hash)
        
        return True
        
    except Exception as e:
        console.print(f"[red]Gagal approve token: {e}[/red]")
        return False

def wrap_unwrap_stt(private_key):
    account = Account.from_key(private_key)

    if not check_enough_gas(account):
        console.print(f"[red]Saldo STT kurang untuk gas, skip wrap/unwrap wallet {account.address}[/red]")
        log_result("Wrap/Unwrap", account.address, TOKENS["WSTT"], "-", "Skipped: Low Gas")
        return

    wstt_contract = web3.eth.contract(address=Web3.to_checksum_address(TOKENS["WSTT"]), abi=WSTT_ABI)

    console.print("[cyan]Wrap STT ke WSTT...[/cyan]")
    try:
        # Build wrap transaction
        wrap_tx = wstt_contract.functions.deposit().build_transaction({
            'from': account.address,
            'value': Web3.to_wei(0.0001, 'ether'),
            'nonce': get_nonce(account.address),
            'gas': 200000,
            'gasPrice': get_current_gas_price()
        })
        
        signed1 = web3.eth.account.sign_transaction(wrap_tx, private_key)
        tx_hash1 = web3.eth.send_raw_transaction(signed1.rawTransaction)
        receipt1 = web3.eth.wait_for_transaction_receipt(tx_hash1)
        console.print(f"TX: {web3.to_hex(tx_hash1)}")
        console.print(f"Blok: {receipt1.blockNumber}")
        console.print("[green]Berhasil wrap STT[/green]")
        log_result("Wrap STT", account.address, TOKENS["WSTT"], web3.to_hex(tx_hash1), "Success")
        time.sleep(random.uniform(3, 5))
        print()

        console.print("[cyan]Unwrap WSTT ke STT...[/cyan]")
        amount = Web3.to_wei(0.0001, 'ether')
        
        # Build unwrap transaction
        unwrap_tx = wstt_contract.functions.withdraw(amount).build_transaction({
            'from': account.address,
            'nonce': get_nonce(account.address),
            'gas': 200000,
            'gasPrice': get_current_gas_price()
        })
        
        signed2 = web3.eth.account.sign_transaction(unwrap_tx, private_key)
        tx_hash2 = web3.eth.send_raw_transaction(signed2.rawTransaction)
        receipt2 = web3.eth.wait_for_transaction_receipt(tx_hash2)
        console.print(f"TX: {web3.to_hex(tx_hash2)}")
        console.print(f"Blok: {receipt2.blockNumber}")
        console.print("[green]Berhasil unwrap WSTT[/green]")
        log_result("Unwrap WSTT", account.address, TOKENS["WSTT"], web3.to_hex(tx_hash2), "Success")
        time.sleep(random.uniform(3, 5))
        print()

    except Exception as e:
        console.print(f"[red]Gagal wrap/unwrap: {e}[/red]")
        log_result("Wrap/Unwrap", account.address, TOKENS["WSTT"], "-", f"Error: {str(e)}")
        print()

def balance_tokens(private_key):
    account = Account.from_key(private_key)

    if not check_enough_gas(account):
        console.print(f"[red]Saldo STT kurang untuk gas, skip balance_tokens wallet {account.address}[/red]")
        log_result("Balance Tokens", account.address, "-", "-", "Skipped: Low Gas")
        return
        
    ping_balance = get_token_balance(web3, TOKENS["PING"], account.address)
    pong_balance = get_token_balance(web3, TOKENS["PONG"], account.address)

    while ping_balance < 100 or pong_balance < 100:
        if ping_balance < 100:
            swap_exact_input(private_key, "PONG", "PING", 500)
            ping_balance = get_token_balance(web3, TOKENS["PING"], account.address)
            console.print(f"[cyan]Saldo PING: {ping_balance:.4f}, PONG: {pong_balance:.4f} setelah swap.[/cyan]")

        elif pong_balance < 100:
            swap_exact_input(private_key, "PING", "PONG", 500)
            pong_balance = get_token_balance(web3, TOKENS["PONG"], account.address)
            console.print(f"[cyan]Saldo PING: {ping_balance:.4f}, PONG: {pong_balance:.4f} setelah swap.[/cyan]")
            print()

        time.sleep(random.uniform(1, 3))

def swap_exact_input(private_key, from_token, to_token, amount_in_token):
    account = Account.from_key(private_key)

    if not check_enough_gas(account):
        console.print(f"[red]Saldo STT kurang untuk gas, skip swap {from_token} -> {to_token} wallet {account.address}[/red]")
        log_result(f"Swap {from_token} -> {to_token}", account.address, ROUTER, "-", "Skipped: Low Gas")
        return

    router = web3.eth.contract(address=ROUTER, abi=EXACT_INPUT_SINGLE_ABI)
    amount_in = Web3.to_wei(amount_in_token, 'ether')
    
    # Approve token first
    if not approve_token_if_needed(private_key, TOKENS[from_token], ROUTER, amount_in):
        console.print(f"[red]Gagal approve {from_token}[/red]")
        return

    params = {
        'tokenIn': Web3.to_checksum_address(TOKENS[from_token]),
        'tokenOut': Web3.to_checksum_address(TOKENS[to_token]),
        'fee': 500,
        'recipient': account.address,
        'amountIn': amount_in,
        'amountOutMinimum': 0,
        'sqrtPriceLimitX96': 0
    }

    console.print(f"[cyan]Swap {from_token} ke {to_token} sebanyak {amount_in_token:.4f}...[/cyan]")

    try:
        tx = router.functions.exactInputSingle(params).build_transaction({
            'from': account.address,
            'nonce': get_nonce(account.address),
            'gas': 200000,
            'gasPrice': get_current_gas_price()
        })

        signed = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        tx_hex = web3.to_hex(tx_hash)
        console.print(f"TX: {tx_hex}")
        console.print(f"Blok: {receipt.blockNumber}")
        console.print("[green]Swap berhasil[/green]")
        log_result(f"Swap {from_token} -> {to_token}", account.address, ROUTER, tx_hex, "Success")
        time.sleep(random.uniform(3, 5))
        print()
    except Exception as e:
        console.print("[red]Gagal swap:[/red]", str(e))
        log_result(f"Swap {from_token} -> {to_token}", account.address, ROUTER, "-", "Failed")
        print()

def swap_ping_pong_cycle(private_key):
    account = Account.from_key(private_key)

    if not check_enough_gas(account):
        console.print(f"[red]Saldo STT kurang untuk gas, skip swap cycle wallet {account.address}[/red]")
        log_result("Swap Ping Pong Cycle", account.address, ROUTER, "-", "Skipped: Low Gas")
        return

    for _ in range(random.randint(3, 5)):
        amount = random.uniform(5, 7)
        swap_exact_input(private_key, "PING", "PONG", amount)
        time.sleep(random.uniform(1, 3))

    for _ in range(random.randint(3, 5)):
        amount = random.uniform(5, 7)
        swap_exact_input(private_key, "PONG", "PING", amount)
        time.sleep(random.uniform(1, 3))

def run_wallet_process(wallet_index, private_key, total_loops):
    account = Account.from_key(private_key)

    if not check_enough_gas(account):
        console.print(f"[red]Wallet {wallet_index} tidak cukup saldo STT, hentikan proses.[/red]")
        return
    stt, ping, pong, wstt = get_balances(account)
    print()
    console.print(f"[cyan]Mulai Wallet {wallet_index}: {account.address}[/cyan]")
    print()
    console.print(f"[cyan]Saldo Awal Wallet {wallet_index}:[/cyan]")
    console.print(f"  STT  : {stt:.4f} ETH")
    console.print(f"  PING : {ping:.4f} PING")
    console.print(f"  PONG : {pong:.4f} PONG")
    console.print(f"  WSTT : {wstt:.4f} WSTT")
    print()
    for proc in range(1, total_loops + 1):
        console.print(f"[cyan]Proses {proc} dari {total_loops}...[/cyan]")
        print()
        try:
            wrap_unwrap_stt(private_key)
            balance_tokens(private_key)
            swap_ping_pong_cycle(private_key)
        except Exception as e:
            console.print(f"[red]Error wallet {wallet_index}: {e}[/red]")
            print()

    stt, ping, pong, wstt = get_balances(account)
    console.print(f"[cyan]Saldo Akhir Wallet {wallet_index}:[/cyan]")
    console.print(f"  STT  : {stt:.4f} ETH")
    console.print(f"  PING : {ping:.4f} PING")
    console.print(f"  PONG : {pong:.4f} PONG")
    console.print(f"  WSTT : {wstt:.4f} WSTT")
    print()

    console.print(f"[green]Selesai Proses {proc} untuk Wallet {wallet_index}[/green]")
    time.sleep(random.randint(3, 5))
    print()

def main():
    wallets = load_wallets()
    if not wallets:
        return

    total_loops = prompt_total_loops()
    accounts = [(idx + 1, pk) for idx, pk in enumerate(wallets)]

    for loop in range(1, total_loops + 1):
        console.print(f"[bold yellow]=== Mulai Proses Loop {loop} dari {total_loops} untuk semua wallet ===[/bold yellow]\n")

        processed_any = False

        for wallet_index, private_key in accounts:
            account = Account.from_key(private_key)
            w3 = Web3(Web3.HTTPProvider(RPC_URL))
            start_native_balance = w3.eth.get_balance(account.address) / 1e18

            gas_price = w3.eth.gas_price
            gas_limit = 200000
            min_stt_needed = (gas_price * gas_limit) / 1e18

            if start_native_balance < min_stt_needed:
                console.print(f"[red]Lewati Wallet {wallet_index} (saldo STT {start_native_balance:.6f} < estimasi gas {min_stt_needed:.6f})[/red]")
                continue

            processed_any = True
            run_wallet_process(wallet_index, private_key, 1)

            tx_count = w3.eth.get_transaction_count(account.address)
            console.print(f"[green]Total TX on-chain: {tx_count}")

        if not processed_any:
            console.print("[bold red]Semua wallet tidak memiliki saldo gas cukup, proses dihentikan.[/bold red]")
            break

if __name__ == "__main__":
    main()