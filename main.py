import requests
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from base58 import b58decode
import asyncio
from decimal import Decimal, getcontext
import time

getcontext().prec = 30

def get_usdc_price_on_solana(token_address):
    url = "https://api.coingecko.com/api/v3/simple/token_price/solana"
    params = {
        'contract_addresses': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        'vs_currencies': 'usd'
    }
    response = requests.get(url, params=params)
    data = response.json()
    return Decimal(data['EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v']['usd'])

def get_balance_sol(wallet_address):
    client = Client("https://api.mainnet-beta.solana.com")
    binary_address = b58decode(wallet_address)
    public_key = Pubkey(binary_address)
    balance = client.get_balance(public_key)
    balance_in_sol = Decimal(balance.value) / Decimal(1000000000)
    return balance_in_sol

def getTokenMetadata(token_address):
    response = requests.post('https://mainnet.helius-rpc.com/?api-key=35eb685f-3541-4c70-a396-7aa18696c965',
        headers= {
            "Content-Type": "application/json"
        },
        json= {
            "jsonrpc": "2.0",
            "id": "",
            "method": "getAsset",
            "params": {
                "id": token_address,
                "displayOptions": {
                    "showUnverifiedCollections": True,
                    "showCollectionMetadata": True,
                    "showFungible": True,
                    "showInscription": True
                }
            }
        },
    )
    response = response.json()
    return response
    
def getWalletHoldings(wallet_address):
    response = requests.post('https://mainnet.helius-rpc.com/?api-key=35eb685f-3541-4c70-a396-7aa18696c965',
        headers= {
            "Content-Type": "application/json"
        },
        json= {
            "jsonrpc": "2.0",
            "id": "",
            "method": "getTokenAccounts",
            "params": {
                "owner": wallet_address,
                "displayOptions": {
                }
            }
        },
    )
    response = response.json()
    
    holdings = []
    total_token_usd_amount = Decimal(0)
    
    for token in response['result']['token_accounts']:
        token_metadata = getTokenMetadata(token['mint'])
        quantity = Decimal(token['amount']) / (Decimal(10) ** token_metadata['result']['token_info']['decimals'])
        # Assume 1 USDC = $1
        usd_per_token = Decimal(token_metadata['result']['token_info']['price_info']['price_per_token'])
        # If you use the live USDC price
        # usd_per_token = Decimal(token_metadata['result']['token_info']['price_info']['price_per_token']) * (get_usdc_price_on_solana())
        usd_amount = quantity * usd_per_token
        holdings.append({
            "token_id": token['mint'],
            "name": token_metadata['result']['content']['metadata']['name'],
            "symbol": token_metadata['result']['token_info']['symbol'],
            "usd_per_token": usd_per_token,
            "quantity": quantity,
            "usd_amount": usd_amount,
        })
        total_token_usd_amount += usd_amount
    sol_balance = get_balance_sol(wallet_address)
    sol_usd_price = Decimal(requests.get("https://api.coincap.io/v2/assets/solana").json()['data']['priceUsd'])
    sol_usd_amount = sol_balance * sol_usd_price
    return {
        'holding_tokens': holdings,
        'total_token_usd_amount': total_token_usd_amount,
        'sol_balance': sol_balance,
        'sol_usd_amount': sol_usd_amount,
        'total_usd_balance': total_token_usd_amount + sol_usd_amount
    }
def main():

    token_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    print(getTokenMetadata(token_address))
    
    print("=================")

    wallet_address = 'CckxW6C1CjsxYcXSiDbk7NYfPLhfqAm3kSB5LEZunnSE'

    print(getWalletHoldings(wallet_address))
    
main()