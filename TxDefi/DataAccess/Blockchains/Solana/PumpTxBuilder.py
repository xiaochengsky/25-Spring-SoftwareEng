from solders.transaction import VersionedTransaction
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from spl.token.constants import ASSOCIATED_TOKEN_PROGRAM_ID, TOKEN_PROGRAM_ID
import struct
from SolanaRpcApi import SolanaRpcApi
from SolanaTxBuilder import SolanaTxBuilder
from SolPubKey import SolPubKey
from JitoExecutor import JitoOrderExecutor
from TxDefi.Data.TradingDTOs import *
from TxDefi.Data.MarketDTOs import *
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager
import TxDefi.DataAccess.Blockchains.Solana.SolanaUtilities as solana_utilities
import TxDefi.Data.Globals as globals

class PumpTxBuilder(SolanaTxBuilder):
    buy_index = 0x66063D1201DAEBEA
    sell_index = 0x33E685A4017F83AD
    create_token_index = 0x181EC828051C0777
    total_minted_tokens = 1000000000*1e6
    max_tokens_witheld = 206900000*1e6
    PUMP_PROGRAM_ADDRESS = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    PUMP_FEE_ADDRESS = "62qc2CNXwrYqQScmEdiZFFAnJR262PxWEuNQtxfafNgV"     
    program_address_pk = Pubkey.from_string(PUMP_PROGRAM_ADDRESS)      
    fee_address_pk = Pubkey.from_string(PUMP_FEE_ADDRESS)    
    jito_tip_address_pk = Pubkey.from_string(JitoOrderExecutor.jito_tip_address)
    global_address_pk = Pubkey.from_string(solana_utilities.GLOBAL_ADDRESS)
    rent_address_pk = Pubkey.from_string(solana_utilities.SYSVAR_RENT)
    event_authority_pk = Pubkey.from_string(solana_utilities.EVENT_AUTHORITY)
    system_program_pk = Pubkey.from_string(solana_utilities.SYSVAR_SYSTEM_PROGRAM_ID)

    def __init__(self, market_manager: AbstractMarketManager, solana_rpc_api: SolanaRpcApi):
        SolanaTxBuilder.__init__(self, solana_rpc_api)
        self.market_manager = market_manager
        self.max_compute_limit = 80000 #TODO need to dynamically set this; more research required
        self.solana_rpc_api = solana_rpc_api  
        self.buyAccounts : list[AccountMeta]= []
        self.sellAccounts : list[AccountMeta] = []

        self._init_base_accounts()    
    
    def get_program_id(self):
        return str(self.program_address_pk)
                
    def _get_accounts(self, order_type: TradeEventType, signer: Pubkey, mint_address: Pubkey, bonding_curve_address: Pubkey, associated_bonding_curve_address: Pubkey,
                       user_associated_address: Pubkey):
        if order_type == TradeEventType.BUY:
            retAccounts = self.buyAccounts.copy()
        else:
            retAccounts = self.sellAccounts.copy()

        retAccounts[2] = AccountMeta(mint_address, False, False)
        retAccounts[3] = AccountMeta(bonding_curve_address, False, True)
        retAccounts[4] = AccountMeta(associated_bonding_curve_address, False, True)
        retAccounts[5] = AccountMeta(user_associated_address, False, True)
        retAccounts[6] = AccountMeta(signer, False, True)
        return retAccounts

    def _init_base_accounts(self):     
        self.buyAccounts = [
                AccountMeta(self.global_address_pk, False, False),
                AccountMeta(self.fee_address_pk, False, True),
                None, #mintAddressPk placeholder
                None, #bondingCurveAddressPk placeholder
                None, #associatedBondingCurveAddressPk placeholder
                None,#AssociatedUserTokenAddres placeholder
                None,#AccountMeta(self.signer_wallet.pubkey(), True, True), 
                AccountMeta(self.system_program_pk, False, False),  
                AccountMeta(TOKEN_PROGRAM_ID, False, False), 
                AccountMeta(self.rent_address_pk, False, False), 
                AccountMeta(self.event_authority_pk, False, False), 
                AccountMeta(self.program_address_pk, False, False)]
        
        self.sellAccounts = [
                AccountMeta(self.global_address_pk, False, False),
                AccountMeta(self.fee_address_pk, False, True),
                None, #mintAddressPk placeholder
                None, #bondingCurveAddressPk placeholder
                None, #associatedBondingCurveAddressPk placeholder
                None, #AssociatedUserTokenAddres placeholder
                None, #AccountMeta(self.signer_wallet.pubkey(), True, True), 
                AccountMeta(self.system_program_pk, False, False),  
                AccountMeta(ASSOCIATED_TOKEN_PROGRAM_ID, False, False), 
                AccountMeta(TOKEN_PROGRAM_ID, False, False), 
                AccountMeta(self.event_authority_pk, False, False), 
                AccountMeta(self.program_address_pk, False, False)]
    
    def build_transaction(self, order: SwapOrder, signer: SolPubKey)->VersionedTransaction:
        #token_metadata = self.market_manager.get_extended_metadata(order.token_address)
        import time
        #print("Building transaction " + str(time.time_ns())) #DELETE THIS 
        token_info = self.market_manager.get_token_info(order.token_address) #Only token info has vaults popupulated (Re-evaluate this)
       
        if token_info:
            instructions : list[Instruction]= []
            signer_pk = signer.get_key_pair().pubkey()
            associated_token_address = self.market_manager.get_associated_token_account(signer.get_account_address(), order.token_address)
            mint_address_pk = Pubkey.from_string(order.token_address)
            bonding_curve_address_pk = Pubkey.from_string(token_info.metadata.sol_vault_address)
            associated_bonding_curve_address_pk = Pubkey.from_string(token_info.metadata.token_vault_address)
            associated_user_account_pk = Pubkey.from_string(associated_token_address)
            slippage_percent = order.swap_settings.slippage.to_ui()/100

            if order.use_signer_amount:
                amount_in = order.get_signer_amount(signer)
            else:
                amount_in = order.swap_settings.amount
                
            #Get the fees #TODO move this code elsewhere
            #fee_estimate = int(self.solana_rpc_api.get_priority_fee_estimate(str(self.program_address_pk)))
            #if fee_estimate < 3e6:
            ##    fee_estimate = int(3e6) #clamp to 3e6
            compute_unit_limit = self.max_compute_limit
            
            if order.order_type == TradeEventType.BUY:
                max_percent = 1+slippage_percent 
                transaction_hex = self.buy_index   
                estimated_tokens = self.market_manager.get_estimated_tokens(order.token_address, amount_in)
                raw_token_quantity = estimated_tokens.to_scaled()
                sol_limit_lamports = amount_in.to_scaled()*max_percent #Add slippage

                token_account_info = self.market_manager.get_token_account_info(signer.get_account_address(), order.token_address)

                if token_account_info is None:  #create an associated account if it doesn't exist
                    #Create the associated user account so we have somewhere to put the tokens
                    assoc_user_account_instruction = SolanaRpcApi.create_associated_token_account_instruction(signer_pk, associated_user_account_pk,
                                                                                            signer_pk, mint_address_pk)
                    #spl_token.create_associated_token_account(self.payerKeys.pubkey(), self.payerKeys.pubkey(), mintAddressPk)

                    instructions.append(assoc_user_account_instruction)
                            
                    compute_unit_limit += 30000 #Add some compute units for this operation
            else: #SELL
                min_percent = 1-slippage_percent 
                transaction_hex = self.sell_index
    
                raw_token_quantity = amount_in.to_scaled()
                estimated_price = self.market_manager.get_estimated_price(order.token_address, amount_in)
                sol_limit_lamports = estimated_price.to_scaled()*min_percent #Add slippage

            priority_fee_limit = int(order.swap_settings.priority_fee.to_scaled()/compute_unit_limit*1e6)#microlamports
            instructions.append(set_compute_unit_limit(compute_unit_limit))
            instructions.append(set_compute_unit_price(priority_fee_limit))                                                               

            # Create a byte array to hold the data
            pump_instruction_data = bytearray(24)
            accounts = self._get_accounts(order.order_type, signer_pk, mint_address_pk, bonding_curve_address_pk, associated_bonding_curve_address_pk, associated_user_account_pk)

            # Pack the data into the byte array
            struct.pack_into('>Q', pump_instruction_data, 0, transaction_hex) #Big-endian 64-bit unsigned
            struct.pack_into('<Q', pump_instruction_data, 8, int(raw_token_quantity)) #Little-endian 64-bit unsigned
            struct.pack_into('<Q', pump_instruction_data, 16, int(sol_limit_lamports)) #Little-endian 64-bit unsigned        
    
            pump_instruction = Instruction(self.program_address_pk, bytes(pump_instruction_data), accounts)
            instructions.append(pump_instruction)

            #Add a tip instruction if tipping; Needs to be the last instruction so it doesn't get taken if bundle is forked
            if order.swap_settings.jito_tip and order.swap_settings.jito_tip.value > 0: #Need to abstract this code so other platforms can add the fee
                jito_tip_instruction = SolanaRpcApi.create_transfer_instruction(signer_pk, self.jito_tip_address_pk, order.swap_settings.jito_tip.to_scaled())
                instructions.append(jito_tip_instruction)
      
            return self.build_v0_transaction(instructions, signer)
    