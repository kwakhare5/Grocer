import asyncio
import httpx
import json
import sys
from sqlalchemy import text
from backend.database.connection import AsyncSessionLocal

# Configure terminal to print UTF-8 characters cleanly on Windows
if sys.platform == "win32":
    getattr(sys.stdout, "reconfigure")(encoding='utf-8')

API_URL = "http://127.0.0.1:8000"

async def clear_alerts_in_db():
    """Clear restock alerts to bypass the 24-hour alert rate limiter."""
    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM restock_alerts"))
        await db.commit()

async def run_scenario(name, steps):
    print(f"\n=============================================================")
    print(f" RUNNING SCENARIO: {name}")
    print(f"=============================================================")
    
    async with httpx.AsyncClient(timeout=45.0) as client:
        # Clear alerts to ensure check-now finds items
        await clear_alerts_in_db()
        
        for step_idx, step in enumerate(steps, 1):
            method = step.get("method", "POST")
            endpoint = step.get("endpoint")
            payload = step.get("payload")
            desc = step.get("desc", f"Step {step_idx}")
            
            print(f"\n--> {desc} ({method} {endpoint})")
            if payload:
                print(f"Payload: {json.dumps(payload)}")
                
            try:
                if method == "POST":
                    r = await client.post(f"{API_URL}{endpoint}", json=payload)
                else:
                    r = await client.get(f"{API_URL}{endpoint}")
                
                print(f"Status: {r.status_code}")
                response_json = r.json()
                print("Response:")
                print(json.dumps(response_json, indent=2))
                
                # Verify key criteria
                expected = step.get("expect")
                if expected:
                    verify_success = True
                    for key, val in expected.items():
                        # Support checking nested response_message
                        actual_val = response_json
                        for k in key.split("."):
                            if isinstance(actual_val, dict):
                                actual_val = actual_val.get(k)
                        
                        if val.lower() in str(actual_val).lower():
                            print(f"  [PASS] Verify '{key}' contains '{val}'")
                        else:
                            print(f"  [FAIL] Verify '{key}' contains '{val}' (Actual: {actual_val})")
                            verify_success = False
                    if not verify_success:
                        print(f"Scenario '{name}' verification failed at {desc}")
                        return False
            except Exception as e:
                print(f"Error in step: {e}")
                return False
    print(f"--> [SUCCESS] Scenario '{name}' completed successfully.")
    return True

