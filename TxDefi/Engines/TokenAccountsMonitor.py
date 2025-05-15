from pubsub import pub
import concurrent.futures
import time
from TokenInfoRetriever import TokenInfoRetriever
from TxDefi.Data.TransactionInfo import *
from TxDefi.Data.TokenPoolStates import TokenPoolStates
from TxDefi.Data.MarketDTOs import *
from TxDefi.DataAccess.Blockchains.Solana.AccountSubscribeSocket import AccountSubscribeSocket
from TxDefi.DataAccess.Blockchains.Solana.RiskAssessor import Risk, RiskAssessor
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import SolanaRpcApi
from TxDefi.Managers.WalletTracker import WalletTracker
from TxDefi.Abstractions.AbstractSubscriber import AbstractSubscriber
from TxDefi.DataAccess.Decoders.SolanaLogsDecoder import SolanaLogsDecoder
import TxDefi.Utilities.LoggerUtil as logger_util
import TxDefi.Data.Globals as globals

class VaultBalances:
    def __init__(self, token_address: str,  sol_vault_address: str, token_vault_address: str, sol_balance: Amount, token_balance: Amount):
        self.token_address = token_address
        self.sol_vault_address = sol_vault_address
        self.token_vault_address = token_vault_address
        self.sol_balance = sol_balance
        self.token_balance = token_balance

