from web3 import Web3
from eth_account import Account
import time

# --- Warna ANSI ---
YELLOW = '\033[93m'
CYAN = '\033[96m'
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def warna(text, color):
    return f"{color}{text}{RESET}"

def garis():
    print(warna('-' * 60, YELLOW))

# --- CONFIGURATION ---
RPC_URL = "https://testnet.riselabs.xyz"
USDT_ADDRESS = Web3.to_checksum_address("0x40918Ba7f132E0aCba2CE4de4c4baF9BD2D7D849")
PEPE_ADDRESS = Web3.to_checksum_address("0x6F6f570F45833E249e27022648a26F4076F48f78")
MOG_ADDRESS  = Web3.to_checksum_address("0x99dBE4AEa58E518C50a1c04aE9b48C9F6354612f")
WBTC_ADDRESS = Web3.to_checksum_address("0xF32D39ff9f6Aa7a7A64d7a4f00a54826Ef791a55")
USDC_ADDRESS = Web3.to_checksum_address("0x8A93d247134d91e0de6f96547cB0204e5BE8e5D8")
MIXSWAP_ADDRESS = Web3.to_checksum_address("0x5eC9BEaCe4a0f46F77945D54511e2b454cb8F38E")

# --- ABI (SINGKAT, LENGKAPI SESUAI FILE ANDA) ---
EXTENDED_ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]
MIXSWAP_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "arg0", "type": "address"},
            {"internalType": "address", "name": "arg1", "type": "address"},
            {"internalType": "uint256", "name": "arg2", "type": "uint256"},
            {"internalType": "uint256", "name": "arg3", "type": "uint256"},
            {"internalType": "uint256", "name": "arg4", "type": "uint256"},
            {"internalType": "address[]", "name": "arg5", "type": "address[]"},
            {"internalType": "address[]", "name": "arg6", "type": "address[]"},
            {"internalType": "address[]", "name": "arg7", "type": "address[]"},
            {"internalType": "uint256", "name": "arg8", "type": "uint256"},
            {"internalType": "bytes[]", "name": "arg9", "type": "bytes[]"},
            {"internalType": "bytes", "name": "arg10", "type": "bytes"},
            {"internalType": "uint256", "name": "arg11", "type": "uint256"}
        ],
        "name": "mixSwap",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

def read_private_keys(filename):
    try:
        with open(filename, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"File {filename} tidak ditemukan!")
        return []

def get_token_info(w3, token_address):
    contract = w3.eth.contract(address=token_address, abi=EXTENDED_ERC20_ABI)
    decimals = contract.functions.decimals().call()
    symbol = contract.functions.symbol().call()
    return decimals, symbol

def get_balance(w3, contract, address, decimals):
    raw = contract.functions.balanceOf(address).call()
    return raw / (10 ** decimals), raw

def get_native_balance(w3, address):
    return float(w3.from_wei(w3.eth.get_balance(address), 'ether'))

def check_allowance(w3, token_contract, owner, spender):
    return token_contract.functions.allowance(owner, spender).call()

def approve_token(w3, account, private_key, token_contract, spender, amount):
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    max_fee = max(gas_price * 2, Web3.to_wei(0.0001, 'gwei'))
    priority_fee = Web3.to_wei(0.0001, 'gwei')
    tx = token_contract.functions.approve(
        spender,
        amount
    ).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': int(max_fee),
        'maxPriorityFeePerGas': int(priority_fee),
        'gas': 100000,
        'chainId': w3.eth.chain_id
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

# === FUNGSI SWAP (amount_out_min dan amount_out_min_97 di-set ke 1) ===

