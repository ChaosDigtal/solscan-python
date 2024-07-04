import requests
import time

start_time = time.time()

token_address = "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux"

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
print(response.json())

print(f'finished in {time.time() - start_time} milliseconds')