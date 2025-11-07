from web3 import Web3
import json
import time
import random
from eth_abi import encode
from colorama import Fore, Style, init
init(autoreset=True)
from web3.middleware import geth_poa_middleware
from decimal import Decimal, getcontext
getcontext().prec = 28

# === LOAD NETWORK CONFIG ===
with open("network_config.json") as f:
    network_config = json.load(f)

print("\n=== PILIH JARINGAN ===")
for i, net in enumerate(network_config.keys()):
    print(f"[{i}] {network_config[net]['name']}")
selected = int(input("Masukkan nomor jaringan: "))
netconf = list(network_config.values())[selected]
native_symbol = netconf["native_symbol"]
contracts = netconf["contracts"]
address_to_name = {v.lower(): k for k, v in contracts.items()}

web3 = Web3(Web3.HTTPProvider(netconf["rpcUrl"]))
web3.middleware_onion.inject(geth_poa_middleware, layer=0)
assert web3.is_connected(), "Gagal konek ke jaringan"
chain_id = web3.eth.chain_id

# === LOAD ABI ===
with open("abi_bundle.json") as f:
    abis = json.load(f)

erc20_abi = abis["erc20"]
add_liq_abi = abis["add_liquidity"]
staking_abi = abis["staking"]

# === KONTRAK ===
def to_addr(addr): return Web3.to_checksum_address(addr)

USDC = web3.eth.contract(address=to_addr(contracts["USDC"]), abi=erc20_abi)
R2USD = web3.eth.contract(address=to_addr(contracts["R2USD"]), abi=erc20_abi)
SR2USD = web3.eth.contract(address=to_addr(contracts["SR2USD"]), abi=erc20_abi)
WBTC = web3.eth.contract(address=to_addr(contracts["WBTC"]), abi=erc20_abi) if contracts["WBTC"] else None
LIQ2 = web3.eth.contract(address=to_addr(contracts["LIQUIDITY2"]), abi=add_liq_abi) if contracts["LIQUIDITY2"] else None
STAKE = web3.eth.contract(address=to_addr(contracts["STAKING"]), abi=staking_abi) if contracts["STAKING"] else None

def get_gas_params(custom_gwei=None):
    if netconf["name"].lower().startswith("monad"):
        return {
            "maxFeePerGas": web3.to_wei("50", "gwei"),
            "maxPriorityFeePerGas": web3.to_wei("1", "gwei")
        }
    else:
        gwei = custom_gwei if custom_gwei else 20
        return {
            "gasPrice": web3.to_wei(gwei, "gwei")
        }

# === TX HELPER ===
def send(tx):
    signed = web3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
    print("Tx:", tx_hash.hex())
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    print("Blok:", receipt.blockNumber)
    time.sleep(2)
    return receipt

# === APPROVE ===
def approve(token, spender, amount):
    if token and spender:
        preferred_names = ["R2USD", "SR2USD", "WBTC"]
        address_to_name = {}

        for name in preferred_names:
            addr = contracts.get(name)
            if addr:
                address_to_name[addr.lower()] = name

        for name, addr in contracts.items():
            if addr and addr.lower() not in address_to_name:
                address_to_name[addr.lower()] = name

        token_address_lower = token.address.lower()
        token_name = address_to_name.get(token_address_lower, token_address_lower)

        print(Fore.CYAN + f"[APPROVE] Approving {token_name}..." + Style.RESET_ALL)

        r2usd_balance = R2USD.functions.balanceOf(WALLET).call()
        wbtc_balance = WBTC.functions.balanceOf(WALLET).call() if WBTC else 0

        if token_name == "R2USD" and r2usd_balance == 0:
            print(Fore.RED + "[!] Gagal approve R2USD karena saldo token kurang" + Style.RESET_ALL)
            print()
            return

        if token_name == "WBTC" and wbtc_balance < int(0.01 * 1e8):
            print(Fore.RED + "[!] Gagal approve WBTC karena saldo token kurang" + Style.RESET_ALL)
            print()
            return

        if token_name == "SR2USD" and r2usd_balance == 0:
            print(Fore.RED + "[!] Gagal approve SR2USD karena saldo R2USD kurang" + Style.RESET_ALL)
            print()
            return

        try:
            nonce = web3.eth.get_transaction_count(WALLET, "pending")
            tx = token.functions.approve(spender, amount).build_transaction({
                "from": WALLET,
                "nonce": nonce,
                "chainId": chain_id,
                "gas": web3.eth.estimate_gas({
                    "from": WALLET,
                    "to": token.address,
                    "data": token.encodeABI(fn_name="approve", args=[spender, amount])
                }),
                **get_gas_params(),
            })
            send(tx)
            print(Fore.GREEN + "[✓] Approve berhasil" + Style.RESET_ALL)
            print()
        except Exception as e:
            print(Fore.RED + f"[!] Gagal approve {token_name}" + Style.RESET_ALL)
            print()
    time.sleep(random.uniform(2, 4))

