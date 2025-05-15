from enum import Enum

class SupportEncryption(Enum):
    AES = 0
    NONE = 1

    @staticmethod
    def to_enum(type_str: str)->Enum:
        if type_str.upper() == SupportEncryption.AES.name:
            return SupportEncryption.AES
        else:
            return SupportEncryption.NONE
        
class PromptInterface(Enum):
    CLI = 0,
    UI = 1

def encrypt(decrypted_data: str, encrypton: SupportEncryption)->str | bytes:
    if encrypton == SupportEncryption.NONE:
        return decrypted_data
    
def decrypt(encrypted_data: str, encrypton: SupportEncryption)->str:
    if encrypton == SupportEncryption.NONE:
        return encrypted_data