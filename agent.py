import json
import os
from typing import Callable, Awaitable
from openai import AsyncOpenAI
from dotenv import load_dotenv

from tools import check_stock, price_order, delivery_eta

load_dotenv()

client = AsyncOpenAI(
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
)
MODEL = os.getenv("NVIDIA_LLM_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")

SYSTEM_PROMPT = """You are a helpful Store Assistant Agent for an Indian online fashion retail store.
Your job: help customers check stock, get pricing with discounts, and find delivery estimates.

When a customer makes a request, follow this order EVERY TIME:
1. call check_stock — verify availability and get the product_id
2. If available, call price_order — calculate total price with any discounts
3. call delivery_eta — estimate delivery to the customer's pincode
4. Give a friendly, concise summary with all three pieces of info

Rules:
- Always use all three tools in order: stock → price → delivery
- If stock check fails (out of stock), inform the customer and suggest alternatives
- Use ₹ (Indian Rupees) symbol for all prices
- Be warm but concise in the final answer
- If size or color is missing, use check_stock with what you have and report what's available
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": (
                "Check if a product is in stock. Returns availability, product_id, stock count, and unit price. "
                "Always call this FIRST before any other tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Product category or type (e.g. 'shirt', 'jeans', 'tshirt')",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of units the customer wants",
                    },
                    "color": {
                        "type": "string",
                        "description": "Product color, e.g. 'blue', 'red', 'black', 'white', 'gray'",
                    },
                    "size": {
                        "type": "string",
                        "description": "Product size, e.g. 'S', 'M', 'L', 'XL' for clothing or '30', '32', '34' for jeans",
                    },
                },
                "required": ["product_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "price_order",
            "description": (
                "Calculate total price for an order including bulk discounts. "
                "Call AFTER check_stock succeeds. Requires the product_id from check_stock."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "Product ID from the check_stock result (e.g. 'SHIRT-BLU-M')",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of units to order",
                    },
                    "customer_type": {
                        "type": "string",
                        "description": "Customer loyalty tier: 'regular' (default) or 'premium' (extra 5% off)",
                        "enum": ["regular", "premium"],
                    },
                },
                "required": ["product_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delivery_eta",
            "description": (
                "Get estimated delivery date and shipping options for a 6-digit Indian pincode. "
                "Call AFTER confirming stock availability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pincode": {
                        "type": "string",
                        "description": "6-digit Indian postal (PIN) code, e.g. '560001' for Bangalore",
                    },
                    "product_id": {
                        "type": "string",
                        "description": "Product ID from check_stock result",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items being ordered",
                    },
                },
                "required": ["pincode", "product_id", "quantity"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict) -> dict:
    try:
        if name == "check_stock":
            return check_stock(**args)
        elif name == "price_order":
            return price_order(**args)
        elif name == "delivery_eta":
            return delivery_eta(**args)
        return {"success": False, "message": f"Unknown tool: {name}"}
    except TypeError as e:
        return {"success": False, "message": f"Invalid arguments: {e}"}
    except Exception as e:
        return {"success": False, "message": f"Tool error: {e}"}


async def run_agent(query: str, send_event: Callable[[dict], Awaitable[None]]):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": query},
    ]
    max_steps = 12

    await send_event({"type": "status", "message": f"Sending to {MODEL}…"})

    for step in range(1, max_steps + 1):
        await send_event({"type": "status", "message": f"Agent reasoning (step {step})…"})

        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=4096,
                temperature=0.2,
            )
        except Exception as e:
            await send_event({"type": "error", "message": f"API error: {e}"})
            return

        choice  = response.choices[0]
        message = choice.message

        # Send any text the model included alongside tool calls (chain-of-thought)
        if message.content:
            await send_event({"type": "thinking", "text": message.content, "step": step})

        # Build assistant turn for history
        assistant_turn: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_turn["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]
        messages.append(assistant_turn)

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            for tc in message.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                await send_event({
                    "type": "tool_call",
                    "tool": name,
                    "input": args,
                    "step": step,
                })

                result = _execute_tool(name, args)

                await send_event({
                    "type": "tool_result",
                    "tool": name,
                    "result": result,
                    "success": result.get("success", True),
                    "step": step,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })

        elif choice.finish_reason in ("stop", "end_turn", "length"):
            final_text = message.content or ""
            await send_event({"type": "answer", "text": final_text, "step": step})
            return

        else:
            await send_event({
                "type": "error",
                "message": f"Unexpected finish_reason: {choice.finish_reason}",
            })
            return

    await send_event({"type": "error", "message": "Agent reached maximum steps."})
