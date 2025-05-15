import requests
import base58
import time
from jsonrpcclient import request, parse, Ok, Error
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed, Processed, Finalized
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.instruction import Instruction, AccountMeta
from solders.transaction import VersionedTransaction
from solders.system_program import TransferParams, transfer
from solana.rpc.async_api import AsyncClient
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from TxDefi.Data.Amount import Amount
from TxDefi.Data.MarketDTOs import TokenInfo
from TxDefi.Data.TransactionInfo import SwapTransactionInfo, AccountInfo
from TxDefi.Utilities.RateLimiter import RateLimiter
import SolanaUtilities as solana_utilites

class SolanaRpcApi(RateLimiter):
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(max_retries=retry)

    def __init__(self, rpc_uri: str, wss_uri: str, rate_limit: int, rpc_backup_uri: str = None):
        RateLimiter.__init__(self, rate_limit)
        self.rpc_uri = rpc_uri
        self.rpc_backup_uri = rpc_backup_uri #Needed for getAsset (Quicknode and Helius provides this)
        self.wss_uri = wss_uri
        self.async_client = AsyncClient(self.rpc_uri)
        self.client = Client(self.rpc_uri)   
        self.last_block_hash = None           
        self.session = requests.Session()
        self.session.mount(self.rpc_uri, self.adapter)

    def run_rpc_method(self, request_name: str, params: list, max_tries = 1, use_backup = False):
        try:            
            for i in range(max_tries):
                if self.acquire_sem():
                    #print("Request: " + request_name)
                    json_request = request(request_name, params=params)

                    if use_backup and self.rpc_backup_uri:
                        response = requests.post(self.rpc_backup_uri, json=json_request)
                    else:
                        response = requests.post(self.rpc_uri, json=json_request)

                    parsed = parse(response.json())

                    if isinstance(parsed, Error):
                        pass
                    else:
                        return parsed
        
                    time.sleep(.2) #Limit to 5 calls per second
        except Exception as e:
            print(f"SolanaRpcApi: Failure on request {request_name}. Check your RPC Node. Error: {e}.")

    def get_transaction(self, tx_signature: str, max_tries = 1)->dict[str, any]:
        response = self.run_rpc_method("getTransaction", [tx_signature,
                                        {'encoding': 'jsonParsed', 'commitment': 'confirmed', 'maxSupportedTransactionVersion':0 }], max_tries)
        
        if response:
            return response.result
    
    def get_tx_signature_at_slot(self, slot: int, account_address: str)->str:
        transactions = self.get_signatures_for_address(account_address, slot, 1) #Archival call; could eliminate if not utilized elsewhere

        if transactions and len(transactions) > 0:
            return transactions[0]['signature']
        
    def get_transaction_at_slot(self, slot: int, account_address: str, max_tries = 1)->str:
        signature = self.get_tx_signature_at_slot(slot, account_address) #Archival call; could eliminate if not utilized elsewhere

        if signature:
            return self.get_transaction(signature, max_tries)

    def get_account_balance(self, account_address: str, max_tries=1)->float:
        response = self.run_rpc_method("getBalance", [ account_address ], max_tries)
        
        if response:
            return response.result['value']
        else:
            return None

    def get_signatures_for_address(self, contract_address: str, min_slot: int, limit = 1):
        response = self.run_rpc_method("getSignaturesForAddress", [contract_address,
                                                                   {'commitment': 'confirmed', 'minContextSlot': min_slot, 'limit': limit}])
                                                                    
        if response:
            return response.result
        else:
            return None
        
    def get_token_account_balance(self, associated_token_address: str, max_tries=1)->Amount:
        response = self.run_rpc_method("getTokenAccountBalance", [ associated_token_address ], max_tries),
        
        if response and len(response) > 0 and response[0]: #make sure it's not none
            ui_amount = response[0].result['value']['uiAmount']
            decimals = response[0].result['value']['decimals']
            
            return Amount.tokens_ui(ui_amount, decimals)
        else:
            return None
        
    def get_token_account_balance2(self, contract_address: str, owner_address: str, token_program_address: str, max_tries=1)->Amount:
        token_account_address = self.get_associated_token_account_address(owner_address, contract_address, token_program_address)
        token_balance = self.get_token_account_balance(token_account_address, max_tries)

        if not token_balance:    
            token_balance = Amount.tokens_ui(0, 0)

        return token_balance
    
    def get_account_balance_Amount(self, contract_address: str, max_tries=1)->Amount:
        raw_amount = self.get_account_balance(contract_address, max_tries)

        if raw_amount is not None:
            return Amount.sol_scaled(raw_amount)
       
    #Get largest holders of a token; returns (token account address, token balance)
    def get_token_largest_accounts(self, mint_address: str, limit = 20)->list[AccountInfo]:
        response = self.run_rpc_method("getTokenLargestAccounts", [mint_address])
        holders = []
              
        if response:          
            count = 0
            token_accounts = response.result['value']
            for count in range(min(limit, len(token_accounts))):
                address = str(token_accounts[count]['address'])
                balance = token_accounts[count]['amount']
                decimals = token_accounts[count]['decimals']
                holders.append(AccountInfo(address, Amount.tokens_scaled(int(balance), decimals)))

        return holders

    def get_token_accounts_by_owner(self, wallet_address: str)->list[AccountInfo]:
        response = self.run_rpc_method("getTokenAccountsByOwner", [wallet_address, {'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},
                                                                     {'encoding': 'jsonParsed'}])
        ret_accounts = []
              
        if response:          
            token_accounts = response.result['value']

            for account in token_accounts:
                token_address = str(account['pubkey'])
                mint_Address = account['account']['data']['parsed']['info']['mint']
                balance = account['account']['data']['parsed']['info']['tokenAmount']['uiAmount']
                decimals = account['account']['data']['parsed']['info']['tokenAmount']['decimals']
          
                ret_accounts.append(AccountInfo(token_address, Amount.tokens_ui(balance, decimals), mint_Address))

        return ret_accounts
    
    def get_token_account_by_owner(self, mint_address: str, owner_address: str)->AccountInfo:
        token_accounts = self.get_token_largest_accounts(mint_address)
        
        for token_account in token_accounts:
            token_owner_address = self.get_spl_account_owner(token_account.account_address)

            if token_owner_address == owner_address:
                return token_account
            
    #Get top holding amount from top holders not including the liquidity pool accounts (i.e pumpfun or raydium)
    def get_top_owners_total_holding(self, mint_address, number_accounts: int, exclude_owners: list[str], is_spl_token: bool)->int:  
        num_exclusions = 0 if not exclude_owners else len(exclude_owners)
        token_accounts = self.get_token_largest_accounts(mint_address, number_accounts+num_exclusions)
        num_accounts_processed = 0
        total_tokens_held = 0
      
        for token_account in token_accounts:
            should_exclude = False
            #Don't include the pool owner tokens account into the calculation
            if num_accounts_processed < number_accounts:
                if num_exclusions > 0:
                    if is_spl_token:
                        token_owner_address = self.get_spl_account_owner(token_account.account_address)
                        account_owner_address = self.get_spl_account_owner(token_owner_address)
                    else:
                        token_owner_address = self.get_account_owner(token_account.account_address)
                        account_owner_address = solana_utilites.SYSVAR_SYSTEM_PROGRAM_ID
                    
                    should_exclude = account_owner_address in exclude_owners
            
            if not should_exclude:
                total_tokens_held += token_account.balance.to_scaled()
                num_accounts_processed += 1

        return total_tokens_held   

    def get_block(self, slot: int):
        response = self.run_rpc_method("getBlock", [
                    slot,
                    {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion":0,
                        "transactionDetails":"full",
                        "rewards":False
                    }
                ])

        if response:
            return response.result

        print("getBlock: Couldn't get asset")

    def get_account_owner(self, address: str, max_tries=1)->str:
        account_info = self.get_account_info(address, max_tries)
        
        if account_info:
            return account_info.get('value', {}).get('owner')
        
    def get_spl_account_owner(self, address: str, max_tries=1)->str:
        account_info = self.get_account_info_parsed(address, max_tries)
        
        if account_info:
            return account_info.get('owner')

    def get_account_spl_token_address(self, address: str, max_tries=1)->str:
        account_info = self.get_account_info(address, max_tries)

        if account_info:
            return account_info.get('mint')
        
    def get_account_info_parsed(self, address: str, max_tries=1)->dict:
        account_info = self.get_account_info(address, max_tries)

        if account_info:
            return account_info.get('value', {}).get('data', {}).get('parsed', {}).get('info')
    
    def get_account_info(self, address: str, max_tries=1)->dict:
        response = self.run_rpc_method("getAccountInfo", [address, {"encoding": "jsonParsed"}],  max_tries) #FIXME doesn't work with all rpcs

        if response:
            return response.result

        print("get_account_info: Couldn't get asset")
         
    def get_asset(self, address: str, max_tries=1, use_backup = False):
        response = self.run_rpc_method("getAsset", [address], max_tries, use_backup)

        if response:
            return response.result
        
    def get_token_supply(self, address: str, max_tries=1)->dict:
        response = self.run_rpc_method("getTokenSupply", [address], max_tries)

        if response:
            return response.result

    def get_token_supply_Amount(self, address: str, max_tries=1)->Amount:
        supply_dict = self.get_token_supply(address, max_tries)

        if supply_dict:
            supply = supply_dict.get('value', {}).get('uiAmount', 0)                    
            decimals = supply_dict.get('value', {}).get('decimals', 1)
               
            return Amount.tokens_ui(supply, decimals)

    def get_priority_fee_estimate(self, program_address: str):
        response = self.run_rpc_method("getPriorityFeeEstimate", [ {'accountKeys': [program_address]},
                                                                 {'options': {'recommended': True}} ])
        if response and len(response.result) > 0 :
            return response.result['priorityFeeEstimate']
        else:
            return 1e5 #default of 100K
    
    def get_recent_priority_fees(self, account_address: str):
        response = self.run_rpc_method("getRecentPrioritizationFees", [ [account_address] ])

        if response and len(response.result) > 0 :
            sum = 0
            fees_count = 0

            for index in range(len(response.result)):
                fee = response.result[index]['prioritizationFee']

                if fee > 0: # Return most recent fee found
                    sum += fee
                    fees_count += 1

            return 0 if fees_count == 0 else sum/fees_count
        
        print("get_recent_priority_fees: No recent fee was found")

    def get_latest_block_hash(self):
        response = self.run_rpc_method("getLatestBlockhash", [ {'commitment': "confirmed"} ])

        if response:
            return response.result['value']['blockhash']

        print("get_latest_block_hash: Couldn't do it")

    def update_latest_block_hash(self)->Hash:
        block_hash_str = self.get_latest_block_hash()

        if block_hash_str:
            self.last_block_hash = Hash.from_string(block_hash_str)
            return self.last_block_hash
    
    def get_last_recorded_block_hash(self)->Hash:
        if not self.last_block_hash:
            self.update_latest_block_hash()
            
        return self.last_block_hash
    
    def send_transaction(self, transaction: VersionedTransaction, maxTries=0):
        transaction_bytes = bytes(transaction)

        import time
        #print("Sending tx: " + str(time.time_ns())) #DELETE THIS
        return self.client.send_raw_transaction(transaction_bytes, opts=TxOpts(skip_confirmation=True,
                                                                               skip_preflight = True,
                                                                            #preflight_commitment=Processed,
                                                                            max_retries=maxTries))
    
    @staticmethod  
    def create_transfer_instruction(sender: Pubkey, receiver: Pubkey, lamports: int):
        return transfer(
            TransferParams(
                from_pubkey=sender,
                to_pubkey=receiver,
                lamports=lamports
            )
        )    
    
    # Function to create Jito bundle
    @staticmethod
    def create_jito_bundle(transactions: list[VersionedTransaction]):
        
        bundle = [base58.b58encode(bytes(tx)).decode('utf-8') for tx in transactions]

        return bundle

    @staticmethod 
    def parse_token_info(account_info: dict)->TokenInfo: 
        token_info_dict = account_info.get("value", {}).get('data', {}).get('parsed', {}).get('info', {})
        mint_address = token_info_dict.get('mint')
      
        if mint_address:
            token_amount = token_info_dict.get('tokenAmount')
            token_decimals = token_amount.get('decimals')
            token_info = TokenInfo(mint_address, token_decimals) 
            token_info.token_vault_amount = Amount.tokens_ui(token_amount.get('uiAmount', 0), token_decimals)        
            token_info.metadata.owner_address = token_info_dict.get('owner')

            return token_info  

    @staticmethod #TODO untested
    def parse_token_accounts(owner_address: str, transaction_data: dict)->list[TokenInfo]:
        ret_list : list[TokenInfo] = []
        accounts = transaction_data['transaction']['message']['accountKeys']
        all_token_balances = transaction_data['meta']['postTokenBalances']
        token_balances = SolanaRpcApi.extract_token_balances(owner_address, all_token_balances)

        for mint_address in token_balances.keys():             
            token_balance = token_balances.get(mint_address)
            token_decimals = token_balance['uiTokenAmount']['decimals']
            token_account_index = token_balance['accountIndex']     
            
            token_info = TokenInfo(mint_address, token_decimals) #Create a partially filled out TokenInfo
            token_info.sol_vault_amount = 1    
            token_info.token_vault_amount = Amount.tokens_ui(token_balance['uiTokenAmount']['uiAmount'], token_decimals)
            token_info.metadata.token_vault_address = accounts[token_account_index]['pubkey']
            ret_list.append(token_info)
        
        return ret_list
    
    @staticmethod
    def parse_swap_transactions(owner_address: str, transaction_data: dict)->list[SwapTransactionInfo]:
        ret_swaps :  list[SwapTransactionInfo] = []
        accounts = transaction_data['transaction']['message']['accountKeys']
        num_accounts = len(accounts)
        owner_account_index = -1
        pre_sol_balances = transaction_data['meta']['preBalances']
        fee = transaction_data['meta']['fee']
        post_sol_balances = transaction_data['meta']['postBalances']
        pre_token_balances = transaction_data['meta']['preTokenBalances']
        post_token_balances = transaction_data['meta']['postTokenBalances']          
        tx_signature = transaction_data['transaction']['signatures'][0]  
        slot = transaction_data['slot']
        
        for i in range(num_accounts):
            if owner_address == accounts[i]['pubkey']:
                owner_account_index = i
                break
        
        if owner_account_index >= 0:
            pre_token_balances = SolanaRpcApi.extract_token_balances(owner_address, pre_token_balances)
            post_token_balances = SolanaRpcApi.extract_token_balances(owner_address, post_token_balances)
           
            for mint_address in post_token_balances.keys():             
                transaction_info = SwapTransactionInfo(tx_signature, slot)
                pre_token_balance = pre_token_balances.get(mint_address)
                post_token_balance = post_token_balances.get(mint_address)
                post_token_amount = post_token_balance['uiTokenAmount']['uiAmount']
                token_decimals = post_token_balance['uiTokenAmount']['decimals']
                token_account_index = post_token_balance['accountIndex']    
                
                if pre_token_balance and post_token_balance:
                    pre_token_amount = pre_token_balance['uiTokenAmount']['uiAmount'] 
                else:
                    pre_token_amount = 0
    
                transaction_info.token_address = post_token_balance['mint']
                transaction_info.fee = fee #Shared between transaction TODO put swap transactions into and aggregator class         
                transaction_info.payer_token_account_address = accounts[token_account_index]['pubkey']
                transaction_info.payer_token_ui_balance = post_token_amount
                transaction_info.sol_balance_change = post_sol_balances[owner_account_index]-pre_sol_balances[owner_account_index]
                transaction_info.token_decimals = token_decimals
                transaction_info.tx_signature = tx_signature
                transaction_info.payer_address = owner_address

                if pre_token_amount and post_token_amount:
                    transaction_info.token_balance_change = post_token_amount-pre_token_amount
                elif pre_token_amount:
                    transaction_info.token_balance_change = -pre_token_amount
                elif post_token_amount:
                    transaction_info.token_balance_change = post_token_amount
                else:
                    transaction_info.token_balance_change = 0

                ret_swaps.append(transaction_info)

            return ret_swaps

    @staticmethod
    def create_associated_token_account_instruction(payer: Pubkey, associated_token_address: Pubkey, owner: Pubkey, token_address: Pubkey):
        return Instruction(
        accounts=[
            AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
            AccountMeta(pubkey=associated_token_address, is_signer=False, is_writable=True),
            AccountMeta(pubkey=owner, is_signer=False, is_writable=False),
            AccountMeta(pubkey=token_address, is_signer=False, is_writable=False),
            AccountMeta(pubkey=solana_utilites.system_program_pk, is_signer=False, is_writable=False),
            AccountMeta(pubkey=solana_utilites.TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
        ],
        program_id=solana_utilites.ASSOCIATED_TOKEN_PROGRAM_ID,
        data=bytes(0),
        )

    @staticmethod
    def get_associated_token_account_address(owner_address: str, mintAddress: str, token_program_address: str)->str:
        mint_address_pk = Pubkey.from_string(mintAddress)        
        owner_address_pk = Pubkey.from_string(owner_address)
        token_program_pk = solana_utilites.solana_pubkeys.get(token_program_address) 

        if token_program_pk:
            # Calculate the associated token address
            #seeds = [bytes(owner_address_pk), bytes(TOKEN_PROGRAM_ID), bytes(mint_address_pk)] #DELETE
            seeds = [bytes(owner_address_pk), bytes(token_program_pk), bytes(mint_address_pk)]

            return str(Pubkey.find_program_address(seeds, solana_utilites.ASSOCIATED_TOKEN_PROGRAM_ID)[0])
          
    @staticmethod
    def extract_mint_decimals(mint_address: str, token_balance_dict: dict)->int:
        for token_balance in token_balance_dict:
            if mint_address == token_balance['mint']:      
                return token_balance['uiTokenAmount']['decimals']

    @staticmethod
    def extract_token_balances(owner_address: str, token_balance_dict: dict)->dict[str, dict]:
        ret_list: dict[str, dict] = {}
        
        for token_balance in token_balance_dict:
            if owner_address == token_balance['owner']:
                mint_address = token_balance['mint']
                ret_list[mint_address] = token_balance
        
        return ret_list

    @staticmethod
    def get_account_subscribe_request(account_address: str, id = 420):
         return {
                "jsonrpc": "2.0",
                "id": id,
                "method": "accountSubscribe",
                "params": [
                account_address, # pubkey of account we want to subscribe to
                {
                    "encoding": "jsonParsed", # base58, base64, base65+zstd, jsonParsed
                    "commitment": "confirmed", # defaults to finalized if unset
                }
            ]
        }           
    
    @staticmethod
    def get_block_request(slot: int):
         return {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBlock",
                "params": [
                    slot,
                    {
                        "encoding": "jsonParsed",
                        "maxSupportedTransactionVersion":0,
                        "transactionDetails":"full",
                        "rewards":False
                    }
                ]
        }  

    #Creates a transaction sub request
    @staticmethod
    def get_signature_request(signature: str):
        return  {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "signatureSubscribe",
                "params": [
                signature, # pubkey of account we want to subscribe to #TODO put in constructor
                {
                    "commitment": "confirmed",
                    "enableReceivedNotification": False
                }
            ]
        }   
    
    @staticmethod
    def get_geyser_transaction_sub_request(contract_ids: list[str]):
        return  {
                "jsonrpc": "2.0",
                "id": 420,
                "method": "transactionSubscribe",
                "params": [
                    {
                        "failed": False,
                        "accountInclude": contract_ids
                    },
                    {
                        "encoding": "jsonParsed", # base58, base64, base65+zstd, jsonParsed
                        "commitment": "confirmed", # defaults to finalized if unset
                        "transactionDetails": "full",
                        "showRewards": False,
                        "maxSupportedTransactionVersion": 0
                    }
                ]
        }
    
    @staticmethod
    def get_logs_sub_request(contract_ids: list[str]):
        return  {
                "jsonrpc": "2.0",
                "id": 420,
                "method": "logsSubscribe",
                "params": [{"mentions": contract_ids},
                           {"commitment": "confirmed"}] 
                        #{"commitment": "processed"}] #Defaults to finalized if unset; FIXME use confirmed only for faster reaction time; tx may fail though so need to batch the tx
        }