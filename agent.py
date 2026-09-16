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

SYSTEM_PROMPT = """You are a Store Assistant Agent for an Indian online fashion retail store.

## Your Job
Help customers by checking stock, calculating prices with discounts, and quoting delivery dates.

## Tool Order — ALWAYS follow this sequence:
1. **check_stock** — FIRST, verify availability. Get the product_id.
2. **price_order** — SECOND (only if stock check succeeded). Use the product_id from step 1.
3. **delivery_eta** — THIRD. Use the product_id from step 1 and the customer's pincode.
4. **Answer** — Summarise all three results in a friendly, concise message.

## Out-of-stock path:
- If check_stock returns available=false, DO NOT call price_order or delivery_eta.
- Report clearly what is out of stock.
- If check_stock returns alternatives, list them for the customer (name, size, stock count).
- Ask if they'd like to order an alternative.

## Tool-error path:
- If a tool returns success=false, report the specific error message to the customer.
- Do NOT retry the same call with identical inputs.
- If delivery_eta fails (e.g. invalid pincode), still report the stock and price you found, then explain the delivery issue and ask for a corrected pincode.

## Style:
- Use ₹ (Indian Rupees) for all prices.
- Be warm, concise, and helpful.
- Always include: availability, total price (with discount breakdown), and delivery date in your final answer.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": (
                "Check if a product is in stock. Returns availability, product_id, "
                "stock count, unit price, and alternatives if out-of-stock. "
                "ALWAYS call this first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "Product category: 'shirt', 'jeans', or 'tshirt'",
                    },
                    "quantity": {"type": "integer", "minimum": 1,
                                 "description": "Number of units requested"},
                    "color":   {"type": "string",
                                "description": "Color: 'blue', 'red', 'black', 'white', 'gray'"},
                    "size":    {"type": "string",
                                "description": "Size: 'S','M','L','XL' for shirts/tshirts; '30','32','34' for jeans"},
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
                "Calculate total price including bulk and loyalty discounts. "
                "Call AFTER check_stock succeeds. Requires product_id from check_stock."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id":    {"type": "string",
                                     "description": "product_id from check_stock (e.g. 'SHIRT-BLU-M')"},
                    "quantity":      {"type": "integer", "minimum": 1},
                    "customer_type": {"type": "string", "enum": ["regular", "premium"],
                                     "description": "'regular' (default) or 'premium' (+5% off)"},
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
                "Get delivery estimate for a 6-digit Indian pincode. "
                "Call AFTER confirming stock. Returns standard + express dates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pincode":    {"type": "string",
                                  "description": "6-digit Indian PIN code, e.g. '560001' for Bangalore"},
                    "product_id": {"type": "string"},
                    "quantity":   {"type": "integer", "minimum": 1},
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
        return {"success": False, "message": f"Unknown tool: '{name}'"}
    except TypeError as e:
        return {"success": False, "message": f"Bad arguments for '{name}': {e}"}
    except Exception as e:
        return {"success": False, "message": f"Tool '{name}' error: {e}"}


async def run_agent(query: str, send_event: Callable[[dict], Awaitable[None]]):
    messages  = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": query},
    ]
    max_steps = 12

    await send_event({"type": "status", "message": f"Sending to {MODEL}…"})

    for step in range(1, max_steps + 1):
        await send_event({"type": "status",
                          "message": f"Agent reasoning (step {step} / max {max_steps})…"})
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

        # Surface any visible chain-of-thought text
        if message.content:
            await send_event({"type": "thinking", "text": message.content, "step": step})

        # Build assistant history entry
        assistant_turn: dict = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            assistant_turn["tool_calls"] = [
                {
                    "id":   tc.id,
                    "type": "function",
                    "function": {
                        "name":      tc.function.name,
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
                    "type":    "tool_result",
                    "tool":    name,
                    "result":  result,
                    "success": result.get("success", True),
                    "step":    step,
                })

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      json.dumps(result),
                })

        elif choice.finish_reason in ("stop", "end_turn", "length"):
            await send_event({
                "type": "answer",
                "text": message.content or "",
                "step": step,
            })
            return

        else:
            await send_event({
                "type":    "error",
                "message": f"Unexpected finish_reason: {choice.finish_reason}",
            })
            return

    await send_event({"type": "error", "message": "Agent reached the maximum step limit."})
