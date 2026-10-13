from crewai import Agent
from langchain_openai import OpenAI
import json
from models.schemas import PolicyResult, PolicyClause, DisputeType

class PolicyAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0)
    
    def get_relevant_policies(self, dispute_type: DisputeType, evidence: dict) -> PolicyResult:
        policy_map = {
    DisputeType.FRAUD: [
        {
            "id": "clause_21",
            "summary": """
1. Transaction Verification & Customer Statement

I reviewed the disputed transaction against the customer’s account activity and statement.

The customer reported that the charge was fraudulent (unauthorized), and the claim aligns with the statement (e.g., “I never made this transaction”).

Supporting evidence indicates unusual transaction patterns, inconsistent merchant category, or transactions outside the customer’s geographic usage.

🔹 2. Merchant Documentation Review

The merchant failed to provide valid authorization proof (no signed slip, weak authentication, or mismatched IP/device details). 

Absence of such documentation indicates the charge was not genuinely authorized by the customer.

🔹 3. Compliance with Regulatory & Card Network Rules

Card network guidelines (e.g., Visa, Mastercard Zero Liability Policy) and RBI/Regulatory norms require customer protection against fraudulent charges.

Refund is mandated when a transaction is proven or reasonably suspected to be fraudulent.

🔹 4. Risk & Customer Protection Consideration

Protecting customers from fraudulent activity preserves trust and meets compliance obligations.

Issuing a refund mitigates financial loss and reduces reputational risk for the bank.

✅ Conclusion
Based on fraud analysis, lack of valid merchant proof, and regulatory requirements, I recommend refunding the disputed transaction and initiating chargeback recovery where applicable.
"""
        }
    ],
    DisputeType.BILLING_ERROR: [
        {
            "id": "clause_12",
            "summary": """
1. Transaction Verification & Customer Statement

I compared the disputed charge with the billing statement and customer’s explanation.

The customer identified a billing error (e.g., incorrect amount, currency mismatch, wrong fee application), which is consistent with transaction logs.

🔹 2. Merchant Documentation Review

The merchant failed to reconcile the billed amount with the actual service or product provided.

Documentation shows discrepancies between agreed charges and the posted transaction.

🔹 3. Compliance with Regulatory & Card Network Rules

As per card network and RBI guidelines, billing errors must be corrected within 90 days of the transaction.

Banks are obligated to refund erroneous charges once verified.

🔹 4. Risk & Customer Protection Consideration

Correcting billing errors reinforces fair banking practices and prevents future disputes.

Refunding ensures compliance and strengthens customer trust.

✅ Conclusion
Given the verified discrepancy and regulatory obligations, I recommend refunding the overcharged/incorrect billed amount and recovering it from the merchant where applicable.
"""
        }
    ],
    DisputeType.DUPLICATE_CHARGE: [
        {
            "id": "clause_15",
            "summary": """
1. Transaction Verification & Customer Statement

I reviewed the disputed transaction against the customer’s account activity and statement.

The customer reported that the charge was unauthorized / incorrect, and the claim aligns with the provided statement (e.g., “I didn’t make this booking”).

Supporting evidence shows the transaction does not match the customer’s usual spending pattern or known merchants.

🔹 2. Merchant Documentation Review

I assessed the merchant-provided documentation (invoice/receipt/authorization logs).

The merchant failed to provide sufficient proof of customer authorization (no valid signed receipt, no 3D secure authentication, or mismatched IP/device details).

As per banking dispute guidelines, the absence of valid merchant proof strengthens the customer’s claim.

🔹 3. Compliance with Regulatory & Card Network Rules

The case falls under the defined chargeback categories (e.g., fraudulent transaction, duplicate billing, or services not rendered).

Card network and RBI/Regulatory guidelines support issuing a refund when merchant proof is inadequate or the transaction is unauthorized.

🔹 4. Risk & Customer Protection Consideration

Protecting customers from unauthorized or disputed charges helps maintain trust and complies with consumer protection laws.

Refunding this transaction reduces reputational and legal risk for the bank.

✅ Conclusion
Based on transaction analysis, merchant response, and regulatory compliance, the evidence supports the customer’s claim. I recommend issuing a refund to the customer and pursuing chargeback recovery from the merchant where applicable.
"""
        }
    ],
    DisputeType.SUBSCRIPTION: [
        {
            "id": "clause_32",
            "summary": """
1. Transaction Verification & Customer Statement

I reviewed the subscription billing records and the customer’s cancellation request.

The customer requested cancellation prior to the renewal date, but charges were still applied for the next billing cycle.

Supporting evidence confirms the cancellation was submitted within the permitted timeframe.

🔹 2. Merchant Documentation Review

The merchant failed to provide evidence of continued service delivery or customer consent to renew.

No valid proof exists of the customer accepting the new billing period.

🔹 3. Compliance with Regulatory & Card Network Rules

Consumer protection and card network policies require refunds for services not used when timely cancellation is requested.

Regulations mandate merchants to honor cancellations and refund unused subscription fees.

🔹 4. Risk & Customer Protection Consideration

Refunding unused subscription charges prevents unfair financial burden and enhances customer confidence in the bank.

Failure to act could expose the bank to compliance issues and reputational damage.

✅ Conclusion
Given the valid cancellation evidence and regulatory obligations, I recommend refunding the unused portion of the subscription fee and initiating chargeback recovery if applicable.
"""
        }
    ],
    DisputeType.MERCHANT_DISPUTE: [
        {
            "id": "clause_45",
            "summary": """
1. Transaction Verification & Customer Statement

The customer reported non-receipt of goods/services despite being charged.

Account history and transaction details confirm the charge but show no delivery confirmation.

🔹 2. Merchant Documentation Review

The merchant failed to provide valid proof of delivery (e.g., signed delivery receipt, courier tracking with customer acknowledgment, or service usage logs).

Absence of such documentation weakens the merchant’s position and validates the customer’s claim.

🔹 3. Compliance with Regulatory & Card Network Rules

Card network and regulatory rules mandate refunds when goods or services are not delivered as promised.

Merchants must provide delivery evidence; failure to do so results in liability for refund.

🔹 4. Risk & Customer Protection Consideration

Protecting customers against undelivered services prevents financial harm and reinforces the bank’s role as a trusted financial institution.

Refund issuance avoids regulatory penalties and preserves goodwill.

✅ Conclusion
As the merchant cannot prove delivery, I recommend issuing a full refund to the customer and pursuing chargeback recovery from the merchant.
"""
        }
    ]
}

        
        # Return policies based on dispute type
        policies = policy_map.get(dispute_type, [
            {"id": "clause_default", "summary": "Review case manually for appropriate resolution"}
        ])
        
        clauses = [PolicyClause(**policy) for policy in policies]
        return PolicyResult(clauses=clauses)