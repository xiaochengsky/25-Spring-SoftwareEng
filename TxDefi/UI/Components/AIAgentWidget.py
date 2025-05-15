import customtkinter as ctk
from openai import OpenAI
from typing import Callable
import threading
import json
import requests
import os
from dotenv import load_dotenv

class AIAgentWidget(ctk.CTkFrame):
    def __init__(self, parent, api_key: str = None):
        super().__init__(parent)
        self.api_key = api_key
        self.client = None
        load_dotenv()
        self.helius_api_key = "73a214ac-2752-4c4f-9e86-b767004cdc3c"
        self.setup_ui()
        
    def setup_ui(self):
        # Token address input (optional)
        self.token_frame = ctk.CTkFrame(self)
        self.token_frame.pack(side=ctk.TOP, pady=5, padx=5, fill=ctk.X)
        
        self.token_label = ctk.CTkLabel(self.token_frame, text="Token Address (Optional):")
        self.token_label.pack(side=ctk.LEFT, padx=5)
        self.token_entry = ctk.CTkEntry(self.token_frame, width=300, placeholder_text="Enter token address for analysis")
        self.token_entry.pack(side=ctk.LEFT, padx=5)
        
        # Question input
        self.question_entry = ctk.CTkEntry(self, width=300, placeholder_text="Ask any question...")
        self.question_entry.pack(side=ctk.TOP, pady=5, padx=5, fill=ctk.X)
        
        # Response display area with scrollbar
        self.response_frame = ctk.CTkFrame(self)
        self.response_frame.pack(side=ctk.TOP, pady=5, padx=5, fill=ctk.BOTH, expand=True)
        
        # Add clear button
        self.clear_button = ctk.CTkButton(
            self.response_frame, 
            text="Clear", 
            text_color="white",
            fg_color="#FF4B4B",
            hover_color="#FF0000",
            width=60,
            command=self._clear_response
        )
        self.clear_button.pack(side=ctk.TOP, padx=5, pady=2, anchor=ctk.E)
        
        # Create text widget with custom font and colors
        self.response_text = ctk.CTkTextbox(
            self.response_frame,
            width=300,
            height=200,
            font=("Consolas", 12),  # 使用等宽字体
            wrap="word"  # 自动换行
        )
        self.response_text.pack(side=ctk.TOP, pady=2, padx=5, fill=ctk.BOTH, expand=True)
        
        # Ask button with improved styling
        self.ask_button = ctk.CTkButton(
            self, 
            text="Ask AI", 
            text_color="white",
            fg_color="#4CAF50",  # 绿色
            hover_color="#45a049",
            width=120,
            height=32,
            command=self.ask_ai
        )
        self.ask_button.pack(side=ctk.TOP, pady=5, padx=5)
        
    def set_api_key(self, api_key: str):
        self.api_key = api_key
        if api_key:
            self.client = OpenAI(api_key=api_key)
            
    def get_token_info(self, token_address: str) -> dict:
        """获取代币基本信息"""
        try:
            if not self.helius_api_key:
                return {
                    "address": token_address,
                    "error": "Helius API key not found",
                    "message": "Please set HELIUS_API_KEY in .env file"
                }
                
            # 使用 Helius RPC 获取代币信息
            url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
            self._update_response(f"Fetching token info from: {url}\n")
            
            # 准备 JSON-RPC 请求
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAsset",
                "params": [token_address]
            }
            
            response = requests.post(url, json=payload)
            
            if response.status_code != 200:
                error_msg = f"Error response: {response.status_code} - {response.text}"
                self._update_response(error_msg + "\n")
                return {
                    "address": token_address,
                    "error": f"API request failed with status {response.status_code}",
                    "message": response.text
                }
                
            asset_data = response.json()
            if "error" in asset_data:
                error_msg = f"API error: {asset_data['error']}"
                self._update_response(error_msg + "\n")
                return {
                    "address": token_address,
                    "error": "API error",
                    "message": asset_data['error']
                }
                
            asset_data = asset_data.get('result', {})
            self._update_response("\nToken Asset Data:\n" + json.dumps(asset_data, indent=2) + "\n")
            
            # 获取代币供应量
            supply_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "getTokenSupply",
                "params": [token_address]
            }
            
            self._update_response(f"\nFetching supply info...\n")
            supply_response = requests.post(url, json=supply_payload)
            supply_data = supply_response.json().get('result', {}) if supply_response.status_code == 200 else {}
            self._update_response("\nToken Supply Data:\n" + json.dumps(supply_data, indent=2) + "\n")
            
            # 获取代币持有者信息
            holders_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "getTokenLargestAccounts",
                "params": [token_address]
            }
            
            self._update_response(f"\nFetching holders info...\n")
            holders_response = requests.post(url, json=holders_payload)
            holders_data = holders_response.json().get('result', {}).get('value', []) if holders_response.status_code == 200 else []
            self._update_response("\nToken Holders Data:\n" + json.dumps(holders_data[:5], indent=2) + "\n")
            
            # 获取代币交易历史
            tx_payload = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "getSignaturesForAddress",
                "params": [token_address, {"limit": 10}]
            }
            
            self._update_response(f"\nFetching recent transactions...\n")
            tx_response = requests.post(url, json=tx_payload)
            tx_data = tx_response.json().get('result', []) if tx_response.status_code == 200 else []
            self._update_response("\nRecent Transactions:\n" + json.dumps(tx_data, indent=2) + "\n")
            
            # 获取代币账户信息
            account_payload = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "getAccountInfo",
                "params": [token_address, {"encoding": "jsonParsed"}]
            }
            
            self._update_response(f"\nFetching account info...\n")
            account_response = requests.post(url, json=account_payload)
            account_data = account_response.json().get('result', {}) if account_response.status_code == 200 else {}
            self._update_response("\nAccount Info:\n" + json.dumps(account_data, indent=2) + "\n")
            
            token_info = {
                "address": token_address,
                "name": asset_data.get('name', 'Unknown'),
                "symbol": asset_data.get('symbol', 'Unknown'),
                "decimals": asset_data.get('decimals', 9),
                "supply": supply_data.get('value', {}).get('uiAmount', 'Unknown'),
                "holders": holders_data[:5],  # 只返回前5个持有者
                "metadata": asset_data.get('metadata', {}),
                "ownership": asset_data.get('ownership', {}),
                "royalty": asset_data.get('royalty', {}),
                "recent_transactions": tx_data,
                "account_info": account_data
            }
            
            self._update_response("\nFinal Token Info:\n" + json.dumps(token_info, indent=2) + "\n")
            
            return token_info
            
        except Exception as e:
            error_msg = f"\nError occurred: {str(e)}"
            self._update_response(error_msg + "\n")
            return {
                "address": token_address,
                "error": str(e),
                "message": "Error occurred while fetching token information"
            }
            
    def ask_ai(self):
        if not self.client:
            self.response_text.delete("1.0", ctk.END)
            self.response_text.insert("1.0", "Please set OpenAI API key first!")
            return
            
        token = self.token_entry.get()
        question = self.question_entry.get()
        
        if not question:
            self.response_text.delete("1.0", ctk.END)
            self.response_text.insert("1.0", "Please enter a question!")
            return
            
        # Disable button while processing
        self.ask_button.configure(state="disabled")
        
        # Run API call in separate thread
        threading.Thread(target=self._process_question, args=(token, question), daemon=True).start()
        
    def _process_question(self, token: str, question: str):
        try:
            # 根据是否有代币地址来决定使用不同的系统提示词
            if token:
                # 获取代币基本信息
                token_info = self.get_token_info(token)
                
                system_prompt = """You are an expert cryptocurrency trading assistant specializing in Solana tokens. 
                Analyze the provided token information and focus on:
                1. Token Distribution Analysis:
                   - Supply distribution among top holders
                   - Concentration risk assessment
                   - Liquidity analysis based on holder distribution
                
                2. Token Characteristics:
                   - Supply metrics and tokenomics
                   - Metadata and branding
                   - Technical implementation details
                
                3. Recent Activity:
                   - Transaction patterns
                   - Holder behavior
                   - Market activity indicators
                
                4. Risk Assessment:
                   - Ownership concentration
                   - Liquidity concerns
                   - Technical implementation risks
                
                Provide clear, data-driven insights and highlight any potential red flags or positive indicators."""
                
                user_prompt = f"""Token Address: {token}
                Token Info: {json.dumps(token_info, indent=2)}
                
                Question: {question}
                
                Please analyze this token based on the provided data and answer the question. Focus on concrete data points and patterns you can observe from the token information."""
            else:
                system_prompt = "You are a helpful trading assistant. Provide clear and accurate information about cryptocurrency trading."
                user_prompt = question
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            answer = response.choices[0].message.content
            
            # Update UI in main thread
            self.after(0, self._update_response, answer)
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.after(0, self._update_response, error_msg)
            
        finally:
            # Re-enable button
            self.after(0, lambda: self.ask_button.configure(state="normal"))
            
    def _clear_response(self):
        """清除响应文本框的内容"""
        self.response_text.delete("1.0", ctk.END)
        
    def _update_response(self, text: str):
        """更新响应文本框的内容，保留原有内容"""
        current_text = self.response_text.get("1.0", ctk.END)
        if current_text.strip():  # 如果当前有内容，添加分隔线
            self.response_text.insert(ctk.END, "\n" + "="*50 + "\n")
        self.response_text.insert(ctk.END, text)
        # 自动滚动到底部
        self.response_text.see(ctk.END) 