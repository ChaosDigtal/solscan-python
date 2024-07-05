import requests
import os
from dotenv import load_dotenv, dotenv_values 
import re
import json
import psycopg2
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from base58 import b58decode
from decimal import Decimal, getcontext
import time

load_dotenv()
getcontext().prec = int(os.getenv('MAX_PRECISION'))

def get_connection():
    try:
        return psycopg2.connect(
            database=os.getenv('DB_name'),
            user=os.getenv('DB_user'),
            password=os.getenv('DB_password'),
            host=os.getenv('DB_host'),
            port=os.getenv('DB_port'),
        )
    except:
        return False
conn = get_connection()
if conn:
    print("Connection to the PostgreSQL established successfully.")
else:
    print("Connection to the PostgreSQL encountered and error.")

# Get USDC price on Solana Chain
def get_usdc_price_on_solana(token_address):
    url = "https://api.coingecko.com/api/v3/simple/token_price/solana"
    params = {
        'contract_addresses': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        'vs_currencies': 'usd'
    }
    response = requests.get(url, params=params)
    data = response.json()
    return Decimal(data['EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v']['usd'])

# Get SOL balance for given wallet address
def get_balance_sol(wallet_address):
    client = Client("https://api.mainnet-beta.solana.com")
    binary_address = b58decode(wallet_address)
    public_key = Pubkey(binary_address)
    balance = client.get_balance(public_key)
    balance_in_sol = Decimal(balance.value) / Decimal(1000000000)
    return balance_in_sol

# Get token metadata with live price(no social links/creation date)
def getTokenMetadataWihtLivePrice(token_address):
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
    curr = conn.cursor()
    curr.execute("SELECT * FROM sol_token_metadata where id=%s", (token_address,))
    row = curr.fetchone()
    if row is None:
        insert_query = """
        INSERT INTO sol_token_metadata (id, name, symbol, decimals)
        VALUES (%s, %s, %s, %s)
        """
        data = (token_address, response['result']['content']['metadata']['name'], response['result']['token_info']['symbol'], response['result']['token_info']['decimals'])
        curr.execute(insert_query, data)
        conn.commit()
    elif row[3] is None:
        update_query = """
        UPDATE sol_token_metadata
        SET decimals=%s
        WHERE id=%s
        """
        data = (response['result']['token_info']['decimals'], token_address)
        curr.execute(update_query, data)
        conn.commit()
    curr.close()
    return response

# Get holding tokens and sol balance of given wallet address
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
        token_metadata = getTokenMetadataWihtLivePrice(token['mint'])
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
    
# Get token metadta including social links & creation date
# First looks up on db, if exists fetch from it,
# If not exist, fetch from external sources(coinmarketcap api) and store into db
def getTokenMetadata(token_address):
    if token_address[:2] == '0x':
        token_address = token_address[2:]
    curr = conn.cursor()
    curr.execute("SELECT * FROM sol_token_metadata where id=%s", (token_address,))
    row = curr.fetchone()
    if row is not None and row[4] is not None and row[6] is not None:
        return row
    decimal = ''
    if row is not None:
        decimal = row[3]
    # Social links
    response = requests.get(f'https://pro-api.coinmarketcap.com/v2/cryptocurrency/info?CMC_PRO_API_KEY=2859b289-6ba0-4d5b-af14-250ba3d0ea20&address={token_address}').json()
    first_key = next(iter(response['data']))
    metadata = response['data'][first_key]
    # Creation date
    response = requests.get('https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json').content.decode('utf-8')
    pattern = rf'({token_address}(.*?)\]\,(.*?)\"(.*?)\")'
    matches =re.findall(pattern, response, re.DOTALL)
    creation_date = matches[0][3]
    if row is None:
        insert_query = """
        INSERT INTO sol_token_metadata (id, name, symbol, social_links, logo, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        data = (token_address, metadata['name'], metadata['symbol'], json.dumps(metadata['urls']), metadata['logo'], creation_date)
        curr.execute(insert_query, data)
    else:
        update_query = """
        UPDATE sol_token_metadata
        SET name=%s, symbol=%s, social_links=%s, logo=%s, created_at=%s
        WHERE id=%s
        """
        data = (metadata['name'], metadata['symbol'],  json.dumps(metadata['urls']), metadata['logo'], creation_date, token_address)
        curr.execute(update_query, data)
        
    conn.commit()
    curr.close()
    return (token_address, metadata['name'], metadata['symbol'], decimal, metadata['urls'], metadata['logo'], creation_date)


def main():

    token_address = "Hax9LTgsQkze1YFychnBLtFH8gYbQKtKfWKKg2SP6gdD"

    print(getTokenMetadata(token_address))
    
    print("=================")

    wallet_address = 'CckxW6C1CjsxYcXSiDbk7NYfPLhfqAm3kSB5LEZunnSE'

    print(getWalletHoldings(wallet_address))
    
    conn.close()
    
main()