from TxDefi.Data.MarketDTOs import TokenInfo
from TxDefi.Data.MarketEnums import TokenPhase

class TokenPoolStates:
    def __init__(self, token_address: str):
       self.token_address = token_address
       self.token_pools: dict[str, TokenInfo] = {} #key=sol_vault_address
       self.selected_pool = None

    def add_pool(self, token_info: TokenInfo):
        if token_info.metadata.sol_vault_address not in self.token_pools:
            self.selected_pool = token_info
            self.token_pools[token_info.metadata.sol_vault_address] = token_info
        
    def remove_pool(self, token_info: TokenInfo):
        if token_info.metadata.sol_vault_address in self.token_pools:
             self.token_pools.pop(token_info.metadata.sol_vault_address)

    def get_pool(self, sol_vault_address: str)->TokenInfo:
        return self.token_pools.get(sol_vault_address)
    
    def get_selected_pool(self)->TokenInfo:
        return self.selected_pool
    
    def get_best_pool(self)->TokenInfo:    
        for token_info in self.token_pools.values():
            if token_info.sol_vault_amount.value > 0 and token_info.phase != TokenPhase.BONDING_IN_PROGRESS:
                return token_info #TODO future work

        #self.token_pools.clear()