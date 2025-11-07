from web3 import Web3
import json
import time
from colorama import Fore, Style, init
from eth_account import Account
from decimal import Decimal

init(autoreset=True)

# Load private keys
with open("pvkey.txt", "r") as f:
    private_keys = [line.strip() for line in f if line.strip()]

# Web3 connection
rpc = "https://testnet-rpc.xoscan.io"
w3 = Web3(Web3.HTTPProvider(rpc))
if not w3.is_connected():
    print(Fore.RED + "Gagal koneksi ke RPC" + Style.RESET_ALL)
    exit()

# Load ABI WXOS
with open("WXOS_ABI.json", "r") as f:
    wxos_abi = json.load(f)

# Inisialisasi kontrak WXOS
WXOS = w3.to_checksum_address("0x0AAB67cf6F2e99847b9A95DeC950B250D648c1BB")
wxos_contract = w3.eth.contract(address=WXOS, abi=wxos_abi)

wrap_amount = w3.to_wei("0.0001", "ether")
chain_id = w3.eth.chain_id
print(Fore.YELLOW + f"Chain ID: {chain_id}" + Style.RESET_ALL)

# Prompt
n = int(input("Berapa kali wrap & unwrap XOS ke WXOS? "))

def extract_error_message(e):
    error_msg = ""
    if hasattr(e, 'args') and e.args:
        first_arg = e.args[0]
        if isinstance(first_arg, dict) and 'message' in first_arg:
            error_msg = first_arg['message'].lower()
        else:
            error_msg = str(e).lower()
    else:
        error_msg = str(e).lower()
    return error_msg

# Jalankan proses wrapping dan unwrapping sebanyak n kali
for i in range(n):
    print(f"\n{Fore.MAGENTA}=== Proses {i+1} dari {n} ==={Style.RESET_ALL}")
    any_processed = False  # Flag untuk cek ada wallet berhasil proses

    for idx, pk in enumerate(private_keys, start=1):
        private_key = pk
        account = Account.from_key(private_key)
        address = account.address

        # Tampilkan saldo awal
        balance_now = w3.eth.get_balance(address)
        print(f"\n{Fore.CYAN}--- Wallet {idx} ---{Style.RESET_ALL}")
        print(f"Saldo XOS saat ini: {w3.from_wei(balance_now, 'ether')}\n")

        # Wrap
        print(Fore.CYAN + f"Wrap XOS ke WXOS..." + Style.RESET_ALL)
        try:
            nonce = w3.eth.get_transaction_count(address, 'pending')
            tx = wxos_contract.functions.deposit().build_transaction({
                'from': address,
                'value': wrap_amount,
                'gas': 100_000,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 1267
            })

            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"tx : {w3.to_hex(tx_hash)}")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"blok : {receipt.blockNumber}")
            print(Fore.GREEN + "✓ Wrap berhasil" + Style.RESET_ALL)
            any_processed = True  # Tandai wallet berhasil proses
        except Exception as e:
            error_msg = extract_error_message(e)
            if "insufficient funds" in error_msg or "insufficient balance" in error_msg:
                print(Fore.YELLOW + "Saldo kurang, skip wallet" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"Gagal wrap: {str(e)}" + Style.RESET_ALL)
            continue

        time.sleep(3)

        # Unwrap
        print(Fore.CYAN + f"Unwrap WXOS ke XOS..." + Style.RESET_ALL)
        try:
            nonce = w3.eth.get_transaction_count(address, 'pending')
            tx = wxos_contract.functions.withdraw(wrap_amount).build_transaction({
                'from': address,
                'gas': 100_000,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
                'chainId': 1267
            })

            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"tx : {w3.to_hex(tx_hash)}")
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"blok : {receipt.blockNumber}")
            print(Fore.GREEN + "✓ Unwrap berhasil" + Style.RESET_ALL)
        except Exception as e:
            error_msg = extract_error_message(e)
            if "insufficient funds" in error_msg or "insufficient balance" in error_msg:
                print(Fore.YELLOW + "Saldo kurang, skip wallet" + Style.RESET_ALL)
            else:
                print(Fore.RED + f"Gagal unwrap: {str(e)}" + Style.RESET_ALL)
            continue

        time.sleep(3)

        balance_after = w3.eth.get_balance(address)
        print(f"Saldo akhir XOS: {w3.from_wei(balance_after, 'ether')}")
        print()
        tx_count = w3.eth.get_transaction_count(address)
        print(f"  Total TX on-chain: {tx_count}")
        print()

    if not any_processed:
        print(Fore.RED + "Semua wallet saldo kurang, proses dihentikan." + Style.RESET_ALL)
        exit()
