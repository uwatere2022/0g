from web3 import Web3
import json
import time
from eth_account import Account

rpc_url = "https://evmrpc-testnet.0g.ai"
w3 = Web3(Web3.HTTPProvider(rpc_url))
chain_id = 16601

def safe_call(func, *args, retries=3, delay=3, **kwargs):
    retries = int(retries)
    attempt = 0
    while attempt < retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"RPC Error: {e}. Retry {attempt+1}/{retries}...")
            attempt += 1
            time.sleep(delay)
    raise Exception(f"Function {func.__name__} failed after {retries} retries.")

router_address = Web3.to_checksum_address("0xb95B5953FF8ee5D5d9818CdbEfE363ff2191318c")
usdt_address = Web3.to_checksum_address("0x3ec8a8705be1d5ca90066b37ba62c4183b024ebf")
btc_address = Web3.to_checksum_address("0x36f6414ff1df609214ddaba71c84f18bcf00f67d")
eth_address = Web3.to_checksum_address("0x0fE9B43625fA7EdD663aDcEC0728DD635e4AbF7c")

with open("abi.json") as f:
    abi_data = json.load(f)

swap_contract = w3.eth.contract(address=router_address, abi=abi_data)

erc20_abi = [
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
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
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function"
    }
]

usdt_contract = w3.eth.contract(address=usdt_address, abi=erc20_abi)
btc_contract = w3.eth.contract(address=btc_address, abi=erc20_abi)
eth_contract = w3.eth.contract(address=eth_address, abi=erc20_abi)

amount_in = w3.to_wei(10, 'ether')
min_amount_out = 1
fee = 3000
sqrt_price_limit = 0

with open("pvkey.txt") as f:
    private_keys = [line.strip() for line in f if line.strip()]

loop_count = int(input("Berapa kali proses ingin dijalankan? "))
print(f"\nMemulai proses sebanyak {loop_count} kali...\n")

# ===================== Tambahan Fungsi Modular =====================
def ensure_allowance(contract, wallet, pk, router_address, amount_in, nonce, gas_price):
    allowance = safe_call(contract.functions.allowance(wallet, router_address).call)
    if allowance < amount_in:
        print("\033[96mApprove diperlukan\033[0m")
        approve_tx = contract.functions.approve(router_address, 2**256 - 1).build_transaction({
            'from': wallet,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': gas_price,
            'chainId': chain_id
        })
        signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key=pk)
        approve_tx_hash = safe_call(w3.eth.send_raw_transaction, signed_approve.rawTransaction)
        receipt = safe_call(w3.eth.wait_for_transaction_receipt, approve_tx_hash)
        print(f"Tx : {approve_tx_hash.hex()}")
        print(f"Blok : {receipt.blockNumber}")
        if receipt.status == 1:
            print("\033[92mApprove berhasil\033[0m")
        else:
            print("\033[91mApprove gagal\033[0m")
        return nonce + 1
    return nonce

def do_swap(wallet, pk, token_in, token_out, amount_in, min_amount_out, nonce, gas_price, fee=3000, desc=""):
    try:
        swap_tx = swap_contract.functions.exactInputSingle({
            'tokenIn': token_in,
            'tokenOut': token_out,
            'fee': fee,
            'recipient': wallet,
            'deadline': int(time.time()) + 1200,
            'amountIn': amount_in,
            'amountOutMinimum': min_amount_out,
            'sqrtPriceLimitX96': 0
        }).build_transaction({
            'from': wallet,
            'nonce': nonce,
            'gas': 500000,
            'gasPrice': gas_price,
            'chainId': chain_id
        })
        signed = w3.eth.account.sign_transaction(swap_tx, private_key=pk)
        tx_hash = safe_call(w3.eth.send_raw_transaction, signed.rawTransaction)
        receipt = safe_call(w3.eth.wait_for_transaction_receipt, tx_hash)
        print(f"\033[96mSwap {desc}\033[0m")
        print(f"Tx : {tx_hash.hex()}")
        print(f"Blok : {receipt.blockNumber}")
        if receipt.status == 1:
            print("\033[92mSwap berhasil ✔️\033[0m")
        else:
            print("\033[91mSwap gagal ❌\033[0m")
        print()
        return receipt.status == 1
    except Exception as e:
        if "insufficient funds" in str(e):
            print(f"Insufficient gas swap {desc}, skip wallet")
        else:
            print(f"Error swap {desc}: {e}")
        return False
# ===================== END Tambahan Fungsi Modular =====================

