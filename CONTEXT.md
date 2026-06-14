# Instamart Intelligence Context

Instamart Intelligence is an AI household manager that sits on top of Swiggy Instamart, analyzing purchase patterns to predict and automate grocery restocking.

## Language

**Household**:
An inferred or declared unit of cohabiting users sharing pantry inventory and grocery ordering patterns.
_Avoid_: Account, family, customer

**Order**:
A completed grocery delivery transaction synced from Swiggy Instamart.
_Avoid_: Purchase, transaction, receipt

**Restock Alert**:
A proactive depletion warning sent to a household's registered contact method (e.g. WhatsApp) asking them to reorder items.
_Avoid_: Notification, message, depletion warning

**Consumption Model**:
The ML-generated forecast profile (using Facebook Prophet) modeling purchase intervals and standard daily consumption rates for a specific grocery item.
_Avoid_: Prediction, forecast profile

**Recipe Cart**:
A calculated bundle of missing grocery items derived by comparing recipe ingredients against a household's estimated pantry state.
_Avoid_: Meal plan cart, shopping list
