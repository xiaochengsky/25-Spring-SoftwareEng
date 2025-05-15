from solders.transaction import VersionedTransaction
from jsonrpcclient import request
import json
import requests
import base64
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
from SolanaRpcApi import SolanaRpcApi
from SolanaTxBuilder import SolanaTxBuilder
import SolanaUtilities as sol_utils
import TxDefi.Utilities.HttpUtils as http_utils
from SolPubKey import SolPubKey

class RaydiumTxBuilder(SolanaTxBuilder):
    raydium_api_uri = "https://transaction-v1.raydium.io"
    raydium_quote_uri = raydium_api_uri + "/compute/swap-base-in"
    raydium_trade_uri = raydium_api_uri + "/transaction/swap-base-in"
    RAYDIUM_AUTHORITY_V4_ADDRESS = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1" #TODO pull from config
    RAYDIUM_V4_PROGRAM_ADDRESS = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

    def __init__(self, market_manager: AbstractMarketManager, solana_rpc_api: SolanaRpcApi):
        SolanaTxBuilder.__init__(self, solana_rpc_api)
        self.market_manager = market_manager
        self.solana_rpc_api = solana_rpc_api
    
    def build_transaction(self, order: SwapOrder, signer: SolPubKey)->VersionedTransaction:        
        if order.order_type == TradeEventType.BUY:
            input_mint = sol_utils.WRAPPED_SOL_MINT_ADDRESS
            output_mint = order.token_address
            associated_token_key = 'outputAccount'
            token_address = output_mint
            wrap_sol = True
            unwrap_sol = False
        else:
            input_mint = order.token_address
            output_mint = sol_utils.WRAPPED_SOL_MINT_ADDRESS
            associated_token_key = 'inputAccount'
            token_address = input_mint
            wrap_sol = False
            unwrap_sol = True
           
        associated_token_address = self.market_manager.get_associated_token_account(signer.get_account_address(), token_address)
        
        if order.use_signer_amount:
            amount_in = order.get_signer_amount(signer)
        else:
            amount_in = order.swap_settings.amount

        params = {
            "inputMint": input_mint,  
            "outputMint": output_mint, 
            "amount": amount_in.to_scaled(), 
            "slippageBps": order.swap_settings.slippage.to_scaled(),  # Slippage in basis points
            "txVersion": "V0"
        }

        quote_response = requests.get(self.raydium_quote_uri, params=params)
        
        if quote_response:  
            json_data = quote_response.json()
            
            headers = {'Content-Type': 'application/json'}

            body = {
                "wallet": signer.get_account_address(),
                "computeUnitPriceMicroLamports": "10000",
                "swapResponse": json_data,
                "txVersion": "V0",
                "wrapSol": wrap_sol,
                "unwrapSol": unwrap_sol,
                associated_token_key: associated_token_address #my associated token account
                # Uncomment and modify the following line if you have a fee account
                # "feeAccount": "fee_account_public_key"            
            }
            json_data = json.dumps(body)
            response = requests.post(self.raydium_trade_uri, headers=headers, data=json_data)    

            if response:
                data = response.json().get('data', [])
                                
                if len(data) > 0:
                    encoded_transaction = data[0].get('transaction')

                    if encoded_transaction:
                        raw_bytes = base64.b64decode(encoded_transaction)
                        raw_tx = VersionedTransaction.from_bytes(raw_bytes)
                        #TODO Add a jito instruction if required
                        return VersionedTransaction(raw_tx.message, [signer.get_key_pair()])

    #Retrieve a token't liquidity pool data using the Raydium v3 API
    @staticmethod
    def get_token_info(token_address: str)->TokenInfo:
        ray_uri = "https://api-v3.raydium.io/pools"
        ray_uri_marketid_uri = ray_uri + "/info/mint?mint1=" + token_address + "&poolType=all&poolSortField=default&sortType=desc&pageSize=1&page=1"

        #Make the API call
        market_data = http_utils.get_request(ray_uri_marketid_uri)
        
        if len(market_data) > 0 and market_data.get('data', {}).get('count', 0) > 0:
            try:
                market_id = market_data['data']['data'][0]['id']
                pool_info_uri = ray_uri + "/key/ids?ids=" + market_id
                ui_price = market_data['data']['data'][0]['price']
                pool_data = http_utils.get_request(pool_info_uri)
                                
                if len(pool_data) > 0:
                    pool_data = pool_data['data'][0]
                    mintA = pool_data['mintA']
                    mintB = pool_data['mintB']
                    vaultA = pool_data['vault']['A']
                    vaultB = pool_data['vault']['B']
            
                    if mintA['address'] == token_address:
                        token_mint_data = mintA
                        sol_mint_data = mintB
                        token_vault_address = vaultA
                        sol_vault_address = vaultB
                    else:
                        token_mint_data = mintB
                        sol_mint_data = mintA
                        token_vault_address = vaultB
                        sol_vault_address = vaultA
                        ui_price = 1/ui_price   
                    
                    decimals = token_mint_data['decimals']
                    token_info = TokenInfo(token_address, decimals)
        
                    token_info.metadata.program_type = SupportedPrograms.RAYDIUMLEGACY                 
                    token_info.ui_price.set_amount2(ui_price, Value_Type.UI)
                    token_info.metadata.token_program_address = token_mint_data['programId']
                    token_info.metadata.quoted_currency_address = sol_mint_data['address']
                    token_info.metadata.market_id = market_id
                    token_info.metadata.sol_vault_address = sol_vault_address
                    token_info.metadata.token_vault_address = token_vault_address
                   
                    token_info.metadata.symbol = token_mint_data['symbol']
                    token_info.metadata.name = token_mint_data['name']
                    token_info.metadata.image_uri = token_mint_data['logoURI']
                 
                    #token_info.metadata.image_uri = sol_mint_data['logoURI'] #may want to save the WSOL uri at some point
                    #token_info.metadata.symbol = sol_mint_data['symbol']
                    
                    return token_info
            except Exception as e:
                print(str(e))

    #Deprecated use of js; could be useful for some other apis not in python
    #def _execute_old(self, order: SwapOrder, max_tries = 3)->str:
    #    ray_js_file = globals.raydium_trade_api_path
    #    is_buy = "true" if order.order_type == TradeEventType.BUY else "false"
#
    #    amount_in = order.get_signer_amount(order.wallet_settings.get_default_signer())
    #    
    #    #FIXME Ray transaction: add argument to pass in wallet keys; js has og account hardcoded!
    #    swap_arguments = [
    #            "--outputMint", order.token_address, "--amount", str(amount_in.to_scaled()),
    #            "--slippage", str(order.swap_settings.slippage.to_scaled()), "--isBuy", is_buy
    #        ]
    #    
    #    result = jscript_runner.execute_js_file(ray_js_file, swap_arguments)
#
    #    if result:  
    #        return result['tx_id']