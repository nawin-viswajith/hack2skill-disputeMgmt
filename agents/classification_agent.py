from crewai import Agent
from langchain_openai import OpenAI
import json
from models.schemas import DisputeType, ClassificationResult

class ClassificationAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0)
    
    def classify_dispute(self, customer_statement: str, transaction_evidence: dict) -> ClassificationResult:
        prompt = f"""
        You are a classification agent for dispute handling. 
        Given the following dispute details, classify the case:

        Customer Statement: "{customer_statement}"
        Transaction Evidence: {json.dumps(transaction_evidence)}

        Classify into one of: [Fraud, Billing Error, Duplicate Charge, Subscription, Merchant Dispute].

        Respond in JSON format with "type" and "confidence" fields.

        Example: {{"type": "Billing Error", "confidence": 0.94}}
        """
        
        try:
            response = self.llm(prompt)
            # Extract JSON from response
            if "{" in response and "}" in response:
                json_str = response[response.find("{"):response.rfind("}")+1]
                result = json.loads(json_str)
                
                # Map to enum
                dispute_type = None
                for dt in DisputeType:
                    if dt.value.lower() in result["type"].lower():
                        dispute_type = dt
                        break
                
                if not dispute_type:
                    dispute_type = DisputeType.MERCHANT_DISPUTE
                
                return ClassificationResult(
                    type=dispute_type,
                    confidence=float(result.get("confidence", 0.5))
                )
        except Exception as e:
            print(f"Classification error: {e}")
        
        # Fallback logic
        if "cancel" in customer_statement.lower():
            return ClassificationResult(type=DisputeType.SUBSCRIPTION, confidence=0.7)
        elif "not received" in customer_statement.lower() or "never received" in customer_statement.lower():
            return ClassificationResult(type=DisputeType.MERCHANT_DISPUTE, confidence=0.8)
        elif "not made" in customer_statement.lower() or "unauthorized" in customer_statement.lower():
            return ClassificationResult(type=DisputeType.FRAUD, confidence=0.75)
        elif "twice" in customer_statement.lower() or "duplicate" in customer_statement.lower():
            return ClassificationResult(type=DisputeType.DUPLICATE_CHARGE, confidence=0.85)
        else:
            return ClassificationResult(type=DisputeType.BILLING_ERROR, confidence=0.6)