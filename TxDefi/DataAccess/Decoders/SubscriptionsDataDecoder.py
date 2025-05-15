from TxDefi.DataAccess.Decoders.MessageDecoder import MessageDecoder
from TxDefi.Data.MarketDTOs import *

class Subscription:
    def __init__(self, id: int, subscription: int):
        self.id = id
        self.subscription = subscription

class SubscriptionsDataDecoder(MessageDecoder[Subscription]):
    def __init__(self):
        self.message_decoders : dict[int, MessageDecoder] = {}

    def add_decoder(self, subscription_id: int, decoder: MessageDecoder):
        self.message_decoders[subscription_id] = decoder
    
    def remove_decoder(self, subscription_id: int):
        self.message_decoders.pop(subscription_id)
        
    def decode(self, data: dict)->Subscription:
        try:
            decoded_data = None
            id = data.get("id", {})

            if id:
                subscription = data.get("result", None)

                if subscription:
                    decoded_data = Subscription(id, subscription)
            else:
                subscription = data['params']['subscription']

                if subscription in self.message_decoders:
                    decoded_data = self.message_decoders[subscription].decode(data)
            
            return decoded_data
        except Exception as e:
            print("Error decoding " + str(e))