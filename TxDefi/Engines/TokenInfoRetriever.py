from typing import TypeVar, Generic
import base64
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.DataAccess.Decoders.TransactionsDecoder import TransactionsDecoder
from TxDefi.DataAccess.Blockchains.Solana.RaydiumTxBuilder import RaydiumTxBuilder
from TxDefi.DataAccess.Decoders.PumpDataDecoder import PumpDataDecoder, BondimgCurveData
from TxDefi.Data.MarketDTOs import *
from TxDefi.Data.TradingDTOs import *
import TxDefi.DataAccess.Blockchains.Solana.SolanaUtilities as solana_utilities
import TxDefi.Utilities.DEX.DexscreenerApi as dexscreener
import TxDefi.Utilities.HttpUtils as http_utils
import TxDefi.Utilities.MetaplexUtility as metaplex_util
import TxDefi.Data.Globals as globals

T = TypeVar("T", bound=InstructionData)  # Generic type Key Pair Type

class TokenInfoRetriever:
    def __init__(self, solana_rpc_api: SolanaRpcApi, pump_decoder: PumpDataDecoder, transaction_decoder: TransactionsDecoder, use_backup_rpc = False):
        self.solana_rpc_api = solana_rpc_api
        self.pump_decoder = pump_decoder
        self.transaction_decoder = transaction_decoder
        self.use_backup_rpc = use_backup_rpc
    
    @staticmethod
    def fetch_and_fill_inner_metadata(metadata: ExtendedMetadata, inner_uri: str)->bool:
        inner_asset_data = http_utils.get_request(inner_uri, timeout=1)

        if inner_asset_data:              
            metadata.description = inner_asset_data.get('description', '')

            metadata.image_uri = inner_asset_data.get('image', '')
            if 'twitter' not in inner_asset_data:
                dex_metadata = dexscreener.get_metadata(metadata.token_address)

                if dex_metadata:
                    metadata.socials = dex_metadata.socials
                    metadata.banner_url = dex_metadata.banner_url
                    metadata.open_graph_url = dex_metadata.open_graph_url
            else:
                metadata.socials.update('telegram', inner_asset_data.get('telegram', ''))
                metadata.socials.update('twitter', inner_asset_data.get('twitter', ''))
                metadata.socials.update('website', inner_asset_data.get('website', '')) 
        
            metadata.created_on = inner_asset_data.get('createdOn', globals.default_screener_uri) + "/" + metadata.token_address

        return inner_asset_data is not None

    #Most complete metadata; some metadata won't get filled out from the transactions themselves; use this to get everything possible
    #just can't get vault information
    def get_complete_metadata_from_account_info(self, token_address: str)->ExtendedMetadata:
        #if token_address in self.tokens_metadata:
        #    return self.tokens_metadata[token_address]
 
        try:
            asset_data = self.solana_rpc_api.get_account_info(token_address, 3)

            if asset_data:
                has_token_supply_info = False                
                value = asset_data.get('value')       

                if value:   
                    token_info_dict = value.get('data', {}).get('parsed', {}).get('info')

                    if token_info_dict:
                        has_token_supply_info = True
                        supply = int(token_info_dict.get('supply', 0))
                        decimals = token_info_dict.get('decimals')    
                        supply_amount = Amount.tokens_scaled(supply, decimals)  
                    else: #Have to query it (this should be rare)
                        supply_amount = self.solana_rpc_api.get_token_supply_Amount(token_address, 3)

                    token_program_address = value.get('owner')  
                    if has_token_supply_info:
                        #Just reuse what's in our records if available
                        ext_metadata = ExtendedMetadata(token_address)
                        ext_metadata.freeze_authority = token_info_dict.get('freezeAuthority')
                        ext_metadata.mint_authority = token_info_dict.get('mintAuthority')
                        ext_metadata.token_program_address = token_program_address 
                        ext_metadata.token_decimals = decimals  
                        ext_metadata.supply = supply_amount
                        #ext_metadata.is_mutable = asset_data.get('mutable') #unavailable; helius has these with getAsset
                        #ext_metadata.is_burnt = asset_data.get('burnt')
                        #ownership = ext_metadata.is_frozen = asset_data.get('ownership', {})
                        #ext_metadata.is_frozen = ownership.get('frozen')
                        #ext_metadata.is_delegated = ownership.get('delegated', False)
                        #ext_metadata.royalty = asset_data.get('royalty', {}).get('percent')    
                                    
                        #metadata = asset_data.get('content', {}).get('metadata', {})
                        #ext_metadata.name = metadata.get('name', '')
                        #ext_metadata.symbol = metadata.get('symbol', '')
        
                        #inner_uri = asset_data.get('content', {}).get('json_uri', '')  
                        #ext_metadata.inner_metadata_uri = inner_uri

                        #if len(inner_uri) > 0:
                        #    self.fill_inner_metadata(ext_metadata, inner_uri)
                        
                        #getLargestAccounts issue: Retrieval fails if we do it too soon
                        #token_info = self.get_token_info(token_address)

                        token_info = self.get_token_info(token_address)
        
                        if token_info: #Keep our vault addresses populated if possible
                            ext_metadata.sol_vault_address = token_info.metadata.sol_vault_address
                            ext_metadata.token_vault_address = token_info.metadata.token_vault_address
                        
                        return ext_metadata
                    else:
                        print("TokenInfoRetriever: Can't process " + token_address + ". Check your RPC Node.")
        except Exception as e:
            print("TokenInfoRetriever: Error retrieving token metadata " + str(e))

    def get_complete_metadata(self, token_address: str)->ExtendedMetadata: 
        try:            
            token_pda_address = metaplex_util.get_metadata_pda(token_address)
            account_info = self.solana_rpc_api.get_account_info(token_pda_address) #FYI getAsset by Helius seems to be faster than this; may revert back if this causes issues; Should only effect the display

            if account_info and account_info.get('value') is not None:
                decoded_data = base64.b64decode(account_info['value']['data'][0])
                asset_metadata = metaplex_util.parse_metaplex_data(decoded_data)

                if asset_metadata:
                    has_token_supply_info = False                
                    token_info_dict = asset_metadata.get('token_info')

                    if token_info_dict:
                        has_token_supply_info = True
                        supply = token_info_dict.get('supply', 0)
                        decimals = token_info_dict.get('decimals')
                        
                        supply_amount = Amount.tokens_scaled(supply, decimals)
                        token_program_address = token_info_dict.get('token_program')  
                    else: #Have to query it (this should be rare)
                        supply_amount = self.solana_rpc_api.get_token_supply_Amount(token_address, 3)

                        if supply_amount:
                            has_token_supply_info = True
                            token_program_address = solana_utilites.TOKEN_PROGRAM_ADDRESS #FIXME Big assumption; won't be able to swap token if this is wrong (need some robust code down the road)
                    
                    if has_token_supply_info:
                        #Just reuse what's in our records if available
                        ext_metadata = ExtendedMetadata(token_address)
                        ext_metadata.token_program_address = token_program_address 
                        ext_metadata.token_decimals = supply_amount.decimals  
                        ext_metadata.supply = supply_amount
                        ext_metadata.is_mutable = asset_metadata.get('mutable')
                        ext_metadata.name = asset_metadata.get('name', '')
                        ext_metadata.symbol = asset_metadata.get('symbol', '')

                        creators = asset_metadata.get('creators')

                        if creators and len(creators) > 0:
                            ext_metadata.creator_address = creators[0].get('address', '')

                        ext_metadata.inner_metadata_uri = asset_metadata.get('uri')

                        if len(ext_metadata.inner_metadata_uri) > 0:
                            self.fetch_and_fill_inner_metadata(ext_metadata, ext_metadata.inner_metadata_uri)
                        
                        return ext_metadata
                    else:
                        print("TokenInfoRetriever: Can't process " + token_address + ". Check your RPC Node.")
        except Exception as e:
            print("TokenInfoRetriever: Error retrieving token metadata " + str(e))

    def parse_account_data(self, account_info: dict)->InstructionData:
        value = account_info.get("value",{})
        owner = account_info.get("value",{}).get("owner")

        if owner and owner in self.supported_programs.keys():                
            return self.supported_programs[owner].decode(value)
        
    def update_token_vaults(self, token_info: TokenInfo):
        if len(token_info.metadata.sol_vault_address) > 0 and len(token_info.metadata.token_vault_address) > 0: 
            account_info = self.solana_rpc_api.get_account_info(token_info.metadata.sol_vault_address, 3)
  
            if account_info and account_info.get("value") is not None:
                value = account_info.get("value")
                owner = value.get("owner")

                if owner and owner == self.pump_decoder.program_address:  #Pump        
                    instruction_data = self.pump_decoder.decode(value)
                
                    if isinstance(instruction_data, BondimgCurveData):
                        token_info.metadata.program_type = SupportedPrograms.PUMPFUN
                        sol_vault_scaled_amount = instruction_data.virtual_sol_reserves
                        token_vault_scaled_amount = instruction_data.virtual_token_reserves

                        token_info.metadata.supply.set_amount2(instruction_data.token_total_supply , Value_Type.SCALED) 
                else: #Ray
                    sol_vault_scaled_amount = self.solana_rpc_api.get_account_balance(token_info.metadata.sol_vault_address, 3)
                    token_vault_scaled_amount = self.solana_rpc_api.get_token_account_balance(token_info.metadata.token_vault_address, 3).to_scaled() #Try a few times as this token may be new

                if sol_vault_scaled_amount and token_vault_scaled_amount:
                    token_info.sol_vault_amount.set_amount2(sol_vault_scaled_amount, Value_Type.SCALED)
                    token_info.token_vault_amount.set_amount2(token_vault_scaled_amount, Value_Type.SCALED)

    def get_token_info(self, token_address: str, is_token_bonding = False)->TokenInfo:
        try:
            #Check Raydium API first
            ret_token_info = RaydiumTxBuilder.get_token_info(token_address)

            if ret_token_info:
                #Need to populate vault reserves since the API doesn't give this to us
                ret_token_info.sol_vault_amount = self.solana_rpc_api.get_account_balance_Amount(ret_token_info.metadata.sol_vault_address)
                ret_token_info.token_vault_amount = self.solana_rpc_api.get_token_account_balance(ret_token_info.metadata.token_vault_address)
       
                return ret_token_info
            else: #Check if it's a Pumpfun Address (Add in other AMM support as needed)
                #TODO Revisit, getting data from market address may be more efficient
                top_accounts = self.solana_rpc_api.get_token_largest_accounts(token_address, 5)

                for token_account in top_accounts:                    
                    token_vault_owner = self.solana_rpc_api.get_spl_account_owner(token_account.account_address)
                    
                    if token_vault_owner == RaydiumTxBuilder.RAYDIUM_AUTHORITY_V4_ADDRESS:                        
                        ret_token_info = TokenInfo(token_address, token_account.balance.decimals)
                        ret_token_info.metadata.program_type = SupportedPrograms.RAYDIUMLEGACY
                        
                        signatures = self.solana_rpc_api.get_signatures_for_address(token_account.account_address, 0, 10)

                        if signatures:                   
                            #Get SOL Reserves now
                            for signature_obj in signatures: #Walk through until we find a swap transaction
                                signature = signature_obj['signature']
                                transaction = self.solana_rpc_api.get_transaction(signature, 3)

                                if transaction:
                                    owner_token_accounts = self.solana_rpc_api.parse_token_accounts(token_vault_owner, transaction)
                        
                                    if owner_token_accounts:
                                        for owner_token_account in owner_token_accounts:                                                             
                                            if owner_token_account.metadata.token_address == solana_utilites.WRAPPED_SOL_MINT_ADDRESS:                                       
                                                ret_token_info.metadata.sol_vault_address = owner_token_account.metadata.token_vault_address #WSOL                                     
                                                ret_token_info.sol_vault_amount = owner_token_account.token_vault_amount
                                                break
                                            
                                        ret_token_info.token_vault_amount = token_account.balance
                                        ret_token_info.metadata.supply = self.solana_rpc_api.get_token_supply_Amount(token_address)
                                        ret_token_info.metadata.token_vault_address = token_account.account_address    
                                        
                                        return ret_token_info
                    elif not is_token_bonding: #Last resort, expensive so caller should thread this (Pump)      
                        account_info = self.solana_rpc_api.get_account_info(token_vault_owner)
                        value = account_info.get('value', {})
                        owner = value.get('owner', "")
                        data_decoder = self.transaction_decoder.get_instructions_decoder(owner)
             
                        if data_decoder:
                            ret_token_info = None
                            program = None
                            decoded_data = data_decoder.decode(value)

                            if decoded_data:
                                if isinstance(decoded_data, BondimgCurveData):                             
                                    sol_reserves =  Amount.sol_scaled(decoded_data.virtual_sol_reserves)
                                    token_reserves =  Amount.tokens_scaled(decoded_data.virtual_token_reserves, 6)
                                    supply = decoded_data.token_total_supply
                                    sol_vault_account = token_vault_owner
                                    program = SupportedPrograms.PUMPFUN                                
                                elif isinstance(decoded_data, LiquidityPoolData):
                                    sol_reserves = self.solana_rpc_api.get_token_account_balance(decoded_data.pool_quote_address, 3)
                                    token_reserves = self.solana_rpc_api.get_token_account_balance(decoded_data.pool_base_address, 3)
                                    supply = decoded_data.total_supply  #TODO may need to pull this later
                                    sol_vault_account = decoded_data.pool_quote_address
                                    program = SupportedPrograms.PUMPFUN_AMM   

                                if program:
                                    ret_token_info = TokenInfo.create(program, token_address, sol_vault_account, token_account.account_address,
                                                                    sol_reserves, token_reserves, token_reserves.decimals)
                                    ret_token_info.metadata.market_id = token_vault_owner
                                    ret_token_info.metadata.supply.set_amount2(supply, Value_Type.SCALED)
                                    ret_token_info.metadata.token_program_address = solana_utilites.TOKEN_PROGRAM_ADDRESS
                                    
                                    if len(ret_token_info.metadata.inner_metadata_uri) == 0:
                                        complete_metadata = self.get_complete_metadata(token_address)
                                        ret_token_info.copy_missing_metadata(complete_metadata)

                                    return ret_token_info
        except Exception as e:
            print("TokenInfoRetriever: Issue retrieving token info for " + token_address)           

    def get_transaction_from_tx(self, tx_signature: str):
        transaction_dict = self.solana_rpc_api.get_transaction(tx_signature, 3)

        if transaction_dict:
            return self.transaction_decoder.decode(transaction_dict)
        
    def extract_token_infos(self, parsed_transaction: ParsedTransaction)->list[TokenInfo]:               
        ret_token_infos : list[TokenInfo]= []
        
        if parsed_transaction:            
            for instruction in parsed_transaction.instructions:
                token_info = None
                program = instruction.data.program_type

                if isinstance(instruction.data, LiquidityPoolData):                   
                    pool1_vault_account = instruction.data.pool_base_address
                    pool2_vault_account = instruction.data.pool_quote_address
        
                    pool1_info = parsed_transaction.get_pool_info(pool1_vault_account)
                    pool2_info = parsed_transaction.get_pool_info(pool2_vault_account)
                    pool1_mint_address = pool1_info.get('mint')
                    pool2_mint_address = pool2_info.get('mint')

                    if pool1_mint_address == solana_utilites.WRAPPED_SOL_MINT_ADDRESS:
                        sol_pool = pool1_info
                        token_pool = pool2_info
                        
                        sol_vault_address = pool1_vault_account
                        token_vault_address = pool2_vault_account 
                        token_address = pool2_mint_address                  
                    else:
                        sol_pool = pool2_info
                        token_pool = pool1_info
                        #Pools are swapped, so need to read the other vault
                        sol_vault_address = pool2_vault_account
                        token_vault_address = pool1_vault_account
                        token_address = pool1_mint_address
                    
                    sol_pool_amount = sol_pool.get('uiTokenAmount')
                    token_pool_amount = token_pool.get('uiTokenAmount')                
                
                    if sol_pool_amount and token_pool_amount:
                        sol_amount = Amount.sol_ui(sol_pool_amount.get("uiAmount", 0))
                        token_decimals = token_pool_amount.get('decimals', 0)
                        token_amount = Amount.tokens_ui(token_pool_amount.get("uiAmount", 0), token_decimals)
                        token_info = TokenInfo.create(program, token_address, sol_vault_address,
                                                        token_vault_address, sol_amount, token_amount, 
                                                        token_decimals)
                        
                        token_info.metadata.market_id = instruction.data.market_address #Thrown in for Pump AMM

                elif isinstance(instruction.data, ExtendedMetadata): #Pump Token
                    #program = SupportedPrograms.PUMPFUN DELETE
                    #Raw vault values don't mean anything due to pumpfun's virtual reserves; must get this onchain
                    sol_amount = Amount.sol_scaled(parsed_transaction.get_sol_balance(instruction.data.sol_vault_address))
                    token_pool_info = parsed_transaction.get_pool_info(instruction.data.token_vault_address)
                    token_pool_amount = token_pool_info.get('uiTokenAmount')                
                
                    if sol_amount and token_pool_amount:
                        token_decimals = token_pool_amount.get('decimals', 0)
                        token_amount = Amount.tokens_ui(token_pool_amount.get("uiAmount", 0), token_decimals)
                        token_info = TokenInfo.create(program, instruction.data.token_address, instruction.data.sol_vault_address,
                                                                        instruction.data.token_vault_address, sol_amount, token_amount, 
                                                                        token_decimals)
                        token_info.metadata.market_id = instruction.data.market_id
                elif isinstance(instruction.data, SwapData) and instruction.data.program_type == SupportedPrograms.PUMPFUN:
                    accounts = instruction.accounts #TODO shouldn't be doing this here
                    token_address = accounts[2]
                    sol_vault_address = accounts[3]
                    token_vault_address = accounts[4]
                    token_info = TokenInfo.create(program, token_address, sol_vault_address, token_vault_address, 
                                                  Amount.sol_scaled(0), Amount.tokens_ui(0, 6), 6)

                if token_info:
                    ret_token_infos.append(token_info)

        return ret_token_infos                                 
                             
    #Create a default token info against SOL Quotes
    @staticmethod
    def create_token_info(token_address: str, token_decimals: int)->TokenInfo:
        ret_val = TokenInfo(token_address, token_decimals)
        ret_val.metadata.quoted_currency_address = solana_utilities.WRAPPED_SOL_MINT_ADDRESS
        ret_val.metadata.token_decimals = token_decimals

        return ret_val