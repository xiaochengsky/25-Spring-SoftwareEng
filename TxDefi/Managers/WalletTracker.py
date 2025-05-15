from pubsub import pub
import threading
import json
from TxDefi.DataAccess.Blockchains.Solana.SolanaRpcApi import *
from TxDefi.Data.TransactionInfo import AccountInfo
from TxDefi.Data.MarketEnums import *
from TxDefi.DataAccess.Decoders.AccountNotificationDecoder import AccountNotificationDecoder, AccountNotification
from TxDefi.DataAccess.Decoders.SubscriptionsDataDecoder import Subscription
from TxDefi.DataAccess.Blockchains.Solana.AccountSubscribeSocket import AccountSubscribeSocket
from TxDefi.Abstractions.AbstractSubscriber import AbstractSubscriber

class AccountUpdateInfoAdvanced(AccountInfo):
    def __init__(self, id: int, account_address: str, balance: Amount, account_data: list[str] | dict = None):
        AccountInfo.__init__(self, account_address, balance, account_data)
        self.id = id
        self.rpc_subscription_id = 0
        self.account_info_decoder: AccountNotificationDecoder = None

    def get_account_notification(self)->AccountNotification:
        return self.last_notification
    
#Manage Tokem Market Activities
class WalletTracker(threading.Thread):
    current_rpc_id = 1

    def __init__(self, sub_socket: AccountSubscribeSocket, solana_rpc_api: SolanaRpcApi):
        threading.Thread.__init__(self, daemon=True)
        self.name = WalletTracker.__name__
        self.subscription_accounts_map : dict[int, AccountUpdateInfoAdvanced] = {} #key=rpc sub id
        self.subscribers : dict[int, AbstractSubscriber[AccountInfo]] = {} #key=callback subscriber id
        self.reverse_subscribers : dict[str, dict[int, AbstractSubscriber[AccountInfo]]] = {} #key=ca
        self.accounts_map : dict[str, AccountUpdateInfoAdvanced] = {} #key=ca
        self.rpc_id_accounts_map : dict[int, AccountUpdateInfoAdvanced] = {} #key=id
        self.sub_socket = sub_socket
        self.solana_rpc_api = solana_rpc_api

        self.updates_lock = threading.Lock()

    def run(self):
        pub.subscribe(topicName=self.sub_socket.out_topic, listener=self._handle_token_update)

    def _remove_client_subscription(self, subscriber_id: int, contract_address: str):
        if subscriber_id in self.subscribers:
            subscriber = self.subscribers.pop(subscriber_id)

            if subscriber.has_key(contract_address):
                subscriber.remove_key(contract_address)
                contract_subs = self.reverse_subscribers.get(contract_address)

                #Clean up the contract subs list
                if len(contract_subs) == 1:
                    contract_subs.clear()
                else:
                    contract_subs.pop(subscriber.get_id())

    def subscribe_to_wallet(self, contract_address: str, subscriber: AbstractSubscriber):
        if contract_address not in self.accounts_map:
            sol_balance = self.get_account_balance(contract_address)
            
            if sol_balance:
                new_account = AccountUpdateInfoAdvanced(self.current_rpc_id, contract_address, sol_balance)
                account_info_decoder = AccountNotificationDecoder(contract_address, self.solana_rpc_api)            

                new_account.account_info_decoder = account_info_decoder
                new_account.balance = sol_balance

                self.accounts_map[contract_address] = new_account
                self.rpc_id_accounts_map[self.current_rpc_id] = new_account
            
                #Make Sub Request
                account_sub_request = SolanaRpcApi.get_account_subscribe_request(contract_address, self.current_rpc_id)
                
                self.current_rpc_id += 1

                #Make socket sub request
                json_request = json.dumps(account_sub_request)  
        
                self.sub_socket.send_request_no_wait(json_request)
            else:
                print("WalletTracker: Issue Retrieving SOL Balance. Did you use the right Solana RPC key?")
    
        #Add subs
        contract_subs = self.reverse_subscribers.get(contract_address) 
        if not contract_subs:
            contract_subs = {}
            self.reverse_subscribers[contract_address] = contract_subs
            self.subscribers[subscriber.get_id()] = subscriber
        contract_subs[subscriber.get_id()] = subscriber

    #TODO
    def unsubscribe_to_wallet(self, contract_address: str, subscriber: AbstractSubscriber):
         with self.updates_lock:
            if contract_address in self.accounts_map.keys():
                id = self.accounts_map[contract_address]
                account = self.accounts_map.pop(contract_address)

                self.rpc_id_accounts_map.pop(id)

                contract_subs = self.reverse_subscribers.get(contract_address) 

                if contract_subs:
                    for sub in contract_subs.values:
                        self._remove_client_subscription(sub.get_id(), contract_address)
           
                self.reverse_subscribers[contract_address] = contract_subs
                #TODO
                account_unsub_request = SolanaRpcApi.get_account_unsubscribe_request(contract_address, self.current_rpc_id)
                json_request = json.dumps(account_unsub_request)       
                self.sub_socket.send_request_no_wait(json_request)

    def get_account_balance(self, contract_address: str)->Amount:
        if contract_address not in self.rpc_id_accounts_map:
            #Query the amount if we're not tracking it
            return self.solana_rpc_api.get_account_balance_Amount(contract_address)

        return self.accounts_map[contract_address].balance

    def _handle_token_update(self, arg1):      
        if isinstance(arg1, Subscription) and arg1.id in self.rpc_id_accounts_map: #Successful subscription, so add the decoder
            with self.updates_lock:
                self.rpc_id_accounts_map[arg1.id].rpc_subscription_id = arg1.subscription #need to hold onto this to unsubscribe
                self.subscription_accounts_map[arg1.subscription] = self.rpc_id_accounts_map[arg1.id]
                decoder = self.rpc_id_accounts_map[arg1.id].account_info_decoder
                account_address = self.rpc_id_accounts_map[arg1.id].account_address
                self.sub_socket.wallet_tracker_decoder.add_decoder(arg1.subscription, decoder)
                print(f"WalletTracker: subsription successful! id: {arg1.id} CA: {account_address}")
        elif isinstance(arg1, AccountNotification): #Has transaction signature
            #print("Wallet update " + arg1.tx_signature) #DELETE
            account_info = self.subscription_accounts_map.get(arg1.subscription_id)
            account_info.balance.set_amount2(arg1.lamports, Value_Type.SCALED)
            account_info.account_data = arg1.account_data
            account_info.last_slot = arg1.slot
            subscribers = self.reverse_subscribers.get(account_info.account_address, {})
            
            for subscriber in subscribers.values():
                subscriber.update(account_info)
            
    #Get an alias name for a given wallet address if available
    def get_wallet_alias(contract_address: str):
        pass #TODO i.e. return Mr. Frog

    def stop(self):
        pub.unsubscribe(topicName=self.sub_socket.out_topic, listener=self._handle_token_update)