for process_round in range(loop_count):
    print(f"\n=== Proses Ke-{process_round + 1} ===\n")
    failed_wallets = 0
    for i, pk in enumerate(private_keys):
        try:
            acct = Account.from_key(pk)
            wallet = acct.address
            print(f"\nWallet {i+1}: {wallet}\n")

            native_balance = safe_call(w3.eth.get_balance, wallet)
            usdt_balance = safe_call(usdt_contract.functions.balanceOf(wallet).call)
            btc_balance = safe_call(btc_contract.functions.balanceOf(wallet).call)
            eth_balance = safe_call(eth_contract.functions.balanceOf(wallet).call)

            print("[Saldo Awal]")
            print(f"Native: {round(w3.from_wei(native_balance, 'ether'), 7)} OG")
            print(f"USDT : {round(w3.from_wei(usdt_balance, 'ether'))}")
            print(f"BTC : {round(w3.from_wei(btc_balance, 'ether'), 6)}")
            print(f"ETH : {round(w3.from_wei(eth_balance, 'ether'), 6)}\n")

            if usdt_balance < amount_in:
                print("Saldo USDT tidak cukup")
                failed_wallets += 1
                continue

            nonce = safe_call(w3.eth.get_transaction_count, wallet)
            gas_price = int(w3.eth.gas_price * 1.1)

            # CEK ALLOWANCE USDT
            allowance = safe_call(usdt_contract.functions.allowance(wallet, router_address).call)
            if allowance < amount_in:
                print("\033[96mApprove USDT\033[0m")
                max_uint256 = 2**256 - 1
                approve_tx = usdt_contract.functions.approve(router_address, max_uint256).build_transaction({
                    'from': wallet,
                    'nonce': nonce,
                    'gas': 100000,
                    'gasPrice': gas_price,
                    'chainId': chain_id
                })
                signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key=pk)
                try:
                    approve_tx_hash = safe_call(w3.eth.send_raw_transaction, signed_approve.rawTransaction)
                    receipt = safe_call(w3.eth.wait_for_transaction_receipt, approve_tx_hash)
                    print(f"Tx : {approve_tx_hash.hex()}")
                    print(f"Blok : {receipt.blockNumber}")
                    print("\033[92mApprove berhasil\033[0m")
                except Exception as e:
                    if "insufficient funds" in str(e):
                        print("Insufficient gas untuk approve, skip wallet")
                        failed_wallets += 1
                        continue
                    else:
                        raise e
                nonce += 1

            # SWAP USDT → BTC
            swap_tx1 = swap_contract.functions.exactInputSingle({
                'tokenIn': usdt_address,
                'tokenOut': btc_address,
                'fee': fee,
                'recipient': wallet,
                'deadline': int(time.time()) + 1200,
                'amountIn': amount_in,
                'amountOutMinimum': min_amount_out,
                'sqrtPriceLimitX96': sqrt_price_limit
            }).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': chain_id
            })
            signed1 = w3.eth.account.sign_transaction(swap_tx1, private_key=pk)
            try:
                tx_hash1 = safe_call(w3.eth.send_raw_transaction, signed1.rawTransaction)
                receipt = safe_call(w3.eth.wait_for_transaction_receipt, tx_hash1)
                print("\033[96mSwap USDT → BTC\033[0m")
                print(f"Tx : {tx_hash1.hex()}")
                print(f"Blok : {receipt.blockNumber}")
                if receipt.status == 1:
                    print("\033[92mSwap berhasil ✔️\033[0m")
                else:
                    print("\033[91mSwap gagal ❌\033[0m")
                print()
            except Exception as e:
                if "insufficient funds" in str(e):
                    print("Insufficient gas swap BTC, skip wallet")
                    failed_wallets += 1
                    continue
                else:
                    raise e
            time.sleep(3)
            nonce += 1

            # CEK ALLOWANCE USDT (lagi)
            allowance = safe_call(usdt_contract.functions.allowance(wallet, router_address).call)
            if allowance < amount_in:
                print("\033[96mApprove USDT\033[0m")
                max_uint256 = 2**256 - 1
                approve_tx = usdt_contract.functions.approve(router_address, max_uint256).build_transaction({
                    'from': wallet,
                    'nonce': nonce,
                    'gas': 100000,
                    'gasPrice': gas_price,
                    'chainId': chain_id
                })
                signed_approve = w3.eth.account.sign_transaction(approve_tx, private_key=pk)
                try:
                    approve_tx_hash = safe_call(w3.eth.send_raw_transaction, signed_approve.rawTransaction)
                    receipt = safe_call(w3.eth.wait_for_transaction_receipt, approve_tx_hash)
                    print(f"Tx : {approve_tx_hash.hex()}")
                    print(f"Blok : {receipt.blockNumber}")
                    print("\033[92mApprove berhasil\033[0m")
                except Exception as e:
                    if "insufficient funds" in str(e):
                        print("Insufficient gas untuk approve, skip wallet")
                        failed_wallets += 1
                        continue
                    else:
                        raise e
                nonce += 1

            # SWAP USDT → ETH
            swap_tx2 = swap_contract.functions.exactInputSingle({
                'tokenIn': usdt_address,
                'tokenOut': eth_address,
                'fee': fee,
                'recipient': wallet,
                'deadline': int(time.time()) + 1200,
                'amountIn': amount_in,
                'amountOutMinimum': min_amount_out,
                'sqrtPriceLimitX96': sqrt_price_limit
            }).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gas': 500000,
                'gasPrice': gas_price,
                'chainId': chain_id
            })
            signed2 = w3.eth.account.sign_transaction(swap_tx2, private_key=pk)
            try:
                tx_hash2 = safe_call(w3.eth.send_raw_transaction, signed2.rawTransaction)
                receipt = safe_call(w3.eth.wait_for_transaction_receipt, tx_hash2)
                print("\033[96mSwap USDT → ETH\033[0m")
                print(f"Tx : {tx_hash2.hex()}")
                print(f"Blok : {receipt.blockNumber}")
                if receipt.status == 1:
                    print("\033[92mSwap berhasil ✔️\033[0m")
                else:
                    print("\033[91mSwap gagal ❌\033[0m")
                print()
            except Exception as e:
                if "insufficient funds" in str(e):
                    print("Insufficient gas swap ETH, skip wallet")
                    failed_wallets += 1
                    continue
                else:
                    raise e
            time.sleep(3)
            nonce += 1

            # ============ SWAP TAMBAHAN ============

            btc_amount_in = w3.to_wei(0.0001, 'ether')
            eth_amount_in = w3.to_wei(0.01, 'ether')
            min_amount_out_swap = 1

            # BTC → USDT
            nonce = ensure_allowance(btc_contract, wallet, pk, router_address, btc_amount_in, nonce, gas_price)
            do_swap(wallet, pk, btc_address, usdt_address, btc_amount_in, min_amount_out_swap, nonce, gas_price, desc="BTC → USDT")
            nonce += 1
            time.sleep(3)

            # BTC → ETH
            nonce = ensure_allowance(btc_contract, wallet, pk, router_address, btc_amount_in, nonce, gas_price)
            do_swap(wallet, pk, btc_address, eth_address, btc_amount_in, min_amount_out_swap, nonce, gas_price, desc="BTC → ETH")
            nonce += 1
            time.sleep(3)

            # ETH → USDT
            nonce = ensure_allowance(eth_contract, wallet, pk, router_address, eth_amount_in, nonce, gas_price)
            do_swap(wallet, pk, eth_address, usdt_address, eth_amount_in, min_amount_out_swap, nonce, gas_price, desc="ETH → USDT")
            nonce += 1
            time.sleep(3)

            # ETH → BTC
            nonce = ensure_allowance(eth_contract, wallet, pk, router_address, eth_amount_in, nonce, gas_price)
            do_swap(wallet, pk, eth_address, btc_address, eth_amount_in, min_amount_out_swap, nonce, gas_price, desc="ETH → BTC")
            nonce += 1
            time.sleep(3)

            # ============ END SWAP TAMBAHAN ============

            native_balance_end = safe_call(w3.eth.get_balance, wallet)
            usdt_end = safe_call(usdt_contract.functions.balanceOf(wallet).call)
            btc_end = safe_call(btc_contract.functions.balanceOf(wallet).call)
            eth_end = safe_call(eth_contract.functions.balanceOf(wallet).call)

            print("[Saldo Akhir]")
            print(f"Native: {round(w3.from_wei(native_balance_end, 'ether'), 7)} OG")
            print(f"USDT : {round(w3.from_wei(usdt_end, 'ether'))}")
            print(f"BTC : {round(w3.from_wei(btc_end, 'ether'), 6)}")
            print(f"ETH : {round(w3.from_wei(eth_end, 'ether'), 6)}")

        except Exception as e:
            print(f"Error wallet {wallet}: {e}")
            failed_wallets += 1

        tx_count = safe_call(w3.eth.get_transaction_count, wallet)
        print(f"\nTotal TX on-chain: {tx_count}\n")
        print("-" * 52)
        time.sleep(5)

    if failed_wallets == len(private_keys):
        print("\nSemua wallet insufficient gas atau saldo swap. Proses dihentikan.")
        break
