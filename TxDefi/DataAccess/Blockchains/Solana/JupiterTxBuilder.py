from solders.transaction import VersionedTransaction
from SolPubKey import SolPubKey
from SolanaRpcApi import SolanaRpcApi
import base64
import requests
import json
import SolanaUtilities as solana_utilities

from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from SolanaTxBuilder import SolanaTxBuilder

class JupiterTxBuilder(SolanaTxBuilder):
    def __init__(self, solana_rpc_api: SolanaRpcApi, payer_keys: str):
        SolanaTxBuilder.__init__(self, solana_rpc_api, payer_keys)

    def build_transaction(self, order: SwapOrder, signer: SolPubKey)->VersionedTransaction:
        if order.order_type == TradeEventType.BUY:
            in_token_address = solana_utilities.WRAPPED_SOL_MINT_ADDRESS
            out_token_address = order.token_address
        else:
            in_token_address = order.token_address 
            out_token_address = solana_utilities.WRAPPED_SOL_MINT_ADDRESS

        swap_transaction = self.get_swap_transaction(self.signer_pubkey, in_token_address, out_token_address, order.amount.ToScaledValue(), 
                                                     order.slippage.ToScaledValue(), order.priority_fee.ToScaledValue())

        if swap_transaction:
            raw_bytes = base64.b64decode(swap_transaction)
            raw_tx = VersionedTransaction.from_bytes(raw_bytes)

            return VersionedTransaction(raw_tx.message, [signer.get_key_pair()])

    @staticmethod
    def get_swap_transaction(signer_pubkey: str, in_token_address: str, out_token_address: str, amount: int, slippage: int, priority_fee: int):
        quote_jup_uri = 'https://quote-api.jup.ag/v6/quote?inputMint=' + in_token_address + '&outputMint=' + \
                    out_token_address + "&amount=" + str(amount) + "&slippageBps=" + str(slippage)
        
        response = requests.get(quote_jup_uri)

        if response and response.status_code == 200:
            quote = response.json()
            swap_jup_uri = 'https://quote-api.jup.ag/v6/swap'

            headers = {'Content-Type': 'application/json'}

            body = {
                "quoteResponse": quote,
                "userPublicKey": signer_pubkey,
                "wrapAndUnwrapSol": True,
                "prioritizationFeeLamports": priority_fee
                # Uncomment and modify the following line if you have a fee account
                # "feeAccount": "fee_account_public_key"            
            }
            json_data = json.dumps(body)
            response = requests.post(swap_jup_uri, headers=headers, data=json_data)    

            if response:
                json_response = response.json()

                return json_response['swapTransaction']
            