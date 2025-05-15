# TraDeFi - AI-Powered Trading Platform

TraDeFi is an advanced trading platform that combines the power of AI with decentralized finance on the Solana blockchain. This platform enables users to trade tokens with the assistance of AI agents while maintaining full control over their assets.

## Prerequisites

- Python 3.10
- Conda package manager
- Phantom Wallet
- Helius RPC Node access

## Setup Steps

1. **Create Conda Environment**
   ```bash
   conda create -n trade python=3.10
   conda activate trade
   ```

2. **Install Dependencies**
   ```bash
   # Install from requirements.txt and pyproject.toml
   pip install -r requirements.txt
   pip install -e .
   ```

3. **Configure Wallet**
   - Download and install Phantom Wallet
   - Import your wallet key into the `.env` file
   - Set the `PAYER_HASH` field in the `.env` file with your wallet's private key

4. **Configure Helius RPC**
   - Sign up for a Helius RPC node
   - Update the following fields in your configuration:
     - `HTTP_RPC_URI`
     - `WSS_RPC_URI`

## Running the Application

1. Start the application:
   ```bash
   python main_gui.py
   ```

2. **Using the Platform**

   a. **GMGN Token View**
   - Navigate to the GMGN section to view available tokens
   ![GMGN Token View](path_to_gmgn_image.png)

   b. **Balance Check**
   - View your Solana balance in the TraDeFi interface
   ![Balance View](path_to_balance_image.png)

   c. **Trading**
   - Execute buy and sell orders through the intuitive interface
   ![Trading Interface](path_to_trading_image.png)

   d. **AI Agent**
   - Utilize the AI agent for trading assistance and market analysis
   ![AI Agent](path_to_ai_agent_image.png)

## Security Notes

- Never share your private keys or `.env` file
- Keep your Phantom Wallet secure
- Regularly backup your wallet credentials

## Support

For any issues or questions, please open an issue in the repository.

## License

This is a private project. All rights reserved.

Copyright (c) 2025 TraDeFi. Unauthorized copying, distribution, or use of this project, via any medium, is strictly prohibited.
