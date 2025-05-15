import re

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False
    
def extract_base58_address(text):
    # Base58 pattern: Matches sequences of Base58 characters with lengths of 32 to 44
    base58_pattern = r'\b[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{32,44}\b'
    matches = re.findall(base58_pattern, text)

    # Return the matches (Base58 addresses)
    return matches