class TokenAccountsMonitor(AbstractSubscriber[AccountInfo]):
    max_saved_transactions = 1000
    min_pump_bonding_pc_amount = 79e9
    max_pump_tokens_at_bonding = 207000000000000
    acceptable_lp_risk = Risk.NONE #Won't pass added liquidity new mints through unless risk is acceptable

    def __init__(self, solana_rpc_api: SolanaRpcApi, info_retriever: TokenInfoRetriever, 
                 pump_logs_decoder: SolanaLogsDecoder, risk_assessor: RiskAssessor):
        AbstractSubscriber. __init__(self)
        self.token_pools: dict[str, TokenPoolStates] = {}
        self.monitored_tokens: dict[str, TokenInfo] = {}
        self.tokens_metadata : dict[str, ExtendedMetadata] = {}
        
        self.vault_balances : dict[str, VaultBalances] = {} #key= reference address (token or vault address)
        self.token_info_retriever = info_retriever
        self.pending_token_updates = set()
        self.solana_rpc_api = solana_rpc_api    

        self.risk_assessor = risk_assessor
        self.token_balance_change_socket = AccountSubscribeSocket(solana_rpc_api.wss_uri, "tam_token_balance", False)
        self.sol_balance_change_socket = AccountSubscribeSocket(solana_rpc_api.wss_uri, "tam_sol_balance", False)
        self.token_balance_tracker = WalletTracker(self.token_balance_change_socket, solana_rpc_api)
        self.sol_balance_tracker = WalletTracker(self.sol_balance_change_socket, solana_rpc_api)
        self.new_mints_paused = False
        self.pump_logs_decoder = pump_logs_decoder
        self.subbed_topics : list[str] = []
        self.saved_transactions : dict[str, ParsedTransaction] = {} #TODO keep the list size small so reduce memory footprint

    def _update_new_token_task(self, token_address: str, max_tries = 10, interval = 10):
        success = False

        time_start = time.time()
        is_token_bonding = False

        if token_address in self.token_pools:
            token_info = self.token_pools.get(token_info).get_selected_pool()

            if token_info:
                is_token_bonding = token_info.phase == TokenPhase.BONDING_IN_PROGRESS

        for _ in range(max_tries):    
            token_info = self.token_info_retriever.get_token_info(token_address, is_token_bonding)
    
            if token_info:
               success = True               
               self.add_new_pool(token_info)
               break  

            time.sleep(interval)     

        time_taken = time.time() - time_start
        message = token_address + " retrieval time " + str(time_taken) + " seconds"
        print(message)
        logger_util.logger.info(message)
        print("Success: " + str(success))
        self.pending_token_updates.pop(token_address)

    def get_complete_metadata(self, token_address: str)->ExtendedMetadata:
        if token_address in self.tokens_metadata:
            return self.tokens_metadata[token_address]
        
        ext_metadata = self.token_info_retriever.get_complete_metadata(token_address)

        if ext_metadata:
            if token_address in self.token_pools and self.token_pools.get(token_address).get_selected_pool():
                token_info = self.token_pools.get(token_address).get_selected_pool()

                if token_info.is_metadata_complete():
                    ext_metadata.sol_vault_address = token_info.metadata.sol_vault_address #TODO see if you really need to do this
                    ext_metadata.token_vault_address = token_info.metadata.token_vault_address #Keep them in sync
           
                token_info.copy_missing_metadata(ext_metadata) #keep token info updated

            self.tokens_metadata[token_address] = ext_metadata #store for quicker access
        
        return ext_metadata
        
    def delete_token_metadata(self, mint_address):
        if mint_address in self.tokens_metadata:
            self.tokens_metadata.pop(mint_address)

    def start_monitoring(self):
        pub.subscribe(topicName=globals.topic_amm_program_event, listener=self._handle_amm_data_task)
        pub.subscribe(topicName=globals.topic_incoming_transactions, listener=self._handle_amm_transactions)   

    def stop_monitoring(self):
        pub.unsubscribe(topicName=globals.topic_amm_program_event, listener=self._handle_amm_data_task)
        pub.unsubscribe(topicName=globals.topic_incoming_transactions, listener=self._handle_amm_transactions)        

    def is_monitoring(self, token_address)->bool:
        return token_address in self.monitored_tokens

    def is_monitoring_token_info(self, token_address)->TokenInfo:
        return token_address in self.monitored_tokens
    
    def get_token_info(self, token_address)->TokenInfo:
        ret_token_info = None

        if token_address in self.token_pools:
            ret_token_info = self.token_pools.get(token_address).get_selected_pool()
            
        if not ret_token_info or ret_token_info.phase == TokenPhase.BONDING_IN_PROGRESS:
            #print("Retrieving " +  token_address)
            ret_token_info = self.token_info_retriever.get_token_info(token_address)

            if ret_token_info:
                self.add_new_pool(ret_token_info)
        
        return ret_token_info
    
    def switch_token_pool(self, token_info: TokenInfo)->TokenInfo:
        #See if we have it already recorded
        self.add_new_pool(token_info)      

        #Switch to monitoring this token pool
        if token_info.token_address in self.monitored_tokens: 
            self.stop_monitoring_token(token_info.token_address)

        self._sub_to_token_updates(token_info)
        
    def toggle_new_mints(self):
        self.new_mints_paused = not self.new_mints_paused

    #Chooses 1st pool available
    def monitor_token(self, token_address: str)->TokenInfo:
        if token_address in self.monitored_tokens:
            token_info = self.monitored_tokens[token_address]
        else: 
            #See if we have it already recorded
            token_pool_state = self.token_pools.get(token_address)
           
            if token_pool_state:
                token_info = token_pool_state.get_selected_pool()

                if token_info and token_info.phase == TokenPhase.BONDED:
                    #We must have the vault info already and just need to update the amounts
                    self.token_info_retriever.update_token_vaults(token_info)
                elif token_info.phase == TokenPhase.BONDING_IN_PROGRESS:           
                    if token_address not in self.pending_token_updates:
                        message = token_address + " is still bonding! Init2 may have been missed due to RPC issues. Trying to retrieve it. Try again later."

                        logger_util.logger.info(message)
                        print(message)
                        self.pending_token_updates.add(token_address)
                        
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            executor.submit(self._update_new_token_task, (token_address))

                    token_info = None

            if not token_pool_state or not token_info: #Go retrieve it the expensive way               
                token_info = self.token_info_retriever.get_token_info(token_address)
                
                if token_info:
                    self.add_new_pool(token_info)          

            if token_info:
                self._sub_to_token_updates(token_info)           
        
        return token_info

    def _sub_to_token_updates(self, token_info: TokenInfo):
        if token_info not in self.monitored_tokens and token_info.phase == TokenPhase.BONDED: #Don't monitor Pumpfun wallets, value is retrieved from the real-time updates
            self.monitored_tokens[token_info.token_address] = token_info
            sol_vault_address = token_info.metadata.sol_vault_address
            token_vault_address = token_info.metadata.token_vault_address
            vault_balances = VaultBalances(token_info.token_address, sol_vault_address, token_vault_address, token_info.sol_vault_amount, token_info.token_vault_amount)
            
            #Link the references
            self.vault_balances[sol_vault_address] = vault_balances
            self.vault_balances[token_vault_address] = vault_balances
            self.sol_balance_tracker.subscribe_to_wallet(sol_vault_address, self)
            self.token_balance_tracker.subscribe_to_wallet(token_vault_address, self) 

    def stop_monitoring_token(self, token_address: str):
        if token_address in self.monitored_tokens:
            token_info = self.monitored_tokens.pop(token_address)

            if token_address in self.vault_balances:
                self.vault_balances.pop(token_info.metadata.sol_vault_address)
                self.vault_balances.pop(token_info.metadata.token_vault_address)

            self.sol_balance_tracker.unsubscribe_to_wallet(token_info.metadata.sol_vault_address, self)
            self.token_balance_tracker.unsubscribe_to_wallet(token_info.metadata.token_vault_address, self) 

    def _update_price(self, token_address: str):
        if token_address in self.monitored_tokens:
            token_info = self.monitored_tokens[token_address]
            token_balance = self.solana_rpc_api.get_token_account_balance(token_info.metadata.token_vault_address) 
                        
            if token_balance:
                token_info.token_vault_amount = token_balance

    def _init(self):
        token_addresses = list(self.monitored_tokens.keys())

        for token_address in token_addresses:
            self.monitor_token(token_address)
    
    def find_instruction(self, transaction: ParsedTransaction, event_type: TradeEventType)->InstructionData | MarketAlert: #FIXME shouldn't be returning 2 different types
        for instruction in transaction.instructions:
            if instruction.data.get_type() == event_type:
                return instruction.data

    def delete_transaction(self, tx_signature)->ParsedTransaction:
        if tx_signature in self.saved_transactions:
            return self.saved_transactions.pop(tx_signature)

    #Process Transactions from a geyser
    def _handle_amm_transactions(self, arg1: ParsedTransaction):
        self.saved_transactions[arg1.tx_signature] = arg1
        trade_alerts = None
        supported_programs = arg1.get_supported_programs()
        
        #TODO: Don't process logs if we have enough info from the transaction; need to probably only do this for pump tokens
        if SupportedPrograms.PUMPFUN in supported_programs: #Need more info from Pump Logs
            trade_alerts = self.pump_logs_decoder.decode_logs(arg1.log_messages, arg1.slot, arg1.tx_signature)
        
        if not trade_alerts and arg1.instructions and len(arg1.instructions) > 0:
            trade_alerts = []
            for instruction in arg1.instructions:
                if (instruction.instruction_type == TradeEventType.BUY or instruction.instruction_type == TradeEventType.SELL
                    or instruction.instruction_type == TradeEventType.ADD_LIQUIDITY or instruction.instruction_type == TradeEventType.REMOVE_LIQUIDITY):
                    
                    trade_alerts.append(instruction.data)
       
        if trade_alerts:            
            self._handle_amm_data_task(trade_alerts)

        if len(self.saved_transactions) > self.max_saved_transactions: #Cleanup Task
            cut_amount = int(self.max_saved_transactions/2) #Remove half of the transactions
            self.saved_transactions = dict(list(self.saved_transactions.items())[cut_amount:])

    #Process Transactions from a logs subscription or MarketAlerts event
    def _handle_amm_data_task(self, arg1: list[MarketAlert]): #use generics to prevent misuse
        with concurrent.futures.ThreadPoolExecutor() as executor: 
            executor.submit(self.process_incoming_data, arg1)

    def process_incoming_data(self, data_list: list[MarketAlert | InstructionData]):
        for data in data_list:
            if not self.new_mints_paused or data.get_type() != TradeEventType.NEW_MINT:    
                self._process_mint_data(data)

    def add_new_pool(self, token_info: TokenInfo):
        token_pool_states = self.token_pools.get(token_info.token_address)

        if not token_pool_states:
            token_pool_states = TokenPoolStates(token_info.token_address)

            #Save for our records
            self.token_pools[token_info.token_address] = token_pool_states
                        
        token_pool_states.add_pool(token_info)

    def _get_transaction(self, tx_signature: str)->ParsedTransaction:
        transaction = self.saved_transactions.get(tx_signature)

        if not transaction:
            transaction = self.token_info_retriever.get_transaction_from_tx(tx_signature)
        
        return transaction

    def _process_mint_data(self, data: PumpMigration | LiquidityPoolData | SwapData | RetailTransaction | ExtendedMetadata):
        if data.program_type == SupportedPrograms.PUMPFUN:
            if data.get_type() == TradeEventType.NEW_MINT:
                if data.tx_signature in self.saved_transactions:
                    transaction = self.saved_transactions[data.tx_signature]
                    new_mint_instruction = self.find_instruction(transaction, data.get_type())

                    if new_mint_instruction and isinstance(new_mint_instruction, ExtendedMetadata):
                        data = new_mint_instruction #Use this, it has the token vault info and saves us from having to make extra RPC calls
               
                token_info = TokenInfo.from_metadata(data)               
                token_info.phase = TokenPhase.NEW_MINT

                self.add_new_pool(token_info) #Need the next retail transaction to fill out reserves; will notify clients then
            elif data.token_address in self.token_pools:
                token_pools = self.token_pools.get(data.token_address)
                token_info = token_pools.get_selected_pool()
                
                if token_info and isinstance(data, RetailTransaction):                                       
                    if token_info.phase == TokenPhase.NEW_MINT:
                        #Copy missing essential data (don't need all the metadata yet, time is of the essence here)
                        if not token_info.is_metadata_complete(): #No vaults
                            transaction = self._get_transaction(data.tx_signature)
                            token_infos = self.token_info_retriever.extract_token_infos(transaction)

                            if token_infos and len(token_infos) > 0:
                                token_info.copy_missing(token_infos[0])
                                
                        token_info.phase = TokenPhase.NOT_BONDED
                        token_info.sol_vault_amount = Amount.sol_scaled(data.sol_reserves)
                        token_info.token_vault_amount = Amount.tokens_scaled(data.token_reserves, 6)
                        pub.sendMessage(topicName=globals.topic_token_alerts, arg1=token_info.metadata) #Send out an ExtendedMetaData message indicating that there's a new mint
                    else:                            
                        #Keep Token Values Updated; Don't need to do this for bonded tokens since we monitor those vault accounts
                        token_info.sol_vault_amount.set_amount2(data.sol_reserves, Value_Type.SCALED)
                        token_info.token_vault_amount.set_amount2(data.token_reserves, Value_Type.SCALED)     

                    pub.sendMessage(topicName=globals.topic_token_update_event, arg1=token_info.token_address)      
                    #TODO Can track snipers and bundlers here    
            elif data.get_type() == TradeEventType.BONDING_COMPLETE and isinstance(data, PumpMigration):          
                self._migrate_token(data)
        elif data.get_type() == TradeEventType.ADD_LIQUIDITY and isinstance(data, LiquidityPoolData): #Raydium or Pump AMM Add Liquidity
            if self.risk_assessor.liquidity_check(data).value >= self.acceptable_lp_risk.value:
                return

            token_pools = self.token_pools.get(data.token_address)

            print(f"Add Liquidity: New Pool {data.token_address} Tx: {data.tx_signature}")
            if not token_pools: #Need to retrieve token info onchain since we're not monitoring this
                transaction = self._get_transaction(data.tx_signature)
                token_infos = self.token_info_retriever.extract_token_infos(transaction)

                for token_info in token_infos:
                    self.add_new_pool(token_info)                         
                    pub.sendMessage(topicName=globals.topic_token_alerts, arg1=MarketAlert(token_info.token_address, data.get_type()))
            else: #Likely an more liquidity added to an existing pool TODO figure out what to do with this
                token_info = token_pools.get_selected_pool()

                if token_info.phase == TokenPhase.NOT_BONDED and data.pc_amount >= 84E9 and data.coin_amount >= 206900E9:
                    self._migrate_token(PumpMigration(data.token_address))   
                #Let client decide what to do with the info
                #pub.sendMessage(topicName=globals.topic_token_alerts, arg1=LiquidityPoolAlert(data))
                pass 
        elif data.get_type() == TradeEventType.REMOVE_LIQUIDITY:
            pass
            #transaction = self._get_transaction(data.tx_signature) #TODO Don't manage this just yet
            #token_infos = self.token_info_retriever.extract_token_infos(transaction)
            
            #for token_info in token_infos:                            
            #    pub.sendMessage(topicName=globals.topic_token_alerts, arg1=MarketAlert(token_info.token_address, data.get_type())) #TODO Revisit, need the amount pulled as well
        elif data.get_type() == TradeEventType.EXCHANGE or data.get_type() == TradeEventType.BUY or data.get_type() == TradeEventType.SELL:
            #token_pools = self.token_pools.get(data.token_address)

            #if not token_pools: #only investigate tokens we're monitoring

            pass #TODO Track Tx Snipers; need to pull the right pools since it's bonded
    
    def _get_add_liquidity(self, tx_signature: str)->LiquidityPoolData:
        transaction = self._get_transaction(tx_signature)
        
        for instruction_info in transaction.instructions:
            if instruction_info.data.get_type() == TradeEventType.ADD_LIQUIDITY:
                return instruction_info

    def _migrate_token(self, data: PumpMigration):
        transaction = self._get_transaction(data.tx_signature)
        migration_data : PumpMigration = None 
        add_liquidity_data : LiquidityPoolData= None

        if transaction:
            for instruction_info in transaction.instructions:
                instr_data = instruction_info.data
                if isinstance(instr_data, PumpMigration):
                    migration_data = instr_data
                elif instruction_info.data.get_type() == TradeEventType.ADD_LIQUIDITY and isinstance(instr_data, LiquidityPoolData):
                    add_liquidity_data = instr_data
                    break
                        
        if migration_data and add_liquidity_data:             
            token_info = self.get_token_info(migration_data.token_address)
            token_info.metadata.program_type = SupportedPrograms.PUMPFUN_AMM
            token_info.phase = TokenPhase.BONDED
            token_info.metadata.market_id = migration_data.market_address 
            token_info.metadata.sol_vault_address = migration_data.sol_vault_address 
            token_info.metadata.token_vault_address = migration_data.token_vault_address
            token_info.sol_vault_amount.set_amount2(add_liquidity_data.pc_amount, Value_Type.SCALED)
            token_info.token_vault_amount.set_amount2(add_liquidity_data.coin_amount, Value_Type.SCALED)

            #Resub to token updates on the new vault
            self._sub_to_token_updates(token_info)

            print(f"Bonding Complete {migration_data.token_address} {type(migration_data)}")         

            pub.sendMessage(topicName=globals.topic_token_alerts, arg1=migration_data)  

    def _process_account_info(self, account_info: AccountInfo):
        vault_balances = self.vault_balances.get(account_info.account_address)
        
        if vault_balances:
            token_info = self.get_token_info(vault_balances.token_address)

            if isinstance(account_info.account_data, dict): #Check if there's token amounts
                info = account_info.account_data.get('parsed', {}).get('info')

                if info:
                    mint_address = info.get('mint')
                    token_amount = info.get('tokenAmount')
                
                    if mint_address and token_amount:
                        ui_amount = token_amount.get('uiAmount') 
                        if mint_address == solana_utilites.WRAPPED_SOL_MINT_ADDRESS:
                            vault_balances.sol_balance.set_amount2(ui_amount, Value_Type.UI)
                            token_info.sol_vault_amount = vault_balances.sol_balance
                        else:
                            vault_balances.token_balance.set_amount2(ui_amount, Value_Type.UI)
                            token_info.token_vault_amount = vault_balances.token_balance
                            #print("Token vault balance changed for " + vault_balances.token_address) #Only need one notification per pair
                            pub.sendMessage(topicName=globals.topic_token_update_event, arg1=vault_balances.token_address)
            else: #Must be just a sol account
                vault_balances.sol_balance.set_amount(account_info.balance)
                token_info.sol_vault_amount = vault_balances.sol_balance
                            
    #This is called by our Wallet Tracker
    def update(self, data: AccountInfo):
        self._process_account_info(data)

    def start(self):
        self.token_balance_change_socket.start()
        self.sol_balance_change_socket.start()
        self.token_balance_tracker.start()
        self.sol_balance_tracker.start()

    def stop(self):
        pub.unsubAll()
        self.token_balance_change_socket.stop()
        self.sol_balance_change_socket.stop()
        self.token_balance_tracker.stop()
        self.sol_balance_tracker.stop()





    
