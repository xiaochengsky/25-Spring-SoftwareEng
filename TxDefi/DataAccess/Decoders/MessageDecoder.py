from abc import abstractmethod
from base64 import b64decode
import base58

from typing import TypeVar, Generic

T = TypeVar("T", bound=object)  # Generic type Key Pair Type

#Abstract class for any message decoder
class MessageDecoder(Generic[T]): #Low priority Fix; need a generic for the output of decode
    base64_encoding = 'base64'
    base58_encoding = 'base58'
        
    @abstractmethod
    def decode(self, data: T)->any:
        pass   
    
    @staticmethod
    def get_bytes(program_data: str, encoding: str)->bytes:
        decoded_bytes = None

        try:           
            if encoding == MessageDecoder.base64_encoding:
                decoded_bytes = b64decode(program_data)
            elif encoding == MessageDecoder.base58_encoding:
                decoded_bytes = base58.b58decode(program_data)

        except Exception as e:
            print("Problem parsing program data " + program_data)

        return decoded_bytes
    
class LogsDecoder(MessageDecoder[T]):
    program_data_prefix = "Program data:"
    program_instruction_prefix = "Program log: Instruction:"
    
    @abstractmethod
    def get_log_data_prefixes(self)->list[str]:
        pass
    
    @abstractmethod
    def decode_log(self, log: str)->object:
        pass