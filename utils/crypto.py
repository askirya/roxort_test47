import aiohttp
import hashlib
import hmac
from typing import Optional, Dict, Any
from config import (
    CRYPTO_BOT_TOKEN,
    CRYPTO_BOT_API_URL,
    CRYPTO_MIN_AMOUNT,
    CRYPTO_CURRENCY,
    CRYPTO_NETWORK
)

class CryptoBot:
    def __init__(self):
        self.token = CRYPTO_BOT_TOKEN
        self.api_url = CRYPTO_BOT_API_URL

    async def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Выполняет запрос к API CryptoBot"""
        url = f"{self.api_url}/{method}"
        headers = {"Crypto-Pay-API-Token": self.token}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=params, headers=headers) as response:
                return await response.json()

    def verify_signature(self, data: Dict[str, Any], signature: str) -> bool:
        """Проверяет подпись уведомления от CryptoBot"""
        sorted_items = sorted(data.items())
        message = "\n".join(f"{k}={v}" for k, v in sorted_items)
        hmac_obj = hmac.new(
            self.token.encode(),
            message.encode(),
            hashlib.sha256
        )
        return hmac_obj.hexdigest() == signature

    async def create_invoice(
        self,
        amount: float,
        description: str,
        paid_btn_name: str = "Вернуться в бот",
        paid_btn_url: str = "https://t.me/your_bot_username",
        payload: str = "",
        allow_comments: bool = False,
        expires_in: int = 3600  # 1 час
    ) -> Dict:
        """Создает инвойс для оплаты"""
        if amount < CRYPTO_MIN_AMOUNT:
            raise ValueError(f"Минимальная сумма пополнения: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}")

        params = {
            "asset": CRYPTO_CURRENCY,
            "amount": str(amount),
            "description": description,
            "paid_btn_name": paid_btn_name,
            "paid_btn_url": paid_btn_url,
            "payload": payload,
            "allow_comments": allow_comments,
            "expires_in": expires_in
        }
        
        return await self._make_request("createInvoice", params)

    async def transfer(
        self,
        user_id: int,
        amount: float,
        spend_id: str,
        comment: str = "Вывод средств"
    ) -> Dict:
        """Выполняет перевод средств пользователю"""
        if amount < CRYPTO_MIN_AMOUNT:
            raise ValueError(f"Минимальная сумма вывода: {CRYPTO_MIN_AMOUNT} {CRYPTO_CURRENCY}")

        params = {
            "user_id": user_id,
            "asset": CRYPTO_CURRENCY,
            "amount": str(amount),
            "spend_id": spend_id,
            "comment": comment
        }
        
        return await self._make_request("transfer", params)

    async def get_balance(self) -> Dict:
        """Получает баланс бота"""
        return await self._make_request("getBalance")

    async def get_exchange_rates(self) -> Dict:
        """Получает курсы обмена"""
        return await self._make_request("getExchangeRates")

crypto_bot = CryptoBot() 