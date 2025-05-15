
import json
import time
import requests
from solders.keypair import Keypair
import HttpUtils as http_utils

class RugCheckerApi:
    uri = "https://api.rugcheck.xyz/"

    def __init__(self, key_pair: Keypair = None):
        if key_pair:
            self.keypair = key_pair
        else:
            self.keypair = Keypair()

        self.auth_token = self.auth()

    def auth(self)->str:
        auth_uri = self.uri + "auth/login/solana"
        auth_request = self.get_auth_request()
        pubkey = str(self.keypair.pubkey())

        auth_request['message']['publicKey'] = pubkey
        auth_request['message']['timestamp'] = int(time.time_ns()/1E6)

        message_bytes = json.dumps(auth_request['message'], separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        signature = self.keypair.sign_message(message_bytes)
              
        auth_request['signature']['data'] = signature.to_bytes_array()
        auth_request['wallet'] = pubkey

        response = requests.post(auth_uri, json=auth_request)

        if response:
            r_text = json.loads(response.text)
            return r_text.get("token")   

    def get_token_report(self, token_address: str):
        uri = f"{self.uri}v1/tokens/{token_address}/report"
        
        headers = {'Content-Type': 'application/json', 'Authorization': f"Bearer {self.auth_token}"}

        return http_utils.get_request(uri, headers=headers)
    
    def stop(self):
        self.rate_limiter.stop()
        
    @staticmethod
    def get_auth_request()->dict:
        return {
        "message": {
            "message": "Sign-in to Rugcheck.xyz",
            "timestamp": 0,
            "publicKey": ""
        },
        "signature": {
            "data": [],
            "type": "Buffer"
        },
        "wallet": ""
        }