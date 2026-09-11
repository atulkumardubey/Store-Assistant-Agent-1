import json
import os
from datetime import datetime, timedelta
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(filename: str) -> dict:
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def check_stock(
    product_name: str,
    quantity: int,
    color: Optional[str] = None,
    size: Optional[str] = None,
) -> dict:
    inventory = _load("inventory.json")
    products = inventory["products"]

    product_name = product_name.lower().strip()
    color = color.lower().strip() if color else None
    size = size.upper().strip() if size else None

    matches = []
    for p in products:
        name_match = (
            product_name in p["category"].lower()
            or product_name in p["name"].lower()
            or p["category"].lower() in product_name
        )
        if not name_match:
            continue
        if color and color not in p["color"].lower():
            continue
        if size and size != p["size"].upper():
            continue
        matches.append(p)

    if not matches:
        desc = product_name
        if color:
            desc = f"{color} {desc}"
        if size:
            desc = f"{desc} (size {size})"
        return {
            "success": False,
            "available": False,
            "message": f"No products found matching: {desc}",
            "alternatives": [],
        }

    available = [p for p in matches if p["stock"] >= quantity]
    low_stock = [p for p in matches if 0 < p["stock"] < quantity]
    out_of_stock = [p for p in matches if p["stock"] == 0]

    if available:
        best = available[0]
        return {
            "success": True,
            "available": True,
            "product_id": best["id"],
            "product_name": best["name"],
            "color": best["color"],
            "size": best["size"],
            "stock": best["stock"],
            "requested_quantity": quantity,
            "unit_price": best["unit_price"],
            "message": (
                f"{best['name']} (Size: {best['size']}) is available. "
                f"{best['stock']} units in stock."
            ),
        }

    if low_stock:
        p = low_stock[0]
        return {
            "success": False,
            "available": False,
            "message": (
                f"{p['name']} (Size: {p['size']}) has only {p['stock']} units — "
                f"not enough for your request of {quantity}."
            ),
            "requested_quantity": quantity,
            "in_stock": p["stock"],
            "alternatives": [
                {"product_id": q["id"], "name": q["name"], "size": q["size"], "stock": q["stock"]}
                for q in available[:3]
            ],
        }

    return {
        "success": False,
        "available": False,
        "message": (
            f"{matches[0]['name']} in size {size or 'requested'} is currently out of stock."
        ),
        "requested_quantity": quantity,
        "alternatives": [
            {"product_id": p["id"], "name": p["name"], "size": p["size"], "stock": p["stock"]}
            for p in matches
            if p["stock"] > 0
        ][:3],
    }


def price_order(
    product_id: str,
    quantity: int,
    customer_type: str = "regular",
) -> dict:
    inventory = _load("inventory.json")
    discounts = _load("discounts.json")

    product = next((p for p in inventory["products"] if p["id"] == product_id), None)
    if not product:
        return {"success": False, "message": f"Product '{product_id}' not found."}

    unit_price = product["unit_price"]
    subtotal = unit_price * quantity

    bulk_discount = 0
    for rule in discounts["bulk_discounts"]:
        if quantity >= rule["min_quantity"]:
            if rule["max_quantity"] is None or quantity <= rule["max_quantity"]:
                bulk_discount = rule["discount_percent"]
                break

    category_discount = 0
    for rule in discounts.get("category_discounts", []):
        if rule["category"] == product["category"]:
            category_discount = rule["discount_percent"]
            break

    customer_discount = discounts["customer_discounts"].get(customer_type, 0)

    base_discount = max(bulk_discount, category_discount)
    total_discount = min(base_discount + customer_discount, 40)

    discount_amount = round(subtotal * total_discount / 100)
    total = subtotal - discount_amount

    breakdown = []
    if bulk_discount:
        breakdown.append(f"Bulk discount: {bulk_discount}%")
    if category_discount and category_discount > bulk_discount:
        breakdown.append(f"Category discount: {category_discount}%")
    if customer_discount:
        breakdown.append(f"Loyalty discount: {customer_discount}%")

    return {
        "success": True,
        "product_id": product_id,
        "product_name": product["name"],
        "quantity": quantity,
        "unit_price": unit_price,
        "subtotal": subtotal,
        "discount_percent": total_discount,
        "discount_amount": discount_amount,
        "total_price": total,
        "discount_breakdown": breakdown,
        "currency": "INR",
        "message": (
            f"{quantity}x {product['name']} = ₹{total:,} "
            f"(saved ₹{discount_amount:,} with {total_discount}% off)"
            if total_discount
            else f"{quantity}x {product['name']} = ₹{total:,}"
        ),
    }


def delivery_eta(pincode: str, product_id: str, quantity: int) -> dict:
    shipping = _load("shipping.json")

    pincode = pincode.strip()
    if not pincode.isdigit() or len(pincode) != 6:
        return {
            "success": False,
            "message": f"Invalid pincode '{pincode}'. Please provide a valid 6-digit Indian postal code.",
        }

    zone = None
    for z in shipping["zones"]:
        if pincode.startswith(z["pincode_prefix"]):
            zone = z
            break

    if not zone:
        zone = dict(shipping["default"])

    today = datetime.now().date()
    std_date = today + timedelta(days=zone["standard_days"])
    exp_date = today + timedelta(days=zone["express_days"])

    city = zone.get("city", "your location")
    state = zone.get("state", "India")

    return {
        "success": True,
        "pincode": pincode,
        "city": city,
        "state": state,
        "standard_delivery": {
            "date": std_date.strftime("%B %d, %Y"),
            "days": zone["standard_days"],
            "cost": zone["standard_cost"],
            "carrier": zone["carrier"],
        },
        "express_delivery": {
            "date": exp_date.strftime("%B %d, %Y"),
            "days": zone["express_days"],
            "cost": zone["express_cost"],
            "carrier": zone["carrier"],
        },
        "free_standard_shipping": zone["standard_cost"] == 0,
        "message": (
            "Delivery to {city}, {state} (PIN: {pincode}) | "
            "Standard: {std} via {carrier} ({cost}) | Express: {exp} (₹{exp_cost})".format(
                city=city, state=state, pincode=pincode,
                std=std_date.strftime("%b %d"), carrier=zone["carrier"],
                cost="FREE" if zone["standard_cost"] == 0 else f"₹{zone['standard_cost']}",
                exp=exp_date.strftime("%b %d"), exp_cost=zone["express_cost"],
            )
        ),
    }
