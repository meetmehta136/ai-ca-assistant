import requests
import os
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")

# Map your trained model's categories to GST ITC rules
CATEGORY_MAP = {
    "Food":        {"blocked": True,  "reason": "Section 17(5)(b) — food/beverages"},
    "Vehicle":     {"blocked": True,  "reason": "Section 17(5)(a) — motor vehicle personal use"},
    "Clothing":    {"blocked": True,  "reason": "Section 17(5) — personal use apparel"},
    "Electronics": {"blocked": False, "reason": "Capital goods — fully eligible"},
    "Office":      {"blocked": False, "reason": "Office supplies — fully eligible"},
    "Pharma":      {"blocked": False, "reason": "Business use — eligible"},
    "Travel":      {"blocked": False, "reason": "Business travel — eligible"},
    "Other":       {"blocked": False, "reason": "Verify manually"},
}


def classify_invoice_description(description: str) -> dict:
    if not description or len(description.strip()) < 3:
        return {"category": "Other", "confidence": 0, "itc_blocked": False, "reason": "No description"}

    print(f"🧠 Classifying with VyapaarBandhu model: {description[:80]}")

    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # Use YOUR trained model
        response = requests.post(
            "https://router.huggingface.co/hf-inference/models/meet136/indicbert-gst-classifier",
            headers=headers,
            json={"inputs": description},
            timeout=30
        )

        print(f"📥 Model status: {response.status_code}")

        if response.status_code == 503:
            print("⏳ Model loading, using keyword fallback...")
            return classify_with_keywords(description)

        if response.status_code != 200:
            print(f"❌ Model error: {response.text[:200]}")
            return classify_with_keywords(description)

        result = response.json()

        # Text classification returns list of {label, score}
        if isinstance(result, list) and len(result) > 0:
            # Could be [[{label, score}]] or [{label, score}]
            items = result[0] if isinstance(result[0], list) else result
            top = max(items, key=lambda x: x["score"])
            top_label = top["label"]
            top_score = top["score"]
        else:
            return classify_with_keywords(description)

        category_info = CATEGORY_MAP.get(top_label, CATEGORY_MAP["Other"])
        print(f"✅ Category: {top_label} | Score: {top_score:.2f} | Blocked: {category_info['blocked']}")

        return {
            "category":    top_label,
            "confidence":  round(top_score, 3),
            "itc_blocked": category_info["blocked"],
            "reason":      category_info["reason"],
            "all_scores":  {item["label"]: round(item["score"], 3) for item in items[:3]}
        }

    except Exception as e:
        print(f"❌ Classification error: {e}")
        return classify_with_keywords(description)


def classify_with_keywords(description: str) -> dict:
    desc = description.lower()
    rules = [
        (["lunch", "dinner", "food", "meal", "restaurant", "catering", "bhojan", "khana", "chai", "nashta"], "Food"),
        (["laptop", "computer", "mobile", "phone", "monitor", "printer", "camera", "dell", "hp", "router"], "Electronics"),
        (["car", "bike", "scooter", "petrol", "diesel", "vehicle", "gaadi", "automobile"], "Vehicle"),
        (["hotel", "flight", "train", "travel", "ticket", "yatra", "bus"], "Travel"),
        (["medicine", "tablet", "pharma", "drug", "medical", "dawa", "chemist"], "Pharma"),
        (["shirt", "cloth", "uniform", "fabric", "textile", "garment", "kapda"], "Clothing"),
        (["paper", "pen", "stationery", "stapler", "file", "office", "furniture", "chair", "desk"], "Office"),
    ]
    for keywords, category in rules:
        if any(kw in desc for kw in keywords):
            info = CATEGORY_MAP[category]
            return {
                "category": category, "confidence": 0.85,
                "itc_blocked": info["blocked"],
                "reason": info["reason"] + " (keyword match)",
                "all_scores": {}
            }
    return {
        "category": "Other", "confidence": 0.60,
        "itc_blocked": False,
        "reason": "Could not classify — verify manually",
        "all_scores": {}
    }


def classify_invoice(invoice_fields: dict) -> dict:
    description = (
        invoice_fields.get("description", {}).get("value") or
        invoice_fields.get("item_name", {}).get("value") or
        invoice_fields.get("product", {}).get("value") or
        "Business purchase invoice"
    )

    result = classify_invoice_description(description)

    total_tax = (
        (invoice_fields.get("cgst", {}).get("value") or 0) +
        (invoice_fields.get("sgst", {}).get("value") or 0) +
        (invoice_fields.get("igst", {}).get("value") or 0)
    )

    itc_eligible = 0 if result["itc_blocked"] else total_tax
    itc_blocked  = total_tax if result["itc_blocked"] else 0

    result["total_tax"]    = round(total_tax, 2)
    result["itc_eligible"] = round(itc_eligible, 2)
    result["itc_blocked"]  = round(itc_blocked, 2)

    return result