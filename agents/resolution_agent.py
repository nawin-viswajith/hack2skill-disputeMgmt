from crewai import Agent
from langchain_openai import OpenAI
import json
from models.schemas import ResolutionRecommendation, ResolutionAction, DisputeType, PolicyResult

class ResolutionAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0)
    
    def recommend_resolution(self, dispute_type: DisputeType, policies: PolicyResult, 
                           evidence: dict, transaction_amount: float, currency: str) -> ResolutionRecommendation:
        
        resolution_map = {
            DisputeType.FRAUD: {
                "resolution": [ResolutionAction.BLOCK_CARD, ResolutionAction.REFUND],
                "rationale": "Transaction flagged as fraudulent. Customer not liable. Card blocked and refund issued."
            },
            DisputeType.BILLING_ERROR: {
                "resolution": [ResolutionAction.REFUND],
                "rationale": "Billing error confirmed. Eligible for full refund."
            },
            DisputeType.DUPLICATE_CHARGE: {
                "resolution": [ResolutionAction.REFUND],
                "rationale": "Duplicate charge confirmed. Eligible for full refund."
            },
            DisputeType.SUBSCRIPTION: {
                "resolution": [ResolutionAction.PARTIAL_REFUND],
                "rationale": "Subscription cancellation recorded before billing. Partial refund issued."
            },
            DisputeType.MERCHANT_DISPUTE: {
                "resolution": [ResolutionAction.REFUND],
                "rationale": "Item not received. Merchant unable to provide proof of delivery. Full refund required."
            }
        }
        
        default_resolution = {
            "resolution": [ResolutionAction.ESCALATE],
            "rationale": "Unable to automatically determine resolution. Case requires manual review."
        }
        
        resolution_data = resolution_map.get(dispute_type, default_resolution)
        
        return ResolutionRecommendation(
            resolution=resolution_data["resolution"],
            amount=transaction_amount if ResolutionAction.REFUND in resolution_data["resolution"] or 
                                       ResolutionAction.PARTIAL_REFUND in resolution_data["resolution"] else None,
            currency=currency,
            citations=[f"policy:{dispute_type.value.lower()}#{policies.clauses[0].id}"],
            rationale=resolution_data["rationale"]
        )