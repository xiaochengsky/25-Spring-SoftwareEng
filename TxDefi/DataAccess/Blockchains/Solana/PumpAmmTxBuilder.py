from solders.transaction import VersionedTransaction
from solders.instruction import Instruction, AccountMeta
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from spl.token.instructions import transfer_checked, sync_native, close_account, CloseAccountParams, TransferCheckedParams, SyncNativeParams
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
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

class PumpAmmTxBuilder(SolanaTxBuilder):
    BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
    SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])
    PUMP_AMM_PROGRAM_ADDRESS = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
    PUMP_AMM_PROGRAM_PK = Pubkey.from_string(PUMP_AMM_PROGRAM_ADDRESS)
    GLOBAL_CONFIG_PK =  Pubkey.from_string("ADyA8hdefvWN2dbGGWFotbzWxrAvLW83WG6QCVXvJKqw")
    FEE_RECIPIENT_PK =  Pubkey.from_string("JCRGumoE9Qi5BBgULTgdgTLjSgkCMSbF62ZZfGs84JeU")
    FEE_RECIPIENT_TOKEN_ACC_PK =  Pubkey.from_string("DWpvfqzGWuVy9jVSKSShdM2733nrEsnnhsUStYbkj6Nn")
    EVENT_AUTHORITY_PK =  Pubkey.from_string("GS4CU59F31iL7aR2Q8zVS8DRrcRnXX1yjQ66TqNVQnaR")
        
    def __init__(self, market_manager: AbstractMarketManager, solana_rpc_api: SolanaRpcApi):
        SolanaTxBuilder.__init__(self, solana_rpc_api)
        self.market_manager = market_manager
        self.max_compute_limit = 80000 #TODO need to dynamically set this; more research required
        self.solana_rpc_api = solana_rpc_api        
        self.jito_tip_address_pk = Pubkey.from_string(JitoOrderExecutor.jito_tip_address)

        self.buy_sell_accounts : list[AccountMeta]= []
        self.sellAccounts : list[AccountMeta] = []

        self._init_base_accounts()    
    
    def get_program_id(self):
        return str(self.PUMP_AMM_PROGRAM_PK)
                
    def _get_accounts(self, order_type: TradeEventType, signer: Pubkey, mint_address: Pubkey, pool_wsol_token_associated_address: Pubkey, pool_token_associated_address: Pubkey,
                       user_token_associated_address: Pubkey, pool_address: Pubkey, user_wsol_token_associated_address: Pubkey):
        if order_type == TradeEventType.BUY:
            retAccounts = self.buy_sell_accounts.copy()
        else:
            retAccounts = self.buy_sell_accounts.copy() #See if there's a difference

        retAccounts[0] = AccountMeta(pool_address, False, False)
        retAccounts[1] = AccountMeta(signer, True, True)

        retAccounts[3] = AccountMeta(mint_address, False, False)
        retAccounts[4] = AccountMeta(solana_utilites.WRAPPED_SOL_MINT, False, False)
        retAccounts[5] = AccountMeta(user_token_associated_address, False, True)
        retAccounts[6] = AccountMeta(user_wsol_token_associated_address, False, True)
        retAccounts[7] = AccountMeta(pool_token_associated_address, False, True)
        retAccounts[8] = AccountMeta(pool_wsol_token_associated_address, False, True)

        return retAccounts

    def _init_base_accounts(self):     
        self.buy_sell_accounts = [
                None, #poolPk
                None, #AccountMeta(self.signer_wallet.pubkey(), True, True),
                AccountMeta(self.GLOBAL_CONFIG_PK, False, False),  
                None,  #base_mint
                None,  #quote_mint
                None,  #user_base_token_account
                None,  #user_quote_token_account
                None,  #pool_base_token_account
                None,  #pool_quote_token_account
                AccountMeta(self.FEE_RECIPIENT_PK, False, False), 
                AccountMeta(self.FEE_RECIPIENT_TOKEN_ACC_PK, False, True),
                AccountMeta(solana_utilites.TOKEN_PROGRAM_ID, False, False),                      
                AccountMeta(solana_utilites.TOKEN_PROGRAM_ID, False, False), 
                AccountMeta(solana_utilites.system_program_pk, False, False),
                AccountMeta(solana_utilites.ASSOCIATED_TOKEN_PROGRAM_ID, False, False),
                AccountMeta(self.EVENT_AUTHORITY_PK, False, False), 
                AccountMeta(self.PUMP_AMM_PROGRAM_PK, False, False)
        ]
        
    def build_transaction(self, order: SwapOrder, signer: SolPubKey)->VersionedTransaction:
        #token_metadata = self.market_manager.get_extended_metadata(order.token_address)
        import time
        #print("Building transaction " + str(time.time_ns())) #DELETE THIS 
        token_info = self.market_manager.get_token_info(order.token_address) #Only token info has vaults popupulated (Re-evaluate this)
       
        if token_info:
            instructions : list[Instruction]= []
            signer_pk = signer.get_key_pair().pubkey()
            pool_address = Pubkey.from_string(token_info.metadata.market_id)
            associated_token_account_pk = Pubkey.from_string(self.market_manager.get_associated_token_account(signer.get_account_address(), order.token_address))
            associated_wsol_account_pk = Pubkey.from_string(self.market_manager.get_associated_token_account(signer.get_account_address(), solana_utilites.WRAPPED_SOL_MINT_ADDRESS))
            mint_address_pk = Pubkey.from_string(order.token_address)
            pool_quote_address_pk = Pubkey.from_string(token_info.metadata.sol_vault_address)
            pool_base_address_pk = Pubkey.from_string(token_info.metadata.token_vault_address)
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

            user_wsol_account_info = self.market_manager.get_token_account_info(signer.get_account_address(), solana_utilites.WRAPPED_SOL_MINT_ADDRESS)
            ix_wrap_sol = None                        
            create_account_instruction1 = None
            create_account_instruction2 = None
            
            #TODO Abstract out common to share with Pumpfun Tx Builder
            if order.order_type == TradeEventType.BUY:
                max_percent = 1+slippage_percent 
                discriminator_bytes = self.BUY_DISCRIMINATOR   
  
                estimated_tokens = self.market_manager.get_estimated_tokens(order.token_address, amount_in)

                raw_token_quantity = estimated_tokens.to_scaled()
                sol_limit_lamports = int(amount_in.to_scaled()*max_percent) #Add slippage
                user_token_account_info = self.market_manager.get_token_account_info(signer.get_account_address(), order.token_address)

                #Create the associated user account so we have somewhere to put the tokens
                if user_token_account_info is None:  #create an associated account if it doesn't exist 
                    create_account_instruction1 = SolanaRpcApi.create_associated_token_account_instruction(signer_pk, associated_token_account_pk,
                                                                                            signer_pk, mint_address_pk)                        
                    compute_unit_limit += 30000 #Add some compute units for this operation
                            
                transfer_amt = int(sol_limit_lamports + .01*1e9)
                ix_wrap_sol = transfer(
                    TransferParams(
                        from_pubkey=signer_pk, to_pubkey=associated_wsol_account_pk, lamports=transfer_amt
                    )
                )

                #x_wrap_sol = transfer_checked(                        
                #       TransferCheckedParams
                #       (                        
                #           program_id=solana_utilites.TOKEN_PROGRAM_ID,
                #           source=associated_wsol_account_pk,
                #           mint=solana_utilites.WRAPPED_SOL_MINT,
                #           dest=associated_wsol_account_pk,
                #           owner=signer_pk,
                #           amount=sol_limit_lamports,
                #           decimals=9,
                #       )
                #   )
            else: #SELL
                min_percent = 1-slippage_percent 
                discriminator_bytes = self.SELL_DISCRIMINATOR
    
                raw_token_quantity = amount_in.to_scaled()
                estimated_price = self.market_manager.get_estimated_price(order.token_address, amount_in)
                sol_limit_lamports = int(estimated_price.to_scaled()*min_percent) #Add slippage

            if not user_wsol_account_info: #Need a WSOL account
                create_account_instruction2 = SolanaRpcApi.create_associated_token_account_instruction(signer_pk, associated_wsol_account_pk,
                                                                                        signer_pk, solana_utilites.WRAPPED_SOL_MINT)                           
                compute_unit_limit += 30000 #Add some compute units for this operation
                    
            priority_fee_limit = int(order.swap_settings.priority_fee.to_scaled()/compute_unit_limit*1e6)#microlamports
            instructions.append(set_compute_unit_limit(compute_unit_limit))
            instructions.append(set_compute_unit_price(priority_fee_limit))

            if create_account_instruction1:                                                            
                instructions.append(create_account_instruction1)
            
            if create_account_instruction2:
                instructions.append(create_account_instruction2) 

            if ix_wrap_sol:
                instructions.append(ix_wrap_sol)
                instructions.append(sync_native(SyncNativeParams(account=associated_wsol_account_pk, program_id=solana_utilites.TOKEN_PROGRAM_ID)))
    
            # Create a byte array to hold the data
            #pump_instruction_data = bytearray(24)
            accounts = self._get_accounts(order.order_type, signer_pk, mint_address_pk, pool_quote_address_pk, pool_base_address_pk, associated_token_account_pk,
                                          pool_address, associated_wsol_account_pk)

            # Pack the data into the byte array
            pump_instruction_data = discriminator_bytes + struct.pack("<QQ", raw_token_quantity, sol_limit_lamports)  
    
            pump_instruction = Instruction(self.PUMP_AMM_PROGRAM_PK, bytes(pump_instruction_data), accounts)
            instructions.append(pump_instruction)

            if ix_wrap_sol:
                ix_close = close_account(CloseAccountParams(
                    account=associated_wsol_account_pk,           # The WSOL ATA to close
                    dest=signer_pk,          # Where the SOL goes
                    owner=signer_pk,                # WSOL account owner (your wallet)
                    signers=[signer_pk],
                    program_id=solana_utilites.TOKEN_PROGRAM_ID)
                )
                instructions.append(ix_close)

            #Add a tip instruction if tipping; Needs to be the last instruction so it doesn't get taken if bundle is forked
            if order.swap_settings.jito_tip and order.swap_settings.jito_tip.value > 0: #Need to abstract this code so other platforms can add the fee
                jito_tip_instruction = SolanaRpcApi.create_transfer_instruction(signer_pk, self.jito_tip_address_pk, order.swap_settings.jito_tip.to_scaled())
                instructions.append(jito_tip_instruction)
      
            return self.build_v0_transaction(instructions, signer)
    