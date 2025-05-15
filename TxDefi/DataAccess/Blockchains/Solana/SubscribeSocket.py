import json
from pubsub import pub
from TxDefi.Data.MarketDTOs import *
from TxDefi.DataAccess.Decoders import MessageDecoder
from TxDefi.DataAccess.MarketDataSocket import MarketDataSocket

class SubscribeSocket(MarketDataSocket):    
    def __init__(self, wss_uri: str, event_decoder: MessageDecoder, out_topic: str, requests: list[str] = [], ping = True):
        MarketDataSocket.__init__(self, wss_uri, ping)
   
        self.event_decoder = event_decoder
        self.out_topic = out_topic
        self.count = 1
        self.sub_requests = requests

    def _init(self):
        for sub_request in self.sub_requests:
            #print(f"Sending sub_request: {sub_request}")
            self.send_request_no_wait(sub_request)

    def add_sub_request(self, request: str):   
        if request not in self.sub_requests:
            self.sub_requests.append(request)

    def send_request_no_wait(self, request: str):
        super().send_request_no_wait(request)

        self.add_sub_request(request)

    def process_data(self, data: str):   
        json_data = json.loads(data)

        if json_data:
            #print("Decoding " + data + "\n")
            decoded_data = self.event_decoder.decode(json_data)

            if decoded_data:
                self.count += 1 #DELETE
                #if isinstance(decoded_data, list):
                #    for obj in decoded_data:
                #        if isinstance(obj, PumpMigration) or isinstance(obj, MintMetadata) or isinstance(obj, LiquidityPoolData):
                #            print(f"Received {self.count}: {obj} {obj.tx_signature} out {self.out_topic}")
                pub.sendMessage(topicName=self.out_topic, arg1=decoded_data)

