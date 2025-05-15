import requests
from jsonrpcclient import request, parse, Ok, Error

#Get a valid code 200 HTTP request and return the response json
def get_request(uri: str, headers : dict = None, timeout: int = None)->dict:
    try:
        response = requests.get(uri, headers, timeout=timeout)

        if response.status_code == 200: #and responseCode < 400:
            return response.json()
    except Exception as e:
        print("HttpUtils: get_request failed " + uri + " " + str(e))
    
def post_request(uri: str, json_request: dict, timeout: int = None)->dict:
    try:
        response = requests.post(uri, json=json_request)
        parsed = parse(response.json())

        if isinstance(parsed, Error): 
            return None
        else:
            return parsed
    except Exception as e:
        print("HttpUtils: post failed " + str(e))