from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["procurement"]
collection = db["orders"]

for doc in collection.find():
    price_str = doc.get("Total Price", "0").replace("$", "").replace(",", "")
    
    try:
        price = float(price_str)
    except:
        price = 0

    collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"total_price_clean": price}}
    )

print("Done cleaning prices!")