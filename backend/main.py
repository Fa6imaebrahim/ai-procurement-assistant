from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pymongo import MongoClient
from fastapi.encoders import jsonable_encoder
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from datetime import datetime
import json
import re

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = MongoClient("mongodb://localhost:27017/")
db = client["procurement"]
collection = db["orders"]

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, timeout=30)

@app.get("/")
def home():
    return {"message": "AI Procurement Assistant Backend is running"}

@app.get("/sample")
def sample_data():
    sample = collection.find_one({}, {"_id": 0})
    return sample

def rule_based_pipeline(question: str):
    q = question.lower()

    if "total spending" in q:
        return [
            {"$group": {"_id": None, "total_spending": {"$sum": "$total_price_clean"}}}
        ]

    if "top 5 suppliers" in q or "top suppliers" in q:
        return [
            {"$group": {"_id": "$Supplier Name", "total_spending": {"$sum": "$total_price_clean"}}},
            {"$sort": {"total_spending": -1}},
            {"$limit": 5}
        ]

    if "most frequent item" in q or "most common item" in q:
        return [
            {"$group": {"_id": "$Item Name", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]

    if "how many orders" in q or "number of orders" in q:
        return [
            {"$count": "total_orders"}
        ]

    if "highest spending quarter" in q:
        return [
            {
                "$addFields": {
                    "quarter": {
                        "$concat": [
                            {"$toString": {"$year": "$Creation Date"}},
                            "-Q",
                            {"$toString": {"$ceil": {"$divide": [{"$month": "$Creation Date"}, 3]}}}
                        ]
                    }
                }
            },
            {"$group": {"_id": "$quarter", "total_spending": {"$sum": "$total_price_clean"}}},
            {"$sort": {"total_spending": -1}},
            {"$limit": 1}
        ]
    if "orders in 2013" in q:
        return [
            {
                "$match": {
                    "Creation Date": {
                        "$gte": datetime(2013, 1, 1),
                        "$lt": datetime(2014, 1, 1)
                    }
                }
            },
            {
                "$count": "total_orders"
            }
        ]

    return None

def clean_llm_json(text: str):
    text = text.strip()
    text = re.sub(r"```json|```", "", text).strip()
    return json.loads(text)

def make_answer(question, result):
    q = question.lower()

    if not result:
        return "No matching results were found."

    #Orders in year
    if "orders in 2013" in q:
        total = result[0].get("total_orders", 0)
        return f"There were {total:,} orders created in 2013."

    #Total spending
    if "total" in q and "spending" in q:
        total = (
            result[0].get("total_spending")
            or result[0].get("totalSpending")
            or result[0].get("total")
            or 0
        )
        return f"The total spending is ${total:,.2f}."

    #Top suppliers
    if "top" in q and "supplier" in q:
        lines = [
            f"{i+1}. {r.get('_id', 'Unknown')} — ${r.get('total_spending', 0):,.2f}"
            for i, r in enumerate(result)
        ]
        return "The top suppliers by spending are:\n" + "\n".join(lines)

    #Frequent items
    if "frequent item" in q or "common item" in q:
        lines = [
            f"{i+1}. {r.get('_id', 'Unknown')} — {r.get('count', 0)} orders"
            for i, r in enumerate(result)
        ]
        return "The most frequent ordered items are:\n" + "\n".join(lines)

    #Number of orders
    if "how many orders" in q or "number of orders" in q:
        total_orders = result[0].get("total_orders", 0)
        return f"There are {total_orders:,} orders in the dataset."

    #Quarter analysis
    if "quarter" in q:
        lines = []
        for i, r in enumerate(result):
            period = r.get("_id", "Unknown")
            total = r.get("total_spending", 0)
            lines.append(f"{i+1}. {period} — ${total:,.2f}")
        return "The top spending quarters are:\n" + "\n".join(lines)

    #Department (LLM case)
    if "department" in q:
     lines = []
    for i, r in enumerate(result):
        dept = r.get("_id", "Unknown")
        total = (
            r.get("total_spending")
            or r.get("totalSpending")
            or r.get("total")
            or 0
        )
        lines.append(f"{i+1}. {dept} — ${total:,.2f}")

    return "Departments by spending:\n" + "\n".join(lines)

    #DEFAULT (for any new LLM query)
    first = result[0]

    if isinstance(first, dict):
        lines = []
        for key, value in first.items():
            if key == "_id":
                lines.append(f"Category: {value}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key}: {value:,.2f}")
            else:
                lines.append(f"{key}: {value}")

        return "Here is the result:\n" + "\n".join(lines)

    return f"I found {len(result)} result(s)."


@app.post("/ask")
def ask(question: str):
    pipeline = rule_based_pipeline(question)

    if pipeline is not None:
        source = "Rule-based"
    else:
        try:
            prompt = f"""
You are an AI procurement assistant and MongoDB expert.

Convert the user's natural language question into a MongoDB aggregation pipeline.

Return ONLY a valid JSON array.

Collection name: orders

Available fields:
- Creation Date
- Fiscal Year
- Supplier Name
- Department Name
- Item Name
- Item Description
- Quantity
- total_price_clean

Rules:
- Fiscal Year is stored as a string, for example "2013".
- Use total_price_clean for spending calculations.
- For counting orders, use $count.

User question:
{question}
"""
            llm_response = llm.invoke(prompt)
            pipeline = clean_llm_json(llm_response.content)
            source = "LLM"

        except Exception:
            return {
                "question": question,
                "answer": "Sorry, I could not generate a query for this question yet.",
                "source": "Error"
            }

    result = list(collection.aggregate(pipeline))
    answer = make_answer(question, result)

    return jsonable_encoder({
        "question": question,
        "answer": answer,
        "source": source,
        "pipeline": pipeline,
        "result": result
    })