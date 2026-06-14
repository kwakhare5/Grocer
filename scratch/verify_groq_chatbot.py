import httpx
import json
import asyncio

async def test_flow():
    print("Step 1: Triggering restock check to ensure active items...")
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("http://127.0.0.1:8000/api/restock/demo_user_001/check-now")
        print("Check-now status:", r.status_code)
        print("Check-now response:", r.json())
        
        # Step 2: Send "skip the amul milk!" (punctuation + amul milk matched)
        print("\nStep 2: Sending 'skip the amul milk!'...")
        payload = {
            "phone": "+9876543210",
            "message": "skip the amul milk!"
        }
        r = await client.post("http://127.0.0.1:8000/api/webhook/whatsapp", json=payload)
        print("Webhook status:", r.status_code)
        print("Response payload:")
        print(json.dumps(r.json(), indent=2))
        
        # Step 3: Send "add tomato?" (punctuation + singular match)
        print("\nStep 3: Sending 'add tomato?'...")
        payload = {
            "phone": "+9876543210",
            "message": "add tomato?"
        }
        r = await client.post("http://127.0.0.1:8000/api/webhook/whatsapp", json=payload)
        print("Webhook status:", r.status_code)
        print("Response payload:")
        print(json.dumps(r.json(), indent=2))
        
        # Step 4: Send "CONFIRM" to place order
        print("\nStep 4: Sending 'CONFIRM'...")
        payload = {
            "phone": "+9876543210",
            "message": "CONFIRM"
        }
        r = await client.post("http://127.0.0.1:8000/api/webhook/whatsapp", json=payload)
        print("Webhook status:", r.status_code)
        print("Response payload:")
        print(json.dumps(r.json(), indent=2))

        # Step 5: Send "CONFIRM" again to check done stage handling
        print("\nStep 5: Sending 'CONFIRM' again after checkout...")
        payload = {
            "phone": "+9876543210",
            "message": "CONFIRM"
        }
        r = await client.post("http://127.0.0.1:8000/api/webhook/whatsapp", json=payload)
        print("Webhook status:", r.status_code)
        print("Response payload:")
        print(json.dumps(r.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(test_flow())
