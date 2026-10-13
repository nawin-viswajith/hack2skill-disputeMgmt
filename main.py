from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
import json
import uuid
import os
import hashlib
from datetime import datetime
import secrets
from dotenv import load_dotenv

# Import agents
from agents.classification_agent import ClassificationAgent
from agents.policy_agent import PolicyAgent
from agents.resolution_agent import ResolutionAgent
from agents.document_analysis_agent import DocumentAnalysisAgent

# Load environment variables from .env (see .env.example for the template)
load_dotenv()

app = FastAPI(title="Agentic AI Dispute Handling System", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize agents
classification_agent = ClassificationAgent()
policy_agent = PolicyAgent()
resolution_agent = ResolutionAgent()
document_analysis_agent = DocumentAnalysisAgent()

# Simple password hashing
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

# User database
users_db = {
    "admin": {
        "username": "admin", 
        "password": hash_password("admin123"), 
        "full_name": "Administrator", 
        "role": "admin"
    },
    "agent1": {
        "username": "agent1", 
        "password": hash_password("Agent@123"), 
        "full_name": "Suraj Sutar", 
        "role": "agent"
    }
}

sessions = {}
cases_db = {}
transactions_db = {}
document_analyses_db = {}  # Store document analyses

os.makedirs("uploads", exist_ok=True)

def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    return sessions.get(session_id)

@app.on_event("startup")
async def startup_event():
    # Load sample data
    try:
        with open("data/sample_data.json", "r") as f:
            data = json.load(f)
            for item in data:
                transactions_db[item["transaction_id"]] = item
        print(f"Loaded {len(transactions_db)} sample transactions")
    except Exception as e:
        print(f"Error loading sample data: {e}")
        # Create some dummy data if file doesn't exist
        transactions_db["TXN30001"] = {
            "customer_id": "CUST1001", 
            "transaction_id": "TXN30001", 
            "amount": 100.0,
            "currency": "USD", 
            "date": "2025-01-01", 
            "merchant": "Test Merchant",
            "channel": "Online", 
            "customer_statement": "Test dispute",
            "crm_ticket_id": "CRM60001", 
            "previous_interactions": [],
            "risk_signals": {"fraud_score": 0.5}
        }


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/login")
async def login(request: Request):
    try:
        data = await request.json()
        username = data.get("username")
        password = data.get("password")
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password required")
        
        if username not in users_db:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_data = users_db[username]
        if hash_password(password) != user_data["password"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = {
            "username": user_data["username"],
            "full_name": user_data["full_name"],
            "role": user_data["role"]
        }
        
        response = JSONResponse(content={
            "message": "Login successful", 
            "user": sessions[session_id]
        })
        response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=3600)
        return response
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        del sessions[session_id]
    response = JSONResponse(content={"message": "Logout successful"})
    response.delete_cookie(key="session_id")
    return response

@app.get("/api/chatbot/open-cases")
async def get_open_cases_for_chatbot(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    open_cases = [case for case in cases_db.values() if case.get("status") == "open"]
    
    # Format cases for chatbot display
    formatted_cases = []
    for case in open_cases:
        formatted_cases.append({
            "case_id": case.get("case_id"),
            "transaction_id": case.get("transaction", {}).get("transaction_id"),
            "amount": case.get("transaction", {}).get("amount"),
            "currency": case.get("transaction", {}).get("currency"),
            "type": case.get("classification", {}).get("type"),
            "customer_id": case.get("transaction", {}).get("customer_id"),
            "merchant": case.get("transaction", {}).get("merchant")
        })
    
    return {
        "open_cases": formatted_cases,
        "count": len(open_cases)
    }

@app.get("/api/check-auth")
async def check_auth(request: Request):
    user = get_current_user(request)
    if not user:
        # Return 200 with authenticated: false instead of 401
        return JSONResponse(content={"authenticated": False})
    return JSONResponse(content={"authenticated": True, "user": user})

@app.get("/api/cases")
async def get_cases(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    open_cases = [case for case in cases_db.values() if case.get("status") == "open"]
    
    return {
        "message": f"Hi {user['full_name']}, you have {len(open_cases)} cases open.",
        "cases": list(cases_db.values()),
        "open_count": len(open_cases)
    }

@app.post("/api/cases/{case_id}/review")
async def review_case(case_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = cases_db[case_id]
    return {
        "message": f"Please open the case {case_id} to review.",
        "case": case
    }

@app.post("/api/cases/{case_id}/documents")
async def upload_documents(
    case_id: str, 
    files: List[UploadFile] = File(...),
    request: Request = None
):
    user = get_current_user(request) if request else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = cases_db[case_id]
    uploaded_files = []
    document_analyses = []
    
    for file in files:
        try:
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{file_extension}"
            file_path = os.path.join("uploads", unique_filename)
            
            # Save file
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Analyze document using AI agent
            transaction_data = case["transaction"]
            dispute_type = case["classification"]["type"]
            
            analysis_result = document_analysis_agent.analyze_document(
                file_path, transaction_data, dispute_type
            )
            
            # Store analysis result
            document_analyses.append(analysis_result)
            
            # Create document info
            doc_info = {
                "filename": unique_filename,
                "original_filename": file.filename,
                "document_type": analysis_result["document_type"],
                "upload_date": datetime.now().isoformat(),
                "size": len(content),
                "analysis": analysis_result
            }
            
            if "supporting_documents" not in case:
                case["supporting_documents"] = []
            case["supporting_documents"].append(doc_info)
            uploaded_files.append(file.filename)
            
        except Exception as e:
            print(f"Error processing file {file.filename}: {e}")
    
    # Calculate composite trust score from all document analyses
    if document_analyses:
        media_trust_score = document_analysis_agent.calculate_composite_trust_score(document_analyses)
        case["media_trust_score"] = media_trust_score
        
        # Store individual analyses
        document_analyses_db[case_id] = document_analyses
        
        # Update case status based on media trust score
        if media_trust_score > 90:
            case["status"] = "escalated"
            requires_escalation = True
        elif media_trust_score > 60:
            case["status"] = "in_review"
            requires_escalation = False
        else:
            case["status"] = "pending_docs"
            requires_escalation = False
    else:
        media_trust_score = 0
        requires_escalation = False
    
    cases_db[case_id] = case
    
    return {
        "success": True,
        "message": f"Uploaded {len(uploaded_files)} documents successfully",
        "media_trust_score": media_trust_score,
        "requires_escalation": requires_escalation,
        "document_analyses": document_analyses
    }

@app.get("/api/cases/{case_id}/documents/analysis")
async def get_document_analysis(case_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = cases_db[case_id]
    analyses = document_analyses_db.get(case_id, [])
    
    return {
        "case_id": case_id,
        "media_trust_score": case.get("media_trust_score"),
        "document_analyses": analyses,
        "supporting_documents": case.get("supporting_documents", [])
    }

@app.post("/api/cases/{case_id}/resolve")
async def resolve_case(
    case_id: str, 
    request: Request
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    try:
        data = await request.json()
        action = data.get("action")
        notes = data.get("notes", "")
        
        case = cases_db[case_id]
        
        if action == "approve":
            case["status"] = "closed"
            case["resolved_date"] = datetime.now().isoformat()
            case["agent_notes"] = notes
        elif action == "escalate":
            case["status"] = "escalated"
            case["agent_notes"] = notes
        elif action == "reopen":
            case["status"] = "open"
            case["resolved_date"] = None
            case["agent_notes"] = notes
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        cases_db[case_id] = case
        
        return {
            "message": f"Case {case_id} {action}d successfully",
            "case": case
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/disputes")
async def create_dispute(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        transaction_id = data.get("transaction_id")
        
        if not transaction_id:
            raise HTTPException(status_code=400, detail="Transaction ID required")
        
        if transaction_id not in transactions_db:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        transaction = transactions_db[transaction_id]
        
        # Use classification agent to classify dispute
        classification = classification_agent.classify_dispute(
            transaction.get("customer_statement", ""),
            transaction.get("risk_signals", {})
        )
        
        # Use policy agent to get relevant policies
        policies = policy_agent.get_relevant_policies(
            classification.type,
            transaction.get("risk_signals", {})
        )
        
        # Use resolution agent to recommend resolution
        resolution = resolution_agent.recommend_resolution(
            classification.type,
            policies,
            transaction.get("risk_signals", {}),
            transaction.get("amount", 0),
            transaction.get("currency", "USD")
        )
        
        # Create case
        case_id = f"CASE_{uuid.uuid4().hex[:8].upper()}"
        case = {
            "case_id": case_id,
            "transaction": transaction,
            "classification": {
                "type": classification.type.value,
                "confidence": classification.confidence
            },
            "policies": {
                "clauses": [clause.dict() for clause in policies.clauses]
            },
            "recommendation": {
                "resolution": [action.value for action in resolution.resolution],
                "amount": resolution.amount,
                "currency": resolution.currency,
                "citations": resolution.citations,
                "rationale": resolution.rationale
            },
            "status": "open",
            "media_trust_score": None,
            "supporting_documents": [],
            "created_date": datetime.now().isoformat(),
            "resolved_date": None,
            "agent_notes": None
        }
        
        cases_db[case_id] = case
        
        return {
            "message": "Dispute case created successfully",
            "case_id": case_id,
            "case": case
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if case_id not in cases_db:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return cases_db[case_id]

@app.get("/api/transactions")
async def get_transactions(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return list(transactions_db.values())

@app.get("/api/debug")
async def debug_info(request: Request):
    user = get_current_user(request)
    return {
        "authenticated": user is not None,
        "user": user,
        "cases_count": len(cases_db),
        "transactions_count": len(transactions_db),
        "sessions_count": len(sessions)
    }

@app.post("/api/chatbot/ask")
async def chatbot_question(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        question = data.get("question", "")
        
        # Simple RAG implementation - in production, use proper vector database
        knowledge_base = {
            "refund policy": "Full refunds within 90 days for unauthorized transactions. 30 days for billing errors.",
            "escalation process": "Cases with >90% trust score auto-escalate. Manual escalation requires supervisor approval.",
            "document requirements": "Need: transaction receipt, ID proof, merchant communication, supporting evidence.",
            "sla": "Standard: 5-7 business days. Urgent: 48 hours resolution time.",
            "fraud prevention": "Multi-factor authentication, transaction monitoring, AI-based fraud detection.",
            "customer support": "24/7 support available. Email: support@dispute.com, Phone: +1-800-DISPUTE"
        }
        
        # Find best match
        best_match = None
        best_score = 0
        
        for topic, answer in knowledge_base.items():
            score = sum(1 for word in question.lower().split() if word in topic.lower())
            if score > best_score:
                best_score = score
                best_match = answer
        
        if best_match:
            return {
                "answer": best_match,
                "confidence": best_score / len(question.split()),
                "source": "Dispute Resolution Knowledge Base 2024"
            }
        else:
            return {
                "answer": "I can help with dispute-related questions. Please ask about refunds, escalations, documents, or policies.",
                "confidence": 0.3,
                "source": "General Knowledge"
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
    )     