async def main():
    print("Starting chatbot deep testing suite...")
    
    # Define the 10 test scenarios
    scenarios = [
        # Scenario 1: Complete Approval
        {
            "name": "Scenario 1: Complete Approval (Confirm All)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check to log new pending alert",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000001", "message": "YES"},
                    "desc": "Send YES to reorder all items",
                    "expect": {"response_message": "Reply CONFIRM to place order"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000001", "message": "CONFIRM"},
                    "desc": "Send CONFIRM to place the order",
                    "expect": {"response_message": "Order placed!"}
                }
            ]
        },
        
        # Scenario 2: Complete Rejection
        {
            "name": "Scenario 2: Complete Rejection (Dismiss Alert)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000002", "message": "NO"},
                    "desc": "Send NO to reject order",
                    "expect": {"response_message": "I'll check again tomorrow"}
                }
            ]
        },
        
        # Scenario 3: Partial Confirmation
        {
            "name": "Scenario 3: Partial Confirmation (Restrict to specific items)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000003", "message": "just the milk and eggs!"},
                    "desc": "Send 'just the milk and eggs!'",
                    "expect": {
                        "response_message": "Cart ready",
                        "response_message": "Milk",
                        "response_message": "Eggs"
                    }
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000003", "message": "CONFIRM"},
                    "desc": "Confirm checkout of partial items",
                    "expect": {"response_message": "Order placed!"}
                }
            ]
        },
        
        # Scenario 4: Partial Rejection
        {
            "name": "Scenario 4: Partial Rejection (Exclude items)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000004", "message": "skip the milk?"},
                    "desc": "Send 'skip the milk?'",
                    "expect": {"response_message": "Cart ready"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000004", "message": "CONFIRM"},
                    "desc": "Confirm checkout",
                    "expect": {"response_message": "Order placed!"}
                }
            ]
        },
        
        # Scenario 5: Multi-turn edits
        {
            "name": "Scenario 5: Multi-turn edits (Skip first, then add item)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000005", "message": "skip milk!"},
                    "desc": "Send 'skip milk!'",
                    "expect": {"response_message": "Cart ready"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000005", "message": "add onion?"},
                    "desc": "Send 'add onion?'",
                    "expect": {
                        "response_message": "Cart ready",
                        "response_message": "Onion"
                    }
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000005", "message": "CONFIRM"},
                    "desc": "Confirm cart with updates",
                    "expect": {"response_message": "Order placed!"}
                }
            ]
        },
        
        # Scenario 6: Manual check request
        {
            "name": "Scenario 6: Manual check request ('check' command)",
            "steps": [
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000006", "message": "check"},
                    "desc": "Send 'check' to trigger depletion check manually",
                    "expect": {"response_message": "Running low"}
                }
            ]
        },
        
        # Scenario 7: Post-checkout protection
        {
            "name": "Scenario 7: Post-checkout protection (Done-stage safety)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000007", "message": "YES"},
                    "desc": "Send YES to reorder",
                    "expect": {"response_message": "Reply CONFIRM"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000007", "message": "CONFIRM"},
                    "desc": "Send CONFIRM to checkout",
                    "expect": {"response_message": "Order placed!"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000007", "message": "YES"},
                    "desc": "Send YES again after order is placed",
                    "expect": {"response_message": "order has already been placed successfully"}
                }
            ]
        },
        
        # Scenario 8: Singular/Plural and Punctuation Immunity
        {
            "name": "Scenario 8: Singular/Plural and Punctuation Immunity",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000008", "message": "skip eggs!"},
                    "desc": "Send 'skip eggs!'",
                    "expect": {"response_message": "Cart ready"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000008", "message": "add tomato?"},
                    "desc": "Send 'add tomato?'",
                    "expect": {
                        "response_message": "Cart ready",
                        "response_message": "Tomatoes"
                    }
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000008", "message": "CONFIRM"},
                    "desc": "Confirm",
                    "expect": {"response_message": "Order placed!"}
                }
            ]
        },
        
        # Scenario 9: Typos & Spelling Mistake Matching
        {
            "name": "Scenario 9: Typos & Spelling Mistake Matching",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000009", "message": "skip egs!"},
                    "desc": "Send 'skip egs!' (typo 'egs' -> 'eggs')",
                    "expect": {"response_message": "Cart ready"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000009", "message": "add tamato?"},
                    "desc": "Send 'add tamato?' (typo 'tamato' -> 'tomatoes')",
                    "expect": {
                        "response_message": "Cart ready",
                        "response_message": "Tomatoes"
                    }
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000009", "message": "add sunflour oil!"},
                    "desc": "Send 'add sunflour oil!' (typo 'sunflour' -> 'sunflower')",
                    "expect": {
                        "response_message": "Cart ready",
                        "response_message": "Sunflower"
                    }
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000009", "message": "CONFIRM"},
                    "desc": "Confirm cart with spelling matching",
                    "expect": {"response_message": "Order placed!"}
                }
            ]
        },
        
        # Scenario 10: Gibberish/Chit-chat Fallback
        {
            "name": "Scenario 10: Gibberish/Chit-chat Fallback (Ask clarification)",
            "steps": [
                {
                    "endpoint": "/api/restock/demo_user_001/check-now",
                    "desc": "Trigger restock check",
                    "expect": {"message": "item(s) depleting"}
                },
                {
                    "endpoint": "/api/webhook/whatsapp",
                    "payload": {"phone": "+910000000010", "message": "hello chatbot are you online right now?"},
                    "desc": "Send chit-chat message",
                    "expect": {"response_message": "didn't catch that"}
                }
            ]
        }
    ]
    
    passed_count = 0
    total_count = len(scenarios)
    
    for sc in scenarios:
        success = await run_scenario(sc["name"], sc["steps"])
        if success:
            passed_count += 1
            
    print(f"\n=============================================================")
    print(f" TEST RUN COMPLETED: {passed_count} / {total_count} SCENARIOS PASSED")
    print(f"=============================================================")

if __name__ == "__main__":
    asyncio.run(main())
