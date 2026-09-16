"""
15-request proof suite.
Runs the three-tool chain directly (no LLM) for determinism and speed.
Each test verifies: correct availability flag, discount tier, and delivery response.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools import check_stock, price_order, delivery_eta

# ── 15 test cases ─────────────────────────────────────────────────────────────
BATCH_TESTS = [
    # ── Happy-path (10) ──────────────────────────────────────────────────────
    {
        "id": 1,  "type": "happy",
        "label": "Blue Shirt M × 2 → Bangalore",
        "args":  {"product_name": "shirt",  "quantity": 2,  "color": "blue",  "size": "M"},
        "pin":   "560001",
        "expect_available": True, "expect_discount": 10,
        "note":  "Bulk 2+ = 10% off, FREE shipping",
    },
    {
        "id": 2,  "type": "happy",
        "label": "Red Shirt L × 1 → Mumbai",
        "args":  {"product_name": "shirt",  "quantity": 1,  "color": "red",   "size": "L"},
        "pin":   "400001",
        "expect_available": True, "expect_discount": 0,
        "note":  "Single item, no discount",
    },
    {
        "id": 3,  "type": "happy",
        "label": "White Shirt M × 5 → Delhi",
        "args":  {"product_name": "shirt",  "quantity": 5,  "color": "white", "size": "M"},
        "pin":   "110001",
        "expect_available": True, "expect_discount": 15,
        "note":  "Bulk 5+ = 15% off",
    },
    {
        "id": 4,  "type": "happy",
        "label": "White Shirt L × 10 → Bangalore",
        "args":  {"product_name": "shirt",  "quantity": 10, "color": "white", "size": "L"},
        "pin":   "560001",
        "expect_available": True, "expect_discount": 20,
        "note":  "Bulk 10+ = max 20% off",
    },
    {
        "id": 5,  "type": "happy",
        "label": "Blue Jeans 32 × 2 → Hyderabad",
        "args":  {"product_name": "jeans",  "quantity": 2,  "color": "blue",  "size": "32"},
        "pin":   "500001",
        "expect_available": True, "expect_discount": 10,
        "note":  "Jeans bulk discount",
    },
    {
        "id": 6,  "type": "happy",
        "label": "Black Jeans 30 × 1 → Chennai",
        "args":  {"product_name": "jeans",  "quantity": 1,  "color": "black", "size": "30"},
        "pin":   "600001",
        "expect_available": True, "expect_discount": 5,
        "note":  "Category discount 5% (jeans)",
    },
    {
        "id": 7,  "type": "happy",
        "label": "White T-Shirt M × 3 → Pune",
        "args":  {"product_name": "tshirt", "quantity": 3,  "color": "white", "size": "M"},
        "pin":   "411001",
        "expect_available": True, "expect_discount": 10,
        "note":  "T-shirt bulk discount",
    },
    {
        "id": 8,  "type": "happy",
        "label": "Gray T-Shirt M × 1 → Jaipur",
        "args":  {"product_name": "tshirt", "quantity": 1,  "color": "gray",  "size": "M"},
        "pin":   "302001",
        "expect_available": True, "expect_discount": 8,
        "note":  "Category discount 8% (tshirt)",
    },
    {
        "id": 9,  "type": "happy",
        "label": "Red Shirt M × 2 → Kolkata",
        "args":  {"product_name": "shirt",  "quantity": 2,  "color": "red",   "size": "M"},
        "pin":   "700001",
        "expect_available": True, "expect_discount": 10,
        "note":  "Paid shipping zone (₹49)",
    },
    {
        "id": 10, "type": "happy",
        "label": "Blue Shirt S × 1 → Lucknow",
        "args":  {"product_name": "shirt",  "quantity": 1,  "color": "blue",  "size": "S"},
        "pin":   "226001",
        "expect_available": True, "expect_discount": 0,
        "note":  "No discount, paid shipping",
    },
    # ── Out-of-stock (4) ──────────────────────────────────────────────────────
    {
        "id": 11, "type": "oos",
        "label": "Blue Shirt L × 2 (OOS)",
        "args":  {"product_name": "shirt",  "quantity": 2,  "color": "blue",  "size": "L"},
        "pin":   "560001",
        "expect_available": False,
        "note":  "L size = 0 stock → agent offers alternatives",
    },
    {
        "id": 12, "type": "oos",
        "label": "Black Shirt M × 1 (OOS)",
        "args":  {"product_name": "shirt",  "quantity": 1,  "color": "black", "size": "M"},
        "pin":   "400001",
        "expect_available": False,
        "note":  "Black M = 0 stock",
    },
    {
        "id": 13, "type": "oos",
        "label": "Blue Jeans 34 × 1 (OOS)",
        "args":  {"product_name": "jeans",  "quantity": 1,  "color": "blue",  "size": "34"},
        "pin":   "110001",
        "expect_available": False,
        "note":  "34 waist = 0 stock",
    },
    {
        "id": 14, "type": "oos",
        "label": "Black T-Shirt M × 1 (OOS)",
        "args":  {"product_name": "tshirt", "quantity": 1,  "color": "black", "size": "M"},
        "pin":   "560001",
        "expect_available": False,
        "note":  "Black T-Shirt M = 0 stock",
    },
    # ── Error-recovery (1) ───────────────────────────────────────────────────
    {
        "id": 15, "type": "error",
        "label": "Blue Shirt M × 1 → Bad PIN (99999)",
        "args":  {"product_name": "shirt",  "quantity": 1,  "color": "blue",  "size": "M"},
        "pin":   "99999",
        "expect_available":      True,
        "expect_discount":       0,
        "expect_delivery_error": True,
        "note":  "5-digit PIN → delivery_eta fails gracefully",
    },
]


def _run_single(test: dict) -> dict:
    steps = {}
    try:
        # ── Step 1: check_stock ───────────────────────────────────────────────
        s1       = check_stock(**test["args"])
        want_avail = test.get("expect_available", True)
        s1_pass  = s1.get("available", False) == want_avail
        steps["check_stock"] = {
            "passed":  s1_pass,
            "result":  s1["message"],
            "skipped": False,
        }

        # Out-of-stock tests stop here
        if not want_avail:
            # Bonus: check alternatives are returned
            alts = s1.get("alternatives", [])
            steps["check_stock"]["alts"] = len(alts)
            return {
                "id": test["id"], "label": test["label"],
                "type": test["type"], "note": test["note"],
                "passed": s1_pass,
                "steps": steps,
            }

        if not s1.get("available", False):
            steps["price_order"]   = {"passed": False, "result": "Skipped (unexpected OOS)", "skipped": True}
            steps["delivery_eta"]  = {"passed": False, "result": "Skipped", "skipped": True}
            return {
                "id": test["id"], "label": test["label"],
                "type": "unexpected-oos", "note": test["note"],
                "passed": False,
                "steps": steps,
            }

        product_id = s1["product_id"]

        # ── Step 2: price_order ───────────────────────────────────────────────
        s2 = price_order(product_id, test["args"]["quantity"])
        want_disc = test.get("expect_discount")
        s2_pass   = s2["success"]
        if want_disc is not None:
            s2_pass = s2_pass and s2.get("discount_percent") == want_disc
        steps["price_order"] = {
            "passed":  s2_pass,
            "result":  f"₹{s2.get('total_price', 0):,} ({s2.get('discount_percent', 0)}% off)",
            "skipped": False,
        }

        # ── Step 3: delivery_eta ──────────────────────────────────────────────
        s3 = delivery_eta(test["pin"], product_id, test["args"]["quantity"])
        want_err  = test.get("expect_delivery_error", False)
        s3_pass   = (not s3["success"]) if want_err else s3["success"]
        steps["delivery_eta"] = {
            "passed":  s3_pass,
            "result":  (
                f"[Expected error] {s3['message']}" if want_err
                else s3.get("standard_delivery", {}).get("date", s3.get("message", ""))[:50]
            ),
            "skipped": False,
        }

        overall = s1_pass and s2_pass and s3_pass

    except Exception as e:
        steps.setdefault("check_stock",  {"passed": False, "result": str(e), "skipped": False})
        steps.setdefault("price_order",  {"passed": False, "result": "—", "skipped": True})
        steps.setdefault("delivery_eta", {"passed": False, "result": "—", "skipped": True})
        overall = False

    return {
        "id": test["id"], "label": test["label"],
        "type": test["type"], "note": test["note"],
        "passed": overall,
        "steps": steps,
    }


def run_batch_test() -> dict:
    results = [_run_single(t) for t in BATCH_TESTS]
    passed  = sum(1 for r in results if r["passed"])
    return {
        "total":   len(results),
        "passed":  passed,
        "failed":  len(results) - passed,
        "results": results,
    }


if __name__ == "__main__":
    import json as _json
    out = run_batch_test()
    print(f"\n{'='*60}")
    print(f" BATCH TEST RESULTS: {out['passed']}/{out['total']} passed")
    print(f"{'='*60}")
    for r in out["results"]:
        icon = "✅" if r["passed"] else "❌"
        print(f" {icon} #{r['id']:2d}  {r['label']}")
        for step, info in r["steps"].items():
            if info.get("skipped"):
                print(f"        {step:15s} —  skipped")
            else:
                mark = "✓" if info["passed"] else "✗"
                print(f"        {mark} {step:15s} {info['result'][:55]}")
    print()
