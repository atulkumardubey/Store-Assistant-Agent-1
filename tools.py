import json
import os
from datetime import datetime, timedelta
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load(filename: str) -> dict:
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def _find_alternatives(products: list, pname: str, quantity: int,
                       exclude_id: str = None) -> list:
    """Return up to 3 in-stock alternatives from the same category."""
    alts = []
    for p in products:
        if p["id"] == exclude_id:
            continue
        if p["stock"] < quantity:
            continue
        match = (
            pname in p["category"].lower()
            or pname in p["name"].lower()
            or p["category"].lower() in pname
        )
        if match:
            alts.append({
                "product_id": p["id"],
                "name":       p["name"],
                "color":      p["color"],
                "size":       p["size"],
                "stock":      p["stock"],
                "unit_price": p["unit_price"],
            })
    return alts[:3]


def check_stock(
    product_name: str,
    quantity: int,
    color: Optional[str] = None,
    size: Optional[str] = None,
) -> dict:
    inventory = _load("inventory.json")
    products  = inventory["products"]

    pname   = product_name.lower().strip()
    color_q = color.lower().strip() if color else None
    size_q  = size.upper().strip()  if size  else None

    # ── 1. Same category
    cat_matches = [
        p for p in products
        if pname in p["category"].lower()
        or pname in p["name"].lower()
        or p["category"].lower() in pname
    ]

    if not cat_matches:
        return {
            "success":    False,
            "available":  False,
            "message":    f"No products found in category '{product_name}'. "
                          f"Available categories: shirt, jeans, tshirt.",
            "alternatives": [],
        }

    # ── 2. Narrow by color
    color_matches = (
        [p for p in cat_matches if color_q in p["color"].lower()]
        if color_q else cat_matches
    )

    # ── 3. Narrow by size
    size_matches = (
        [p for p in color_matches if size_q == p["size"].upper()]
        if size_q else color_matches
    )

    # ── 4. Exact match exists?
    if size_matches:
        available = [p for p in size_matches if p["stock"] >= quantity]
        if available:
            best = available[0]
            return {
                "success":            True,
                "available":          True,
                "product_id":         best["id"],
                "product_name":       best["name"],
                "color":              best["color"],
                "size":               best["size"],
                "stock":              best["stock"],
                "requested_quantity": quantity,
                "unit_price":         best["unit_price"],
                "message":            (
                    f"{best['name']} (Size {best['size']}) is available — "
                    f"{best['stock']} units in stock at ₹{best['unit_price']:,} each."
                ),
            }

        # Exact color+size match but 0 / insufficient stock
        oos = size_matches[0]
        alts = _find_alternatives(products, pname, quantity, exclude_id=oos["id"])
        return {
            "success":            False,
            "available":          False,
            "message":            (
                f"'{oos['name']}' (Size {oos['size']}) is out of stock "
                f"(only {oos['stock']} unit(s) available, {quantity} requested)."
            ),
            "in_stock":           oos["stock"],
            "requested_quantity": quantity,
            "alternatives":       alts,
        }

    # ── 5. Color found but not that size
    if color_matches:
        in_stock_other_sizes = [p for p in color_matches if p["stock"] >= quantity]
        desc = f"{color_q} {product_name}" if color_q else product_name
        if size_q:
            desc += f" in size {size_q}"
        alts = [
            {"product_id": p["id"], "name": p["name"],
             "color": p["color"], "size": p["size"],
             "stock": p["stock"], "unit_price": p["unit_price"]}
            for p in in_stock_other_sizes
        ][:3]
        return {
            "success":    False,
            "available":  False,
            "message":    (
                f"'{desc.title()}' is not available, "
                f"but {len(alts)} similar item(s) found."
                if alts else
                f"'{desc.title()}' is not available and no alternatives are in stock."
            ),
            "alternatives": alts,
        }

    # ── 6. Category exists but not that color
    alts = _find_alternatives(products, pname, quantity)
    color_desc = f"{color_q} " if color_q else ""
    return {
        "success":    False,
        "available":  False,
        "message":    (
            f"No {color_desc}{product_name} is in stock. "
            f"{len(alts)} alternative(s) available."
        ),
        "alternatives": alts,
    }


