import math
import numpy as np
from TxDefi.Data.Amount import Amount

#Gets the price change
def get_value_change_percent(last_value: float, current_value: float)->float:
    if last_value == 0:
        return 0
    
    retPercent = current_value/last_value

    if current_value < last_value:
        retPercent = -(1-retPercent)
    else:
        retPercent = retPercent - 1
         
    return retPercent

#Estimate what the b reserves quantity should be for exchanging a certain amount of the 'a' token
def estimate_reserves_b_required(curr_reserves_a: float, curr_reserves_b: float, b_held: float, a_desired_quantity: float)->float:
    if b_held == 0 or a_desired_quantity == 0:
        return curr_reserves_b
    
    k_constant = curr_reserves_a*curr_reserves_b #pass this in for better performance

    #original equation
    #a_desired_quantity = k_constant/estimated_token_reserves - k_constant/(estimated_token_reserves - b_held)
    estimated_b_reserves = (b_held * (-a_desired_quantity + math.sqrt(a_desired_quantity**2 + (4 * k_constant * a_desired_quantity) / b_held))) / (2 * a_desired_quantity)

    return estimated_b_reserves

#Returns number of estimated tokens you receive with a given the input exchange quantity
def est_exchange_reserves(curr_reserves_a: float, curr_reserves_b: float, a_exchange_quanity: float)->float:
    k_constant = curr_reserves_a*curr_reserves_b #pass this in for better performance

    new_reserves_a = curr_reserves_a+a_exchange_quanity
    new_reserves_b = get_new_token_balance(new_reserves_a, k_constant)
    tokensReceivable = curr_reserves_b - new_reserves_b

    return {'reserves_a' : new_reserves_a, 'reserves_b' : new_reserves_b, 'tokens_receivable': tokensReceivable} 

def estimate_exchange(curr_reserves_a: float, curr_reserves_b: float, a_exchange_quanity: float)->float:
    return est_exchange_reserves(curr_reserves_a, curr_reserves_b, a_exchange_quanity)['tokens_receivable']

def est_new_token_price(curr_sol_balance: float, curr_token_balance: float, sol_change: float)->float:
        k_constant = curr_sol_balance*curr_token_balance #pass this in for better performance
        newSolBalance = curr_sol_balance+sol_change
        newTokenBalance = get_new_token_balance(newSolBalance, k_constant)

        return get_token_price(newSolBalance, newTokenBalance)

#Gets new token balance of a liquidity pool
def get_new_token_balance(currency_liquidity: float, k_constant: float)->float:
    return k_constant/currency_liquidity

#Get token price of a currency pair
def get_token_price(currency_liquidity_a: float, currency_liquidity_b: float)->float:
    return currency_liquidity_a/currency_liquidity_b

def calculate_potential_loss(buyAmountSol: float, currentSolValue: float, currentTokensAvailable: float, tokensHeld: float)->float:
    kConstant = currentSolValue*currentTokensAvailable

    newSolValue = currentSolValue+buyAmountSol
    newTokensAvailable = kConstant/newSolValue
    tokensReceived = currentTokensAvailable - newTokensAvailable

    #Calculate sol balance if others sold all their tokens
    newTokensAvailable = newTokensAvailable+tokensHeld
    solBalanceAfterSelloff = kConstant/newTokensAvailable

    #Check what happens when we sell back after the selloff
    newTokensAvailable = newTokensAvailable+tokensReceived
    solBalanceAfterMySelloff = kConstant/newTokensAvailable
    myProfit = solBalanceAfterSelloff-solBalanceAfterMySelloff-buyAmountSol

    return myProfit

def calc_potential_loss_percent(buyAmountSol: float, tokensHeld: float, currentSolValue: float, currentTokensAvailable: float)->float:
    #totaTokensHeld = totalMintedTokens - marketData.currTokenBalance this isn't right!
    lossAmount = calculate_potential_loss(buyAmountSol, currentSolValue, currentTokensAvailable, tokensHeld)

    return lossAmount/buyAmountSol

def calculate_diff(pre_token_balance: Amount, post_token_balance: Amount)->float:
    if post_token_balance:
        if not pre_token_balance:
            pre_token_ui_balance = 0
        else:
            pre_token_ui_balance = pre_token_balance.to_ui()

        if not post_token_balance:
            post_token_ui_balance = 0
        else:
            post_token_ui_balance = post_token_balance.to_ui()

        return post_token_ui_balance-pre_token_ui_balance
    
#Removes outliers from an array of numbers pass a Z-score > 3
def filter_noise(data : list):
    retArray = data
    npArray = np.array(data)
    mean = np.mean(npArray)
    std_dev = np.std(npArray)
 
    if std_dev > 0: 
        z_scores = (npArray - mean) / std_dev
        retArray = npArray[np.abs(z_scores) < 3]

    return retArray

def calc_mean(data : list, filtered = False):
    dataList = data
    if filtered:
        dataList = filter_noise(dataList)

    return np.mean(dataList)

if __name__ == '__main__':
    a_reserves = 1
    b_reserves = 700000000

    k = a_reserves*b_reserves
    estimatedExhange = est_exchange_reserves(a_reserves, b_reserves, .25)

    b_held = estimatedExhange['tokens_receivable']
    a_reserves = estimatedExhange['reserves_a']
    b_reserves = estimatedExhange['reserves_b']

    estimatedExhange2 = est_exchange_reserves(b_reserves, a_reserves, b_held) #Should go back to the way it was

    a_desired_out = 3
    k = a_reserves*b_reserves
    new_b_reserves = estimate_reserves_b_required(a_reserves, b_reserves, b_held, a_desired_out)

    print(str(new_b_reserves))
    new_a_reserves = k/new_b_reserves

    estimatedExhange = est_exchange_reserves(new_b_reserves, new_a_reserves, b_held)

    print(estimatedExhange)

