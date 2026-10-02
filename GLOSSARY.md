# GROCER shopping language

Terms used to describe a customer's grocery task across conversation and Swiggy commerce state.

## Language

**Customer**:
The verified WhatsApp sender who owns a GROCER shopping task and connects their own Swiggy account.
_Avoid_: Owner account, typed phone number

**Shopping task**:
The customer's current grocery request, including requested items, constraints, decisions, and destination. It can remain open across messages and provider changes.
_Avoid_: Chat turn, prompt

**Requested item**:
A grocery need stated or accepted by the customer. It remains part of the task until matched, substituted with disclosure, or explicitly removed.
_Avoid_: Search result

**Provider cart**:
The basket currently held by Swiggy, which may change outside GROCER. It is observed before review and checkout.
_Avoid_: GROCER memory

**Substitute**:
A different product selected for a requested item when the original is unavailable. It is disclosed before approval and cannot violate an explicit hard constraint.
_Avoid_: Silent replacement

**Approval**:
The customer's permission for one reviewed basket, destination, and payable total. A change to any of these requires a new review.
_Avoid_: Generic yes, model confirmation flag

**Unknown checkout outcome**:
A checkout attempt whose effect cannot yet be verified with Swiggy. It is distinct from a confirmed failure.
_Avoid_: Failed order, safe retry
