import time
from web3 import Web3
from eth_account import Account
from termcolor import colored

# Konfigurasi jaringan
RPC_URL = "https://rpc-testnet.haust.app"
CHAIN_ID = 1523903251

WRAP_CONTRACT_ADDRESS = Web3.to_checksum_address("0x6c25c1cb4b8677982791328471be1bfb187687c1")
WRAP_ABI = [
    {
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    }
]

AMOUNT_TO_WRAP = int(0.001 * 10**18)
PVKEY_FILE = "pvkey.txt"

w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    print(colored("Gagal terhubung ke RPC testnet Haust. Pastikan RPC URL benar.", "red"))
    exit(1)

def safe_call(func, *args, **kwargs):
    """Memanggil fungsi RPC dengan penanganan error."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(colored(f"Error RPC call: {e}", "red"))
        return None

def load_private_keys(filename):
    keys = []
    try:
        with open(filename, "r") as f:
            for line in f:
                key = line.strip()
                if key:
                    keys.append(key)
        if not keys:
            print(colored("File private key kosong.", "red"))
            exit(1)
        return keys
    except FileNotFoundError:
        print(colored(f"File {filename} tidak ditemukan.", "red"))
        exit(1)

def create_account(pk):
    try:
        return Account.from_key(pk)
    except Exception as e:
        print(colored(f"Error membuat akun dari private key: {e}", "red"))
        return None

def send_wrap_tx(account, contract, amount):
    nonce = safe_call(w3.eth.get_transaction_count, account.address)
    if nonce is None:
        raise Exception("Gagal mendapatkan nonce")

    try:
        gas_estimate = contract.functions.deposit().estimate_gas({
            'from': account.address,
            'value': amount
        })
        gas_limit = int(gas_estimate * 1.2)
    except Exception as e:
        print(colored(f"Error estimasi gas: {e}", "yellow"))
        gas_limit = 30000  # fallback gas limit

    tx = contract.functions.deposit().build_transaction({
        'chainId': CHAIN_ID,
        'gas': gas_limit,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
        'value': amount,
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    return tx_hash.hex()

def wait_for_receipt(tx_hash, timeout=120):
    try:
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        return receipt
    except Exception as e:
        print(colored(f"Timeout atau error saat menunggu receipt: {e}", "red"))
        return None

def main():
    print(colored("=== Skrip Wrap HAUST ke wHAUST Multi Wallet ===", attrs=['bold']))

    private_keys = load_private_keys(PVKEY_FILE)
    accounts = [create_account(pk) for pk in private_keys]
    accounts = [acc for acc in accounts if acc is not None]

    contract = w3.eth.contract(address=WRAP_CONTRACT_ADDRESS, abi=WRAP_ABI)

    try:
        total_process = int(input("Berapa kali proses ingin dijalankan? "))
        if total_process <= 0:
            print(colored("Jumlah proses harus positif.", "red"))
            return
    except ValueError:
        print(colored("Input tidak valid.", "red"))
        return

    for process_num in range(1, total_process + 1):
        print(colored(f"\n=== Proses ke-{process_num} ===", attrs=['bold']))

        for idx, account in enumerate(accounts, start=1):
            print(colored(f"\n[{idx}/{len(accounts)}] Wallet: {account.address}\n", attrs=['bold']))

            balance_awal = safe_call(w3.eth.get_balance, account.address)
            if balance_awal is None:
                print(colored("Gagal mendapatkan saldo wallet.\n", "red"))
                continue

            print("[Saldo Awal]")
            print(f"Native: {w3.from_wei(balance_awal, 'ether')} HAUST\n")

            estimated_gas_cost = 30000 * w3.eth.gas_price
            required_balance = AMOUNT_TO_WRAP + estimated_gas_cost

            if balance_awal < required_balance:
                print(colored(f"Saldo HAUST tidak cukup untuk wrap + gas fee. Dibutuhkan minimal {w3.from_wei(required_balance, 'ether')} HAUST\n", "red"))
                continue

            print(colored(f"Wrap HAUST ke wHAUST: {w3.from_wei(AMOUNT_TO_WRAP, 'ether')} HAUST", "cyan"))

            try:
                tx_hash = send_wrap_tx(account, contract, AMOUNT_TO_WRAP)
                print(f"Tx    : {tx_hash}")

                receipt = wait_for_receipt(tx_hash)
                if receipt and receipt.status == 1:
                    print(f"Blok  : {receipt.blockNumber}")
                    print(f"Status: {colored('✅ Wrap berhasil', 'green')}\n")
                else:
                    print(colored("Status: ❌ Wrap gagal\n", "red"))

            except Exception as e:
                print(colored(f"Error saat mengirim transaksi: {e}", "red"))
                print(colored("Status: ❌ Wrap gagal\n", "red"))

            balance_akhir = safe_call(w3.eth.get_balance, account.address)
            if balance_akhir is None:
                print(colored("Gagal mendapatkan saldo akhir wallet.\n", "red"))
                continue

            print("[Saldo Akhir]")
            print(f"Native: {w3.from_wei(balance_akhir, 'ether')} HAUST\n")

            # Ambil total transaksi on-chain (nonce)
            tx_count = safe_call(w3.eth.get_transaction_count, account.address)
            if tx_count is not None:
                print(f"Total TX on-chain: {tx_count}\n")
            else:
                print(colored("Gagal mendapatkan total transaksi on-chain.\n", "red"))

            print("-" * 56)

            time.sleep(5)  # delay 3 detik agar tidak spam RPC

        print(colored(f"=== Proses ke-{process_num} selesai ===\n", attrs=['bold']))

    print(colored("Semua proses selesai.\n", attrs=['bold']))

if __name__ == "__main__":
    main()
