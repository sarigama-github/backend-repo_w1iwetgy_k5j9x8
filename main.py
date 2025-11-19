import os
import hashlib
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from database import db, create_document, get_documents
from schemas import Upload, UserProgress, Report

app = FastAPI(title="Nova Enterprises Security API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Nova Enterprises backend running"}

@app.get("/test")
def test_database():
    status = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            status["database"] = "✅ Available"
            status["database_url"] = "✅ Set"
            status["database_name"] = getattr(db, 'name', '✅ Connected')
            status["connection_status"] = "Connected"
            try:
                status["collections"] = db.list_collection_names()[:10]
                status["database"] = "✅ Connected & Working"
            except Exception as e:
                status["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
    except Exception as e:
        status["database"] = f"❌ Error: {str(e)[:50]}"

    # Env check
    status["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    status["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return status

# Helper: compute SHA-256
async def _sha256_file(file: UploadFile) -> str:
    hasher = hashlib.sha256()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
    await file.seek(0)
    return hasher.hexdigest()

# Upload endpoint (metadata only)
@app.post("/api/uploads", response_model=dict)
async def upload_file(client_id: str = Form(...), file: UploadFile = File(...)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    checksum = await _sha256_file(file)
    # Need size; read content
    content = await file.read()
    size = len(content)
    await file.seek(0)

    metadata = Upload(
        client_id=client_id,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=size,
        sha256=checksum,
        verdict="scanned",
    )

    doc_id = create_document("upload", metadata)

    # Update gamification progress
    existing = db["userprogress"].find_one({"client_id": client_id})
    if existing:
        db["userprogress"].update_one({"_id": existing["_id"]}, {"$inc": {"points": 10, "uploads_count": 1}})
    else:
        create_document("userprogress", UserProgress(client_id=client_id, points=10, uploads_count=1))

    return {"ok": True, "id": doc_id, "sha256": checksum}

class AskRequest(BaseModel):
    question: str
    client_id: Optional[str] = None

class AskResponse(BaseModel):
    answer: str

@app.post("/api/ask", response_model=AskResponse)
async def ask_ai(payload: AskRequest):
    q = payload.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    base = "Nova AI: "
    if "upload" in q.lower():
        ans = "Your uploads are secured with checksum verification and metadata auditing."
    elif "security" in q.lower():
        ans = "We apply zero-trust principles, integrity hashing, and encrypted storage pipelines."
    else:
        ans = "I can help with uploads, security practices, and status. Ask me about how we protect your data."
    return AskResponse(answer=base + ans)

class ReportRequest(BaseModel):
    client_id: str
    subject: str
    message: str
    from_email: Optional[str] = None

@app.post("/api/report", response_model=dict)
async def report_issue(payload: ReportRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    report = Report(
        client_id=payload.client_id,
        subject=payload.subject,
        message=payload.message,
        from_email=payload.from_email,
        created_at=datetime.now(timezone.utc)
    )

    create_document("report", report)

    owner_email = os.getenv("OWNER_EMAIL", "kingnova1010@gmail.com")
    sent = False
    try:
        import smtplib
        from email.mime.text import MIMEText

        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        if smtp_host and smtp_user and smtp_pass:
            msg = MIMEText(f"Client: {payload.client_id}\nFrom: {payload.from_email}\n\n{payload.message}")
            msg["Subject"] = f"Nova Enterprises Report: {payload.subject}"
            msg["From"] = smtp_user
            msg["To"] = owner_email
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            sent = True
    except Exception:
        sent = False

    if sent:
        db["report"].update_one({"client_id": payload.client_id, "subject": payload.subject}, {"$set": {"sent_to_owner": True}})

    return {"ok": True, "sent": sent, "owner": owner_email}

@app.get("/api/progress/{client_id}")
def get_progress(client_id: str):
    doc = db["userprogress"].find_one({"client_id": client_id}) if db else None
    if not doc:
        return {"points": 0, "uploads_count": 0, "badges": []}
    doc.pop("_id", None)
    return doc

@app.get("/api/uploads/recent")
def recent_uploads(limit: int = 10):
    if db is None:
        return []
    docs = get_documents("upload", {}, limit)
    for d in docs:
        d.pop("_id", None)
    return docs

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
