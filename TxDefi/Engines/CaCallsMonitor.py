from pubsub import pub
import TxDefi.Utilities.ParsingUtilities as utils
import TxDefi.Data.Globals as globals
from TxDefi.Data.TradingDTOs import CallEvent
from TxDefi.Data.WebMessage import WebMessage

#CA monitor with Discord and X support
class CaCallsMonitor:
    def __init__(self, fiter_on = False):
        self.fiter_on = fiter_on

    def start(self):
        pub.subscribe(topicName=globals.topic_socials_messages, listener=self._handle_message)
        self.user_filter: list[str] = []

    def stop(self):
        pub.unsubscribe(topicName=globals.topic_socials_messages, listener=self._handle_message)
        
    def toggle_filter(self):
        self.fiter_on = not self.fiter_on

    def filter_on(self, user: str):
        self.user_filter.append(user.lower())
       
    def remove(self, user: str):
        if user in self.user_filter:
            self.user_filter.pop(user)
    
    def _handle_message(self, arg1: WebMessage):
        if not self.fiter_on or arg1.user.lower() in self.user_filter:
            contract_addresses = utils.extract_base58_address(arg1.message)
            #print(f"{arg1.timestamp}: {arg1.appname} {arg1.user} CA: {arg1.message}")

            pub.sendMessage(topicName=globals.topic_ca_call_event, arg1=CallEvent(arg1.user, arg1.message, contract_addresses))
    