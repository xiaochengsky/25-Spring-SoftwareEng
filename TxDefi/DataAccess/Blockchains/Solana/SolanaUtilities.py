from solders.keypair import Keypair
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
import base58
from spl.token.constants import *
import numpy as np
import requests
import ast

GLOBAL_ADDRESS = '4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf'
EVENT_AUTHORITY = 'Ce6TQqeHC9p8KetsN6JsjHK7UTZk7nasjjnr7XxXp9F1'
SOL_DECIMALS = NATIVE_DECIMALS
SOL_SCALE_FACTOR = 10**NATIVE_DECIMALS
TOKEN_2022_PROGRAM_ADDRESS = str(TOKEN_2022_PROGRAM_ID)
TOKEN_PROGRAM_ADDRESS=str(TOKEN_PROGRAM_ID)
WRAPPED_SOL_MINT_ADDRESS = str(WRAPPED_SOL_MINT)
UNWRAPPED_SOL_MINT_ADDRESS = "11111111111111111111111111111111"
SYSVAR_SYSTEM_PROGRAM_ID =   '11111111111111111111111111111111'
SYSVAR_RENT = 'SysvarRent111111111111111111111111111111111'
NATIVE_MINT_2022 = '9pan9bMn5HatX4EJdBwg9VgCa7Uz5HL8N1m5D3NdXejP'

system_program_pk = Pubkey.from_string(SYSVAR_SYSTEM_PROGRAM_ID)

solana_pubkeys: dict[str, Pubkey] = {   str(ASSOCIATED_TOKEN_PROGRAM_ID): ASSOCIATED_TOKEN_PROGRAM_ID, 
                                        str(TOKEN_PROGRAM_ID): TOKEN_PROGRAM_ID,
                                        str(TOKEN_2022_PROGRAM_ID): TOKEN_2022_PROGRAM_ID,
                                        str(WRAPPED_SOL_MINT): WRAPPED_SOL_MINT
                                    }
#solana utilities
def create_new_payer_keys():
    return Keypair()   

#Get keys from a base58 string (e.g. Phantom)
def get_payer_keys(keysString: str):
    return Keypair.from_base58_string(keysString)

#Get keys from a byte array string (e.g. Phantom)
def get_payer_keys_from_array(keysString: str):
    list = ast.literal_eval(keysString)
    uint8_array = np.array(list, dtype=np.uint8)
            
    payerKeys = Keypair.from_bytes(uint8_array)
    return payerKeys

def get_solana_price()->float:
    # Endpoint for Solana price data
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd'
    try:
        # Make a GET request to the API
        response = requests.get(url)
        # Check if request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            # Extract the price of Solana in USD
            solana_price = data['solana']['usd']
            return solana_price
        else:
            #print("get_solana_price failed to fetch data:", response.status_code)
            return None
    except Exception as e:
        print("An error occurred:", e)
        return None

def get_private_key(keypair: Keypair)->str:
    # Get the private key (secret key)
    return base58.b58encode(bytes(keypair)).decode()