def do_swap_usdt_to_pepe(w3, account, private_key, mixswap_contract, usdt_contract, swap_amount_usdt, usdt_decimals):
    amount_in = int(swap_amount_usdt * (10 ** usdt_decimals))
    amount_out_min = 1
    amount_out_min_97 = 1
    allowance = check_allowance(w3, usdt_contract, account.address, MIXSWAP_ADDRESS)
    if allowance < amount_in:
        approve_hash, _ = approve_token(w3, account, private_key, usdt_contract, MIXSWAP_ADDRESS, amount_in)
        time.sleep(5)
    params = [
        USDT_ADDRESS,
        PEPE_ADDRESS,
        amount_in,
        amount_out_min,
        amount_out_min_97,
        [Web3.to_checksum_address("0x7Bd75781c1837f8C41A6A41CA9C4E66d3a726B5c")],
        [Web3.to_checksum_address("0x79e57089994Fc8cB1ca65162416F995A0bEB84ae")],
        [Web3.to_checksum_address("0x79e57089994Fc8cB1ca65162416F995A0bEB84ae"), MIXSWAP_ADDRESS],
        0,
        [bytes.fromhex("000000000000000000000000000000000000000000000000000000000000001e0000000000000000000000000000000000000000000000000000000000002710")],
        bytes.fromhex("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        int(time.time()) + 600
    ]
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    max_fee = max(gas_price * 2, w3.to_wei(0.0001, 'gwei'))
    priority_fee = w3.to_wei(0.0001, 'gwei')
    tx = mixswap_contract.functions.mixSwap(*params).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': int(max_fee),
        'maxPriorityFeePerGas': int(priority_fee),
        'gas': 250000,
        'chainId': w3.eth.chain_id,
        'value': 0
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

def do_swap_pepe_to_mog(w3, account, private_key, mixswap_contract, pepe_contract, swap_amount_pepe, pepe_decimals):
    amount_in = int(swap_amount_pepe * (10 ** pepe_decimals))
    amount_out_min = 1
    amount_out_min_97 = 1
    allowance = check_allowance(w3, pepe_contract, account.address, MIXSWAP_ADDRESS)
    if allowance < amount_in:
        approve_hash, _ = approve_token(w3, account, private_key, pepe_contract, MIXSWAP_ADDRESS, amount_in)
        time.sleep(5)
    params = [
        PEPE_ADDRESS,
        MOG_ADDRESS,
        amount_in,
        amount_out_min,
        amount_out_min_97,
        [Web3.to_checksum_address("0x0f9053E174c123098C17e60A2B1FAb3b303f9e29")],
        [Web3.to_checksum_address("0x3c5B24D0aE4e8747e824378872bc29ABB34db9ef")],
        [Web3.to_checksum_address("0x3c5B24D0aE4e8747e824378872bc29ABB34db9ef"), MIXSWAP_ADDRESS],
        0,
        [bytes.fromhex("00")],
        bytes.fromhex("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        int(time.time()) + 600
    ]
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    max_fee = max(gas_price * 2, w3.to_wei(0.0001, 'gwei'))
    priority_fee = w3.to_wei(0.0001, 'gwei')
    tx = mixswap_contract.functions.mixSwap(*params).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': int(max_fee),
        'maxPriorityFeePerGas': int(priority_fee),
        'gas': 300000,
        'chainId': w3.eth.chain_id,
        'value': 0
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

def do_swap_mog_to_wbtc(w3, account, private_key, mixswap_contract, mog_contract, swap_amount_mog, mog_decimals):
    amount_in = int(swap_amount_mog * (10 ** mog_decimals))
    amount_out_min = 1
    amount_out_min_97 = 1
    allowance = check_allowance(w3, mog_contract, account.address, MIXSWAP_ADDRESS)
    if allowance < amount_in:
        approve_hash, _ = approve_token(w3, account, private_key, mog_contract, MIXSWAP_ADDRESS, amount_in)
        time.sleep(5)
    params = [
        MOG_ADDRESS,
        WBTC_ADDRESS,
        amount_in,
        amount_out_min,
        amount_out_min_97,
        [Web3.to_checksum_address("0x0f9053E174c123098C17e60A2B1FAb3b303f9e29")],
        [Web3.to_checksum_address("0x9B142d96A2E05322820edb611c2211efe82f8471")],
        [Web3.to_checksum_address("0x9B142d96A2E05322820edb611c2211efe82f8471"), MIXSWAP_ADDRESS],
        1,
        [bytes.fromhex("00")],
        bytes.fromhex("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        int(time.time()) + 600
    ]
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    max_fee = max(gas_price * 2, w3.to_wei(0.0001, 'gwei'))
    priority_fee = w3.to_wei(0.0001, 'gwei')
    tx = mixswap_contract.functions.mixSwap(*params).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': int(max_fee),
        'maxPriorityFeePerGas': int(priority_fee),
        'gas': 250000,
        'chainId': w3.eth.chain_id,
        'value': 0
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

def do_swap_wbtc_to_usdc(w3, account, private_key, mixswap_contract, wbtc_contract, swap_amount_wbtc, wbtc_decimals):
    amount_in = int(swap_amount_wbtc * (10 ** wbtc_decimals))
    amount_out_min = 1
    amount_out_min_97 = 1
    allowance = check_allowance(w3, wbtc_contract, account.address, MIXSWAP_ADDRESS)
    if allowance < amount_in:
        approve_hash, _ = approve_token(w3, account, private_key, wbtc_contract, MIXSWAP_ADDRESS, amount_in)
        time.sleep(5)
    params = [
        WBTC_ADDRESS,
        USDC_ADDRESS,
        amount_in,
        amount_out_min,
        amount_out_min_97,
        [Web3.to_checksum_address("0x0f9053E174c123098C17e60A2B1FAb3b303f9e29")],
        [Web3.to_checksum_address("0xA3e766D777793DaAad9b57d00A523D5FcF31260A")],
        [Web3.to_checksum_address("0xA3e766D777793DaAad9b57d00A523D5FcF31260A"), MIXSWAP_ADDRESS],
        1,
        [bytes.fromhex("00")],
        bytes.fromhex("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        int(time.time()) + 600
    ]
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    max_fee = max(gas_price * 2, w3.to_wei(0.0001, 'gwei'))
    priority_fee = w3.to_wei(0.0001, 'gwei')
    tx = mixswap_contract.functions.mixSwap(*params).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': int(max_fee),
        'maxPriorityFeePerGas': int(priority_fee),
        'gas': 250000,
        'chainId': w3.eth.chain_id,
        'value': 0
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

def do_swap_usdc_to_usdt(w3, account, private_key, mixswap_contract, usdc_contract, swap_amount_usdc, usdc_decimals):
    USDT_ADDRESS = Web3.to_checksum_address("0x40918Ba7f132E0aCba2CE4de4c4baF9BD2D7D849")
    amount_in = int(swap_amount_usdc * (10 ** usdc_decimals))
    amount_out_min = 1
    amount_out_min_97 = 1
    allowance = check_allowance(w3, usdc_contract, account.address, MIXSWAP_ADDRESS)
    if allowance < amount_in:
        approve_hash, _ = approve_token(w3, account, private_key, usdc_contract, MIXSWAP_ADDRESS, amount_in)
        time.sleep(5)
    params = [
        USDC_ADDRESS,
        USDT_ADDRESS,
        amount_in,
        amount_out_min,
        amount_out_min_97,
        [Web3.to_checksum_address("0x0f9053E174c123098C17e60A2B1FAb3b303f9e29")],
        [Web3.to_checksum_address("0x1E10EBe824fb5ff849ad3441Ebc793756A7aBe9c")],
        [Web3.to_checksum_address("0x1E10EBe824fb5ff849ad3441Ebc793756A7aBe9c"), MIXSWAP_ADDRESS],
        1,
        [bytes.fromhex("00")],
        bytes.fromhex("00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"),
        int(time.time()) + 600
    ]
    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price
    max_fee = max(gas_price * 2, w3.to_wei(0.0001, 'gwei'))
    priority_fee = w3.to_wei(0.0001, 'gwei')
    tx = mixswap_contract.functions.mixSwap(*params).build_transaction({
        'from': account.address,
        'nonce': nonce,
        'maxFeePerGas': int(max_fee),
        'maxPriorityFeePerGas': int(priority_fee),
        'gas': 250000,
        'chainId': w3.eth.chain_id,
        'value': 0
    })
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex(), receipt

def print_saldo(judul, eth, usdt, pepe, mog, wbtc, usdc, usdt_symbol, pepe_symbol, mog_symbol, wbtc_symbol, usdc_symbol):
    print(warna(f"\n[{judul}]", YELLOW))
    print(f"Native: {eth:.6f} ETH")
    print(f"USDT  : {usdt:.3f} {usdt_symbol}")
    print(f"PEPE  : {int(pepe)} {pepe_symbol}")
    print(f"MOG   : {int(mog)} {mog_symbol}")
    print(f"WBTC  : {wbtc:.7f} {wbtc_symbol}")
    print(f"USDC  : {usdc:.3f} {usdc_symbol}")

def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("RPC gagal terhubung!")
        return

    usdt_decimals, usdt_symbol = get_token_info(w3, USDT_ADDRESS)
    pepe_decimals, pepe_symbol = get_token_info(w3, PEPE_ADDRESS)
    mog_decimals, mog_symbol = get_token_info(w3, MOG_ADDRESS)
    wbtc_decimals, wbtc_symbol = get_token_info(w3, WBTC_ADDRESS)
    usdc_decimals, usdc_symbol = get_token_info(w3, USDC_ADDRESS)

    usdt_contract = w3.eth.contract(address=USDT_ADDRESS, abi=EXTENDED_ERC20_ABI)
    pepe_contract = w3.eth.contract(address=PEPE_ADDRESS, abi=EXTENDED_ERC20_ABI)
    mog_contract  = w3.eth.contract(address=MOG_ADDRESS, abi=EXTENDED_ERC20_ABI)
    wbtc_contract = w3.eth.contract(address=WBTC_ADDRESS, abi=EXTENDED_ERC20_ABI)
    usdc_contract = w3.eth.contract(address=USDC_ADDRESS, abi=EXTENDED_ERC20_ABI)
    mixswap_contract = w3.eth.contract(address=MIXSWAP_ADDRESS, abi=MIXSWAP_ABI)

    private_keys = read_private_keys("pvkey.txt")
    if not private_keys:
        return

    swap_amount_usdt = 0.005
    swap_amount_pepe = 1000
    swap_amount_mog  = 1
    swap_amount_wbtc = 0.0000005
    swap_amount_usdc = 0.005

    rounds = int(input("Berapa kali proses (rounds)? "))

    for round_num in range(1, rounds + 1):
        print(f"\n=== ROUND {round_num}/{rounds} ===")

        wallet_has_enough = False
        for pk in private_keys:
            account = Account.from_key(pk)
            WALLET = account.address
            usdt0 = get_balance(w3, usdt_contract, WALLET, usdt_decimals)[0]
            pepe0 = get_balance(w3, pepe_contract, WALLET, pepe_decimals)[0]
            mog0 = get_balance(w3, mog_contract, WALLET, mog_decimals)[0]
            wbtc0 = get_balance(w3, wbtc_contract, WALLET, wbtc_decimals)[0]
            usdc0 = get_balance(w3, usdc_contract, WALLET, usdc_decimals)[0]
            if (usdt0 >= swap_amount_usdt or
                pepe0 >= swap_amount_pepe or
                mog0 >= swap_amount_mog or
                wbtc0 >= swap_amount_wbtc or
                usdc0 >= swap_amount_usdc):
                wallet_has_enough = True
                break
        if not wallet_has_enough:
            print(warna("❌ Semua wallet kekurangan saldo swap. Proses dihentikan.", RED))
            break

        for idx, pk in enumerate(private_keys):
            garis()
            account = Account.from_key(pk)
            WALLET = account.address
            print(f"\n[{idx+1}/{len(private_keys)}] Wallet: {WALLET}")

            # Saldo awal
            eth0 = get_native_balance(w3, WALLET)
            usdt0 = get_balance(w3, usdt_contract, WALLET, usdt_decimals)[0]
            pepe0 = get_balance(w3, pepe_contract, WALLET, pepe_decimals)[0]
            mog0 = get_balance(w3, mog_contract, WALLET, mog_decimals)[0]
            wbtc0 = get_balance(w3, wbtc_contract, WALLET, wbtc_decimals)[0]
            usdc0 = get_balance(w3, usdc_contract, WALLET, usdc_decimals)[0]

            print_saldo("Saldo Awal", eth0, usdt0, pepe0, mog0, wbtc0, usdc0, usdt_symbol, pepe_symbol, mog_symbol, wbtc_symbol, usdc_symbol)

            # Swap USDT -> PEPE
            if usdt0 >= swap_amount_usdt:
                try:
                    print(warna(f"\nSwap USDT -> PEPE [{swap_amount_usdt} USDT]", CYAN))
                    tx_hash1, receipt1 = do_swap_usdt_to_pepe(
                        w3, account, pk, mixswap_contract, usdt_contract, swap_amount_usdt, usdt_decimals
                    )
                    print(f"Tx    : {tx_hash1}")
                    print(f"Blok  : {receipt1.blockNumber}")
                    print(warna("Status: ✅Swap sukses", GREEN) if receipt1.status == 1 else warna("Status: Swap gagal", RED))
                except Exception as e:
                    print(warna(f"Status: ❌Swap gagal ({e})", RED))
                time.sleep(5)
            else:
                print(f"\n❌ Saldo USDT kurang dari {swap_amount_usdt}, skip swap USDT -> PEPE")

            # Swap PEPE -> MOG
            pepe_now = get_balance(w3, pepe_contract, WALLET, pepe_decimals)[0]
            if pepe_now >= swap_amount_pepe:
                try:
                    print(warna(f"\nSwap PEPE -> MOG [{int(swap_amount_pepe)} PEPE]", CYAN))
                    tx_hash2, receipt2 = do_swap_pepe_to_mog(
                        w3, account, pk, mixswap_contract, pepe_contract, swap_amount_pepe, pepe_decimals
                    )
                    print(f"Tx    : {tx_hash2}")
                    print(f"Blok  : {receipt2.blockNumber}")
                    print(warna("Status: ✅Swap sukses", GREEN) if receipt2.status == 1 else warna("Status: Swap gagal", RED))
                except Exception as e:
                    print(warna(f"Status: ❌Swap gagal ({e})", RED))
                time.sleep(5)
            else:
                print(f"\n❌ Saldo PEPE kurang dari {int(swap_amount_pepe)}, skip swap PEPE -> MOG")

            # Swap MOG -> WBTC
            mog_now = get_balance(w3, mog_contract, WALLET, mog_decimals)[0]
            if mog_now >= swap_amount_mog:
                try:
                    print(warna(f"\nSwap MOG -> WBTC [{int(swap_amount_mog)} MOG]", CYAN))
                    tx_hash3, receipt3 = do_swap_mog_to_wbtc(
                        w3, account, pk, mixswap_contract, mog_contract, swap_amount_mog, mog_decimals
                    )
                    print(f"Tx    : {tx_hash3}")
                    print(f"Blok  : {receipt3.blockNumber}")
                    print(warna("Status: ✅Swap sukses", GREEN) if receipt3.status == 1 else warna("Status: Swap gagal", RED))
                except Exception as e:
                    print(warna(f"Status: ❌Swap gagal ({e})", RED))
                time.sleep(5)
            else:
                print(f"\n❌ Saldo MOG kurang dari {int(swap_amount_mog)}, skip swap MOG -> WBTC")

            # Swap WBTC -> USDC
            wbtc_now = get_balance(w3, wbtc_contract, WALLET, wbtc_decimals)[0]
            if wbtc_now >= swap_amount_wbtc:
                try:
                    print(warna(f"\nSwap WBTC -> USDC [{swap_amount_wbtc} WBTC]", CYAN))
                    tx_hash4, receipt4 = do_swap_wbtc_to_usdc(
                        w3, account, pk, mixswap_contract, wbtc_contract, swap_amount_wbtc, wbtc_decimals
                    )
                    print(f"Tx    : {tx_hash4}")
                    print(f"Blok  : {receipt4.blockNumber}")
                    print(warna("Status: ✅Swap sukses", GREEN) if receipt4.status == 1 else warna("Status: Swap gagal", RED))
                except Exception as e:
                    print(warna(f"Status: ❌Swap gagal ({e})", RED))
                time.sleep(5)
            else:
                print(f"\n❌ Saldo WBTC kurang dari {swap_amount_wbtc}, skip swap WBTC -> USDC")

            # Swap USDC -> USDT
            usdc_now = get_balance(w3, usdc_contract, WALLET, usdc_decimals)[0]
            if usdc_now >= swap_amount_usdc:
                try:
                    print(warna(f"\nSwap USDC -> USDT [{swap_amount_usdc} USDC]", CYAN))
                    tx_hash5, receipt5 = do_swap_usdc_to_usdt(
                        w3, account, pk, mixswap_contract, usdc_contract, swap_amount_usdc, usdc_decimals
                    )
                    print(f"Tx    : {tx_hash5}")
                    print(f"Blok  : {receipt5.blockNumber}")
                    print(warna("Status: ✅Swap sukses", GREEN) if receipt5.status == 1 else warna("Status: Swap gagal", RED))
                except Exception as e:
                    print(warna(f"Status: ❌Swap gagal ({e})", RED))
                time.sleep(5)
            else:
                print(f"\n❌ Saldo USDC kurang dari {swap_amount_usdc}, skip swap USDC -> USDT")

            # Saldo akhir
            eth1 = get_native_balance(w3, WALLET)
            usdt1 = get_balance(w3, usdt_contract, WALLET, usdt_decimals)[0]
            pepe1 = get_balance(w3, pepe_contract, WALLET, pepe_decimals)[0]
            mog1 = get_balance(w3, mog_contract, WALLET, mog_decimals)[0]
            wbtc1 = get_balance(w3, wbtc_contract, WALLET, wbtc_decimals)[0]
            usdc1 = get_balance(w3, usdc_contract, WALLET, usdc_decimals)[0]

            print_saldo("Saldo Akhir", eth1, usdt1, pepe1, mog1, wbtc1, usdc1, usdt_symbol, pepe_symbol, mog_symbol, wbtc_symbol, usdc_symbol)

            tx_count = w3.eth.get_transaction_count(WALLET)
            print(f"Total TX on-chain: {tx_count}")

    garis()
    print(warna("Selesai semua wallet di round ini.", YELLOW))

if __name__ == "__main__":
    main()
