from TxDefi.Data.TradingDTOs import *
from TxDefi.Abstractions.AbstractMarketManager import AbstractMarketManager

class TokenDipSignalGenerator:
    def __init__(self, token_address: str, market_manager: AbstractMarketManager, chart_interval_seconds: int, trigger_drop_percent: Amount):
        self.token_address = token_address
        self.market_manager = market_manager
        self.chart_interval_seconds = chart_interval_seconds
        self.trigger_drop_percent = trigger_drop_percent.to_ui()/100

    def update(self)->SignalState:
        signal_state = SignalState.UNTRIGGERED

        latest_candles = self.market_manager.get_candlesticks(self.token_address, self.chart_interval_seconds)

        if latest_candles and len(latest_candles) >= 2:
            count = len(latest_candles)
            previous_low_price = latest_candles[count-2].low
            latest_close_price = latest_candles[count-1].close

            if latest_close_price < previous_low_price:
                percent_change = 1 - latest_close_price/previous_low_price

                if percent_change >= self.trigger_drop_percent:
                    signal_state = SignalState.TRIGGERED
                    print("Trigger for self.trigger_drop_percent occured! Percent drop=" + str(percent_change*100) + "%")
        
        return signal_state
