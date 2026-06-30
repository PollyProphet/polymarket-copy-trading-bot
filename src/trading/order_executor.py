"""
Order execution utilities for Polymarket trading.

Handles market and limit order creation and submission.
"""

import json
from typing import Dict, Any, Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType

from src.logger import log


class OrderExecutionError(Exception):
    """Order execution error exception."""
    pass


class OrderExecutor:
    """
    Handles order creation and execution for Polymarket trading.

    Supports both market and limit orders.
    """

    @staticmethod
    def _normalize_side(side: str) -> str:
        return side.upper()

    @staticmethod
    def _usdc_to_token_size(amount_usdc: float, price: float) -> float:
        """Convert a USDC notional into outcome token quantity."""
        if price <= 0:
            raise OrderExecutionError("Price must be greater than 0 to convert USDC to token size")
        return amount_usdc / price

    def __init__(self, clob_client: ClobClient, wallet_name: str = "Wallet", signature_type: int = 0):
        """
        Initialize order executor.

        Args:
            clob_client: Configured CLOB client instance
            wallet_name: Wallet name for logging
            signature_type: Signature type (0=EOA, 2=Proxy)
        """
        self.clob_client = clob_client
        self.name = wallet_name
        self.signature_type = signature_type

    def get_token_id(self, condition_id: str, outcome: str) -> Optional[str]:
        """
        Get token_id from condition_id and outcome.

        Args:
            condition_id: Market condition ID
            outcome: Outcome (YES/NO)

        Returns:
            token_id string, or None if not found

        Raises:
            OrderExecutionError: If unable to retrieve token_id
        """
        try:
            market_info = self.clob_client.get_market(condition_id)

            # Find token_id for the specified outcome
            if 'tokens' in market_info:
                for token in market_info['tokens']:
                    if token.get('outcome', '').upper() == outcome.upper():
                        return token.get('token_id')

            log.error(f"[{self.name}] No token_id found for outcome '{outcome}' in market info")
            return None

        except Exception as e:
            log.error(f"[{self.name}] Failed to get token_id: {e}")
            raise OrderExecutionError(f"Failed to get token_id: {e}")

    def execute_market_order(
        self,
        token_id: str,
        side: Any,
        amount: float,
        price: Optional[float] = None
    ) -> Dict:
        """
        Execute a market order.

        Args:
            token_id: Token ID
            side: Order side (BUY/SELL)
            amount: USDC notional for BUY orders; converted to token quantity for SELL
            price: Reference price used to convert USDC to token size for SELL orders

        Returns:
            Order response dictionary

        Raises:
            OrderExecutionError: If order execution fails
        """
        try:
            side = self._normalize_side(side)

            # py-clob-client: BUY amount is USDC, SELL amount is outcome token quantity
            if side == 'BUY':
                order_amount = amount
                amount_display = f"${amount:.2f} USDC"
            else:
                if price is None:
                    raise OrderExecutionError(
                        "SELL market orders require price to convert USDC notional to token size"
                    )
                order_amount = self._usdc_to_token_size(amount, price)
                amount_display = f"{order_amount:.4f} tokens (${amount:.2f} USDC @ {price})"

            market_order_args = MarketOrderArgs(
                token_id=token_id,
                amount=order_amount,
                side=side,
                order_type=OrderType.FOK  # Fill or Kill
            )

            signed_order = self.clob_client.create_market_order(market_order_args)
            response = self.clob_client.post_order(signed_order, OrderType.FOK)

            log.info(
                f"[{self.name}] Market order submitted | "
                f"token_id: {token_id} | "
                f"side: {side} | "
                f"amount: {amount_display}"
            )

            return response

        except OrderExecutionError:
            raise
        except Exception as e:
            log.error(f"[{self.name}] Market order execution failed: {e}")
            raise OrderExecutionError(f"Market order failed: {e}")

    def execute_limit_order(
        self,
        token_id: str,
        side: Any,
        amount_usdc: float,
        price: float
    ) -> Dict:
        """
        Execute a limit order.

        Args:
            token_id: Token ID
            side: Order side (BUY/SELL)
            amount_usdc: Target trade notional in USDC
            price: Limit price

        Returns:
            Order response dictionary

        Raises:
            OrderExecutionError: If order execution fails
        """
        try:
            side = self._normalize_side(side)
            token_size = self._usdc_to_token_size(amount_usdc, price)

            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=token_size,
                side=side
            )

            log.info(
                f"[{self.name}] Creating order parameters | "
                f"token_id: {token_id} | "
                f"side: {side} | "
                f"price: {price} | "
                f"size: {token_size:.4f} tokens (${amount_usdc:.2f} USDC) | "
                f"signature_type: {self.signature_type}"
            )

            signed_order = self.clob_client.create_order(order_args)

            log.info(f"[{self.name}] Signed order content:")
            log.info(json.dumps(signed_order, indent=2, default=str))

            response = self.clob_client.post_order(signed_order)

            log.info(
                f"[{self.name}] Limit order submitted | "
                f"token_id: {token_id} | "
                f"side: {side} | "
                f"price: {price} | "
                f"size: {token_size:.4f} tokens"
            )

            return response

        except OrderExecutionError:
            raise
        except Exception as e:
            log.error(f"[{self.name}] Limit order execution failed: {e}")
            raise OrderExecutionError(f"Limit order failed: {e}")

    def execute_order(
        self,
        condition_id: str,
        outcome: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = 'market'
    ) -> Dict:
        """
        Execute an order (market or limit) based on order_type.

        Args:
            condition_id: Market condition ID
            outcome: Outcome (YES/NO)
            side: Order side (BUY/SELL)
            amount: Order amount in USDC
            price: Limit price (required for limit orders)
            order_type: Order type ('market' or 'limit')

        Returns:
            Order response dictionary

        Raises:
            OrderExecutionError: If order execution fails
        """
        # Normalize side string
        side = self._normalize_side(side)

        # Get token_id
        token_id = self.get_token_id(condition_id, outcome)
        if not token_id:
            raise OrderExecutionError(
                f"Cannot get token_id: condition_id={condition_id}, outcome={outcome}"
            )

        if order_type == 'market':
            if side == 'SELL' and not price:
                raise OrderExecutionError(
                    "SELL market orders require price to convert USDC notional to token size"
                )
            return self.execute_market_order(token_id, side, amount, price=price)
        elif order_type == 'limit':
            if not price:
                raise OrderExecutionError("Limit order requires price parameter")
            return self.execute_limit_order(token_id, side, amount, price)
        else:
            raise OrderExecutionError(f"Unsupported order type: {order_type}")
