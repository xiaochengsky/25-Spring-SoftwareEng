import os
import sys

from TxDefi.DataAccess.Decoders.AccountNotificationDecoder import AccountNotificationDecoder
from TxDefi.DataAccess.Blockchains.Solana.SubscribeSocket import SubscribeSocket
from TxDefi.DataAccess.Decoders.SubscriptionsDataDecoder import SubscriptionsDataDecoder

class AccountSubscribeSocket(SubscribeSocket):    
    def __init__(self, wss_uri: str, out_topic: str, ping = False):
        SubscribeSocket.__init__(self, wss_uri, SubscriptionsDataDecoder(), out_topic, [], ping)
        self.wallet_tracker_decoder : SubscriptionsDataDecoder = self.event_decoder
    
    def add_decoder(self, subscription_id: int, account_info_decoder: AccountNotificationDecoder):
        self.wallet_tracker_decoder.add_decoder(subscription_id, account_info_decoder)
    
    def remove_decoder(self, subscription_id: int):
        self.wallet_tracker_decoder.remove_decoder(subscription_id) 