def price_order(
    product_id: str,
    quantity: int,
    customer_type: str = "regular",
) -> dict:
    try:
        inventory = _load("inventory.json")
        discounts = _load("discounts.json")
    except Exception as e:
        return {"success": False, "message": f"Data load error: {e}"}

    product = next((p for p in inventory["products"] if p["id"] == product_id), None)
    if not product:
        return {"success": False, "message": f"Product ID '{product_id}' not found."}

    unit_price = product["unit_price"]
    subtotal   = unit_price * quantity

    bulk_discount = 0
    for rule in discounts["bulk_discounts"]:
        if quantity >= rule["min_quantity"]:
            if rule["max_quantity"] is None or quantity <= rule["max_quantity"]:
                bulk_discount = rule["discount_percent"]
                break

    cat_discount = next(
        (r["discount_percent"] for r in discounts.get("category_discounts", [])
         if r["category"] == product["category"]),
        0
    )
    loyalty_discount = discounts["customer_discounts"].get(customer_type, 0)

    base_discount  = max(bulk_discount, cat_discount)
    total_discount = min(base_discount + loyalty_discount, 40)

    discount_amount = round(subtotal * total_discount / 100)
    total           = subtotal - discount_amount

    breakdown = []
    if bulk_discount:
        breakdown.append(f"Bulk {quantity}+ items: {bulk_discount}%")
    if cat_discount and cat_discount > bulk_discount:
        breakdown.append(f"Category '{product['category']}': {cat_discount}%")
    if loyalty_discount:
        breakdown.append(f"Loyalty ({customer_type}): {loyalty_discount}%")

    return {
        "success":            True,
        "product_id":         product_id,
        "product_name":       product["name"],
        "quantity":           quantity,
        "unit_price":         unit_price,
        "subtotal":           subtotal,
        "discount_percent":   total_discount,
        "discount_amount":    discount_amount,
        "total_price":        total,
        "discount_breakdown": breakdown,
        "currency":           "INR",
        "message":            (
            f"{quantity}x {product['name']} = ₹{total:,} "
            f"(saved ₹{discount_amount:,} with {total_discount}% off)"
            if total_discount else
            f"{quantity}x {product['name']} = ₹{total:,} (no discount)"
        ),
    }


def delivery_eta(pincode: str, product_id: str, quantity: int) -> dict:
    try:
        shipping = _load("shipping.json")
    except Exception as e:
        return {"success": False, "message": f"Shipping data error: {e}"}

    pincode = pincode.strip()
    if not pincode.isdigit():
        return {
            "success": False,
            "message": f"Invalid pincode '{pincode}' — must contain only digits.",
        }
    if len(pincode) != 6:
        return {
            "success": False,
            "message": (
                f"Invalid pincode '{pincode}' — Indian PIN codes are 6 digits "
                f"(got {len(pincode)} digits)."
            ),
        }

    zone = next((z for z in shipping["zones"] if pincode.startswith(z["pincode_prefix"])), None)
    if not zone:
        zone = dict(shipping["default"])

    today    = datetime.now().date()
    std_date = today + timedelta(days=zone["standard_days"])
    exp_date = today + timedelta(days=zone["express_days"])
    city     = zone.get("city", "your location")
    state    = zone.get("state", "India")

    return {
        "success":  True,
        "pincode":  pincode,
        "city":     city,
        "state":    state,
        "standard_delivery": {
            "date":    std_date.strftime("%B %d, %Y"),
            "days":    zone["standard_days"],
            "cost":    zone["standard_cost"],
            "carrier": zone["carrier"],
        },
        "express_delivery": {
            "date":    exp_date.strftime("%B %d, %Y"),
            "days":    zone["express_days"],
            "cost":    zone["express_cost"],
            "carrier": zone["carrier"],
        },
        "free_standard_shipping": zone["standard_cost"] == 0,
        "message": (
            "Delivery to {city}, {state} (PIN {pin}) | "
            "Standard: {std} via {carrier} ({cost}) | "
            "Express: {exp} (₹{exp_cost})"
        ).format(
            city=city, state=state, pin=pincode,
            std=std_date.strftime("%b %d"), carrier=zone["carrier"],
            cost="FREE" if zone["standard_cost"] == 0 else f"₹{zone['standard_cost']}",
            exp=exp_date.strftime("%b %d"), exp_cost=zone["express_cost"],
        ),
    }