# === SWAP USDC to R2USD ===
def swap_usdc(amount):
    print(Fore.CYAN + f"[SWAP] Menukar {amount / 1e6:.2f} USDC ke R2USD..." + Style.RESET_ALL)
    try:
        data = Web3.to_hex(bytes.fromhex("095e7a95") + encode(
            ['address', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256', 'uint256'],
            [WALLET, amount, 0, 0, 0, 0, 0]
        ))

        contract_address = to_addr(contracts["R2USD"])
        nonce = web3.eth.get_transaction_count(WALLET, "pending")

        tx = {
            "from": WALLET,
            "to": contract_address,
            "data": data,
            "chainId": chain_id,
            "nonce": nonce,
            "gas": web3.eth.estimate_gas({
                "from": WALLET,
                "to": contract_address,
                "data": data
            }),
            **get_gas_params(),
        }
        send(tx)
        print(Fore.GREEN + "[✓] Swap USDC ke RUSD berhasil" + Style.RESET_ALL)
        print()
    except Exception as e:
        print(Fore.RED + f"[!] Gagal swap USDC karena saldo token kurang" + Style.RESET_ALL)
        print()
        time.sleep(random.uniform(2, 4))

# === STAKE R2USD TO SR2USD ===
def stake_sr2(amount):
    print(Fore.CYAN + f"[STAKE] Menstake {amount / 1e6:.2f} R2USD ke sR2USD..." + Style.RESET_ALL)
    try:
        data = Web3.to_hex(bytes.fromhex("1a5f0f00") + encode(['uint256'] * 10, [amount] + [0]*9))
        contract_address = to_addr(contracts["STAKE_SR2"])

        tx = {
            "from": WALLET,
            "to": contract_address,
            "data": data,
            "chainId": chain_id,
            "nonce": web3.eth.get_transaction_count(WALLET, "pending"),
            "gas": web3.eth.estimate_gas({
                "from": WALLET,
                "to": contract_address,
                "data": data
            }),
            **get_gas_params(),
        }
        send(tx)
        print(Fore.GREEN + "[✓] Stake R2USD ke sR2USD berhasil" + Style.RESET_ALL)
        print()
    except Exception as e:
        print(Fore.RED + f"[!] Gagal stake R2USD karena saldo token kurang" + Style.RESET_ALL)
        print()
        time.sleep(random.uniform(2, 4))


# === GET POOL RATIO ===
def get_ratio(contract, tokenA, tokenB):
    a = tokenA.functions.balanceOf(contract.address).call()
    b = tokenB.functions.balanceOf(contract.address).call()
    return a / b if b else 1

def show_balances(prefix=""):
    native = web3.eth.get_balance(WALLET) / 1e18
    usdc = USDC.functions.balanceOf(WALLET).call() / 1e6
    r2usd = R2USD.functions.balanceOf(WALLET).call() / 1e6
    sr2usd = SR2USD.functions.balanceOf(WALLET).call() / 1e6
    wbtc = WBTC.functions.balanceOf(WALLET).call() / 1e8 if WBTC else None

    rows = [
        [native_symbol, f"{native:.4f}"],
        ["USDC", f"{usdc:.0f}"],
        ["R2USD", f"{r2usd:.0f}"],
        ["sR2USD", f"{sr2usd:.0f}"]
    ]
    if wbtc is not None:
        rows.append(["WBTC", f"{wbtc:.3f}"])

    print(Fore.CYAN + f"\n{prefix}Saldo Wallet:" + Style.RESET_ALL)
    for token, saldo in rows:
        print(f"  - {token:<7}: {saldo}")

# === CEK SALDO CUKUP ===
def check_enough():
    native = web3.eth.get_balance(WALLET)
    usdc = USDC.functions.balanceOf(WALLET).call()
    sr2 = SR2USD.functions.balanceOf(WALLET).call()
    wbtc = WBTC.functions.balanceOf(WALLET).call() if WBTC else 10**8

    issues = []
    if native < 0.001 * 1e18:
        issues.append(f"Native ({native / 1e18:.4f} < 0.001)")
    if usdc < 0 * 1e6:
        issues.append(f"USDC ({usdc / 1e6:.2f} < 1000)")
    if WBTC and wbtc < 0.001 * 1e8:
        issues.append(f"WBTC ({wbtc / 1e8:.3f} < 0.01)")

    if issues:
        print(Fore.RED + "[!] Wallet dilewati karena saldo tidak mencukupi:" + Style.RESET_ALL)
        for msg in issues:
            print(Fore.RED + f"  - {msg}" + Style.RESET_ALL)
        return False
    return True

# === ADD LP R2USD / SR2USD ===
def add_lp_r2_sr2(amount):
    try:
        if LIQ2:
            ratio = Decimal(get_ratio(LIQ2, SR2USD, R2USD))
            sr2_amt = int(Decimal(amount) * ratio)

            if sr2_amt < 1:
                print(Fore.YELLOW + "[LP2] sR2USD terlalu kecil, LP dilewati." + Style.RESET_ALL)
                return

            approve(R2USD, LIQ2.address, amount)
            approve(SR2USD, LIQ2.address, sr2_amt)
            nonce = web3.eth.get_transaction_count(WALLET, "pending")
            print(Fore.CYAN + "[LP2] Menambahkan liquidity R2USD/sR2USD..." + Style.RESET_ALL)
            tx = LIQ2.functions.add_liquidity([sr2_amt, amount], 0, WALLET).build_transaction({
                "from": WALLET,
                "nonce": nonce,
                "gas": max(web3.eth.estimate_gas({
                    "from": WALLET,
                    "to": LIQ2.address,
                    "data": LIQ2.encodeABI(fn_name="add_liquidity", args=[[sr2_amt, amount], 0, WALLET])
                }), 250_000),
                **get_gas_params(40),
                "chainId": chain_id
            })
            send(tx)
            print(Fore.GREEN + "[✓] LP R2USD/sR2USD berhasil" + Style.RESET_ALL)
            print()
    except Exception as e:
        print(Fore.RED + f"[!] Gagal LP R2USD/sR2USD karena saldo token kurang" + Style.RESET_ALL)
        print()
        time.sleep(random.uniform(2, 4))

# === STAKE WBTC (ETH ONLY) ===
def stake_wbtc(amount):
    try:
        if STAKE and WBTC:
            approve(WBTC, STAKE.address, amount)
            nonce = web3.eth.get_transaction_count(WALLET, "pending")
            print(Fore.CYAN + "[STAKE-WBTC] Staking WBTC..." + Style.RESET_ALL)
            tx = STAKE.functions.stake(WBTC.address, amount).build_transaction({
                "from": WALLET,
                "nonce": nonce,
                "gas": web3.eth.estimate_gas({
                    "from": WALLET,
                    "to": STAKE.address,
                    "data": STAKE.encodeABI(fn_name="stake", args=[WBTC.address, amount])
                }),
                **get_gas_params(),
                "chainId": chain_id
            })
            send(tx)
            print(Fore.GREEN + "[✓] Stake 0.01 WBTC berhasil" + Style.RESET_ALL)
            print()
    except Exception as e:
        print(Fore.RED + f"[!] Gagal stake WBTC karena saldo token kurang" + Style.RESET_ALL)
        print()
        time.sleep(random.uniform(2, 4))

# === MULTI WALLET EXECUTION ===
with open("pvkey.txt", "r") as f:
    PRIVATE_KEYS = [line.strip() if line.strip().startswith("0x") else "0x" + line.strip() for line in f if line.strip()]

loop_count = int(input("Mau berapa kali proses per wallet? "))

for run in range(loop_count):
    print(f"\n=== Proses ke-{run + 1} ===")
    all_wallets_empty = True
    for i, key in enumerate(PRIVATE_KEYS):
        print(f"\n=== Wallet {i+1} ===")
        account = web3.eth.account.from_key(key)
        WALLET = account.address
        PRIVATE_KEY = key
        print("Wallet:", WALLET)
        show_balances("[Awal] ")
        print()

        usdc_raw = USDC.functions.balanceOf(WALLET).call()
        r2usd_raw = R2USD.functions.balanceOf(WALLET).call()
        sr2usd_raw = SR2USD.functions.balanceOf(WALLET).call()
        native_raw = web3.eth.get_balance(WALLET)
        wbtc_raw = WBTC.functions.balanceOf(WALLET).call() if WBTC else 10**8

        usdc_amount = int(2222 * 1e6)
        if chain_id in [97, 84532, 688688]:
            stake_amount = int(2222 * 1e6)
        else:
            stake_amount = int(1111 * 1e6)
        wbtc_amount = int(0.01 * 1e8)
        swap_usdc(usdc_amount)
        stake_sr2(stake_amount)

        if LIQ2 and chain_id in [11155111, 421614, 98867, 10143]:
            add_lp_r2_sr2(stake_amount)

        if STAKE and WBTC and chain_id == 11155111:
            stake_wbtc(wbtc_amount)

        show_balances("[Akhir] ")
        print()
        tx_count = web3.eth.get_transaction_count(WALLET)
        print(f"  Total TX on-chain: {tx_count}")

    if all_wallets_empty:
        print(Fore.RED + "\n[!] proses selesai" + Style.RESET_ALL)
        break

    time.sleep(3)
