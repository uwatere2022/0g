from web3 import Web3
import json
import time

# === Konfigurasi ===
PHAROS_RPC = "https://testnet.dplabs-internal.com"
CHAIN_ID = 688688
CONTRACT_ADDRESS = "0x76aaada469d23216be5f7c596fa25f282ff9b364"

# ABI minimal: deposit() dan Deposit event
WPHRS_ABI = json.loads("""
[
    {
        "constant": false,
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "payable": true,
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "nftId", "type": "uint256"},
            {"indexed": false, "name": "sender", "type": "address"}
        ],
        "name": "Deposit",
        "type": "event"
    }
]
""")

# ANSI color codes
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

web3 = Web3(Web3.HTTPProvider(PHAROS_RPC))
contract = web3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=WPHRS_ABI)

def wrap_from_account(private_key, amount_eth, process_index, wallet_index):
    acct = web3.eth.account.from_key(private_key)
    saldo = web3.eth.get_balance(acct.address)
    gas_limit = 100000
    gas_price = web3.to_wei('1', 'gwei')
    biaya_gas = gas_limit * gas_price
    total_cost = web3.to_wei(amount_eth, 'ether') + biaya_gas

    if saldo < total_cost:
        print(f"[PROSES {process_index+1}] [Wallet {wallet_index+1}] {acct.address} → SALDO TIDAK CUKUP! (Saldo: {web3.from_wei(saldo, 'ether'):.6f} PHRS, Butuh: {web3.from_wei(total_cost, 'ether'):.6f} PHRS)")
        return

    nonce = web3.eth.get_transaction_count(acct.address)
    saldo_awal = web3.from_wei(web3.eth.get_balance(acct.address), 'ether')
    print(f"[PROSES {process_index+1}] [Wallet {wallet_index+1}] {acct.address}")
    print(f"Saldo awal: {saldo_awal} PHRS")
    print()
    tx = contract.functions.deposit().build_transaction({
        'from': acct.address,
        'value': web3.to_wei(amount_eth, 'ether'),
        'gas': 100000,
        'gasPrice': web3.to_wei('1', 'gwei'),
        'nonce': nonce,
        'chainId': CHAIN_ID
    })

    signed = web3.eth.account.sign_transaction(tx, private_key)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)

    # OUTPUT WARNA SESUAI PERMINTAAN
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 1:
        status = f"{GREEN}Deposit berhasil ✔️{RESET}"
    else:
        status = f"{RED}Deposit gagal ❌{RESET}"
    print(f"{CYAN}Deposit PHRS → wPHRS{RESET}")
    print(f"Tx : {web3.to_hex(tx_hash)}")
    print(f"Blok : {receipt.blockNumber}")
    print(status)
    print()
    # END OUTPUT CUSTOM

    saldo_akhir = web3.from_wei(web3.eth.get_balance(acct.address), 'ether')
    print(f"Saldo akhir: {saldo_akhir} PHRS\n")

def run_multi_wallet_loop():
    with open("pvkey.txt", "r") as file:
        keys = [line.strip() for line in file if line.strip()]

    jumlah_proses = int(input("Berapa jumlah proses (putaran semua wallet)? "))
    delay_wallet = 3
    delay_proses = 5

    print(f"Memulai {jumlah_proses} proses... Total eksekusi: {jumlah_proses * len(keys)} transaksi\n")

    for p in range(jumlah_proses):
        print(f"=== PROSES KE-{p+1} ===")
        aktif_wallet = 0 # hitung wallet yang masih cukup saldo

        for i, pk in enumerate(keys):
            acct = web3.eth.account.from_key(pk)
            saldo = web3.eth.get_balance(acct.address)
            total_cost = web3.to_wei(0.001, 'ether') + (100000 * web3.to_wei('1', 'gwei'))

            if saldo < total_cost:
                print(f"[Wallet {i+1}] {acct.address} → SALDO TIDAK CUKUP (Saldo: {web3.from_wei(saldo, 'ether'):.6f} PHRS)")
                continue

            aktif_wallet += 1
            try:
                wrap_from_account(pk, amount_eth=0.001, process_index=p, wallet_index=i)
                time.sleep(delay_wallet)
            except Exception as e:
                print(f"[ERROR Wallet {i+1}] {pk[:10]}...: {e}")

            tx_count = web3.eth.get_transaction_count(acct.address)
            print(f"Total TX on-chain: {tx_count}")
            print()

        if aktif_wallet == 0:
            print(f"\n>>> Semua wallet saldo tidak cukup. Proses dihentikan di PROSES KE-{p+1}\n")
            break

        print(f"=== SELESAI PROSES KE-{p+1} ===\n")
        time.sleep(delay_proses)

if __name__ == "__main__":
    run_multi_wallet_loop()
