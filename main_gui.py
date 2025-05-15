import asyncio
import os
from dotenv import load_dotenv
from TxDefi.TxDefiToolKit import TxDefiToolKit
from TxDefi.Data.TradingDTOs import *
from TxDefi.UI.MainUi import MainUi

async def main():    
    program_executor = TxDefiToolKit(True)
    
    main_gui = MainUi(program_executor, is_muted=False)
    
    # Set OpenAI API key directly
    main_gui.set_openai_api("xxxxx")  # key

    main_gui.show_modal()

if __name__ == "__main__":
    asyncio.run(main())