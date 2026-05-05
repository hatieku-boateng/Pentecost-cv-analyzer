from __future__ import annotations

import shutil
import sys
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pandas.errors import ParserError
from pydantic import BaseModel, EmailStr


ROOT_DIR = Path(__file__).resolve().parents[1]
PROJE_DIR = ROOT_DIR / "Proje"
DATA_DIR = PROJE_DIR / "data"
CV_DIR = DATA_DIR / "cvs"
IMAGE_DIR = DATA_DIR / "images"

sys.path.insert(0, str(PROJE_DIR))
from utils.cv_processor import compute_similarity, extract_text_from_pdf  # noqa: E402


USERS_FILE = DATA_DIR / "users.csv"
JOBS_FILE = DATA_DIR / "jobs.csv"
APPLICATIONS_FILE = DATA_DIR / "applications.csv"
SIMILARITY_PASS_MARK = 0.55
TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_MINUTES", "480")) * 60
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-only-change-me-before-deploying")
PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 210_000
PUBLIC_ASSETS = {
    "school.jpeg",
    "pentecost logo.jpg",
    "pent 2.jpg",
    "Tips to Design An Impressive Architectural Resume.jpg",
}

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
ALLOWED_ORIGINS = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]

USER_COLUMNS = ["id", "username", "email", "password", "role"]
JOB_COLUMNS = ["id", "title", "description", "requirements", "salary"]
APPLICATION_COLUMNS = [
    "id",
    "name",
    "email",
    "phone",
    "job_id",
    "cv_path",
    "image_path",
    "submitted_at",
    "similarity",
    "cv_passed",
    "interview_scheduled_at",
    "interview_meet_link",
    "interview_notes",
    "interview_passed",
    "hr_report_sent",
    "status",
]


app = FastAPI(
    title="Pentecost Recruiter API",
    description="Interactive API layer for the Pentecost University CV Analyzer.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str


class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class JobCreate(BaseModel):
    title: str
    description: str
    requirements: str
    salary: float | int | str


class ApplicationPatch(BaseModel):
    interview_scheduled_at: str | None = None
    interview_meet_link: str | None = None
    interview_notes: str | None = None
    interview_passed: bool | None = None
    hr_report_sent: bool | None = None
    status: str | None = None


def read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(path)
    except ParserError:
        frame = pd.read_csv(path, engine="python", on_bad_lines="skip")
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame[columns]


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def clean_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.fillna("")
    records = clean.to_dict(orient="records")
    for record in records:
        for key, value in list(record.items()):
            if hasattr(value, "item"):
                record[key] = value.item()
    return records


def normalize_role(role: Any) -> str:
    role_value = str(role).strip().lower()
    if role_value in {"pro-vc", "pro_vc", "provc", "vc"}:
        return "pro_vc"
    return role_value


def public_user(record: pd.Series | dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record.get("id", "")),
        "username": str(record.get("username", "")),
        "email": str(record.get("email", "")).strip(),
        "role": normalize_role(record.get("role", "user")),
    }


def classify_job(row: pd.Series | dict[str, Any]) -> tuple[str, str]:
    text = f"{row.get('title', '')} {row.get('description', '')}".lower()
    if "comput" in text or "ict" in text or "systems" in text:
        return "Faculty of Computing", "Computing / ICT"
    if "account" in text or "market" in text or "finance" in text or "audit" in text or "procurement" in text:
        return "Business School", "Business / Finance"
    if "nursing" in text or "health" in text or "laboratory" in text:
        return "Faculty of Health Sciences", "Health and Clinical"
    if "theology" in text or "biblical" in text:
        return "Faculty of Theology", "Theology"
    if "education" in text or "counsel" in text:
        return "Faculty of Education", "Education and Counseling"
    if "engineering" in text or "science" in text:
        return "Faculty of Engineering and Science", "Engineering / Science"
    if "library" in text:
        return "Library Services", "University Library"
    if "admission" in text or "examination" in text or "registr" in text:
        return "Academic Affairs", "Admissions and Exams"
    if "human resource" in text or "administrative assistant" in text or "admin" in text:
        return "Central Administration", "HR and Admin"
    if "public relations" in text or "quality assurance" in text:
        return "Corporate Services", "PR and Quality Assurance"
    if "estate" in text or "security" in text:
        return "Operations and Facilities", "Estate and Security"
    if "sports" in text or "student affairs" in text:
        return "Student Affairs", "Student Life"
    return "General University Services", "General"


def jobs_frame_with_classification() -> pd.DataFrame:
    jobs = read_csv(JOBS_FILE, JOB_COLUMNS)
    if jobs.empty:
        jobs["faculty"] = []
        jobs["department"] = []
        return jobs
    classifications = jobs.apply(classify_job, axis=1)
    jobs["faculty"] = [item[0] for item in classifications]
    jobs["department"] = [item[1] for item in classifications]
    return jobs


def next_numeric_id(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 1
    values = pd.to_numeric(frame["id"], errors="coerce").dropna()
    return 1 if values.empty else int(values.max()) + 1


def model_payload(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


def password_is_hashed(value: str) -> bool:
    return value.startswith(f"{PASSWORD_SCHEME}$")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(candidate: str, stored: Any) -> bool:
    stored_text = str(stored).strip()
    if not password_is_hashed(stored_text):
        return hmac.compare_digest(candidate.strip(), stored_text)

    try:
        scheme, iterations_raw, salt, expected = stored_text.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            candidate.strip().encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_raw),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except (TypeError, ValueError):
        return False


def b64url_encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def b64url_decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(f"{payload}{padding}")


def sign_payload(payload: dict[str, Any]) -> str:
    encoded_payload = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(APP_SECRET_KEY.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{b64url_encode(signature)}"


def parse_token(token: str) -> dict[str, Any]:
    try:
        encoded_payload, signature = token.split(".", 1)
        expected = hmac.new(APP_SECRET_KEY.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(b64url_encode(expected), signature):
            raise ValueError("bad signature")
        payload = json.loads(b64url_decode(encoded_payload))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Invalid session token.") from None

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    return payload


def issue_token(user: dict[str, Any]) -> str:
    now = int(time.time())
    return sign_payload(
        {
            "sub": user["username"],
            "email": user["email"],
            "role": user["role"],
            "iat": now,
            "exp": now + TOKEN_TTL_SECONDS,
        }
    )


def user_from_token(token: str) -> dict[str, Any]:
    payload = parse_token(token)
    users = read_csv(USERS_FILE, USER_COLUMNS)
    matched = users[users["username"].astype(str).str.strip() == str(payload.get("sub", "")).strip()]
    if matched.empty:
        raise HTTPException(status_code=401, detail="User account no longer exists.")

    user = public_user(matched.iloc[0])
    if user["role"] != normalize_role(payload.get("role", "")):
        raise HTTPException(status_code=401, detail="Session role changed. Please sign in again.")
    return user


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user_from_token(authorization.split(" ", 1)[1].strip())


def require_roles(*roles: str):
    allowed = {normalize_role(role) for role in roles}

    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action.")
        return user

    return dependency


@app.get("/assets/{filename}")
def public_asset(filename: str) -> FileResponse:
    if filename not in PUBLIC_ASSETS:
        raise HTTPException(status_code=404, detail="Asset not found.")
    path = (PROJE_DIR / filename).resolve()
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(path)


@app.get("/api/files/{file_path:path}")
def protected_file(
    file_path: str,
    access_token: str | None = None,
    authorization: str | None = Header(default=None),
) -> FileResponse:
    token = access_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    user = user_from_token(token)
    requested = (PROJE_DIR / file_path).resolve()
    data_root = DATA_DIR.resolve()
    if data_root not in requested.parents:
        raise HTTPException(status_code=403, detail="Requested file is outside the protected data area.")
    if requested.suffix.lower() not in {".pdf", ".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=403, detail="File type is not allowed.")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    normalized_path = str(requested.relative_to(PROJE_DIR)).replace("\\", "/")
    if user["role"] == "user":
        applications = read_csv(APPLICATIONS_FILE, APPLICATION_COLUMNS)
        owner_rows = applications[applications["email"].astype(str).str.strip().str.lower() == user["email"].lower()]
        allowed_paths = set(owner_rows["cv_path"].astype(str)) | set(owner_rows["image_path"].astype(str))
        if normalized_path not in allowed_paths:
            raise HTTPException(status_code=403, detail="You do not have access to this file.")

    return FileResponse(requested)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_dir": str(DATA_DIR)}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    users = read_csv(USERS_FILE, USER_COLUMNS)
    username = payload.username.strip()
    password = payload.password.strip()
    matched = users[users["username"].astype(str).str.strip() == username]
    if matched.empty:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    record = matched.iloc[0]
    if not verify_password(password, record.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    user = public_user(record)
    return {"user": user, "token": issue_token(user)}


@app.post("/api/auth/signup")
def signup(payload: SignupRequest) -> dict[str, Any]:
    users = read_csv(USERS_FILE, USER_COLUMNS)
    username = payload.username.strip()
    email = payload.email.strip()
    if not username or not payload.password.strip():
        raise HTTPException(status_code=400, detail="Username and password are required.")
    if username in users["username"].astype(str).str.strip().values:
        raise HTTPException(status_code=409, detail="Username already exists.")
    if email.lower() in users["email"].astype(str).str.strip().str.lower().values:
        raise HTTPException(status_code=409, detail="Email already exists.")

    row = {
        "id": next_numeric_id(users),
        "username": username,
        "email": email,
        "password": hash_password(payload.password.strip()),
        "role": "user",
    }
    users = pd.concat([users, pd.DataFrame([row])], ignore_index=True)
    write_csv(USERS_FILE, users)
    user = public_user(row)
    return {"user": user, "token": issue_token(user)}


@app.get("/api/users")
def list_users(_: dict[str, Any] = Depends(require_roles("admin"))) -> list[dict[str, Any]]:
    users = read_csv(USERS_FILE, USER_COLUMNS)
    return [public_user(record) for record in clean_records(users)]


@app.get("/api/auth/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return {"user": user}


@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    jobs = jobs_frame_with_classification()
    return clean_records(jobs)


@app.post("/api/jobs")
def create_job(payload: JobCreate, _: dict[str, Any] = Depends(require_roles("admin", "hr"))) -> dict[str, Any]:
    jobs = read_csv(JOBS_FILE, JOB_COLUMNS)
    row = {
        "id": next_numeric_id(jobs),
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "requirements": payload.requirements.strip(),
        "salary": payload.salary,
    }
    if not row["title"] or not row["description"] or not row["requirements"]:
        raise HTTPException(status_code=400, detail="Title, description, and requirements are required.")
    jobs = pd.concat([jobs, pd.DataFrame([row])], ignore_index=True)
    write_csv(JOBS_FILE, jobs)
    faculty, department = classify_job(row)
    return {**row, "faculty": faculty, "department": department}


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, _: dict[str, Any] = Depends(require_roles("admin", "hr"))) -> dict[str, str]:
    jobs = read_csv(JOBS_FILE, JOB_COLUMNS)
    remaining = jobs[jobs["id"].astype(str) != str(job_id)]
    if len(remaining) == len(jobs):
        raise HTTPException(status_code=404, detail="Job not found.")
    write_csv(JOBS_FILE, remaining)
    return {"status": "deleted"}


@app.get("/api/applications")
def list_applications(
    email: str | None = None,
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    applications = read_csv(APPLICATIONS_FILE, APPLICATION_COLUMNS)
    if user["role"] == "user":
        applications = applications[applications["email"].astype(str).str.strip().str.lower() == user["email"].lower()]
    elif email:
        applications = applications[applications["email"].astype(str).str.strip().str.lower() == email.strip().lower()]
    return clean_records(applications)


@app.post("/api/applications")
async def create_application(
    name: str = Form(...),
    email: EmailStr = Form(...),
    phone: str = Form(""),
    job_id: str = Form(...),
    cv: UploadFile = File(...),
    image: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_roles("user")),
) -> dict[str, Any]:
    if str(email).strip().lower() != user["email"].lower():
        raise HTTPException(status_code=403, detail="You can only submit applications under your own account email.")

    jobs = read_csv(JOBS_FILE, JOB_COLUMNS)
    job_match = jobs[jobs["id"].astype(str) == str(job_id)]
    if job_match.empty:
        raise HTTPException(status_code=404, detail="Selected job was not found.")

    application_id = str(uuid4())
    cv_extension = Path(cv.filename or "").suffix.lower() or ".pdf"
    image_extension = Path(image.filename or "").suffix.lower() or ".jpg"
    if cv_extension != ".pdf":
        raise HTTPException(status_code=400, detail="CV must be a PDF.")
    if image_extension not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=400, detail="Photo must be JPG, JPEG, or PNG.")

    CV_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    cv_path = CV_DIR / f"{application_id}{cv_extension}"
    image_path = IMAGE_DIR / f"{application_id}{image_extension}"

    with cv_path.open("wb") as output:
        shutil.copyfileobj(cv.file, output)
    with image_path.open("wb") as output:
        shutil.copyfileobj(image.file, output)

    job = job_match.iloc[0]
    job_text = f"{job.get('title', '')} {job.get('description', '')} {job.get('requirements', '')}"
    try:
        cv_text = extract_text_from_pdf(str(cv_path))
        similarity = compute_similarity(cv_text, job_text)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not analyze PDF: {exc}") from exc

    cv_passed = similarity >= SIMILARITY_PASS_MARK
    row = {
        "id": application_id,
        "name": name.strip(),
        "email": str(email).strip(),
        "phone": phone.strip(),
        "job_id": job_id,
        "cv_path": f"data/cvs/{cv_path.name}",
        "image_path": f"data/images/{image_path.name}",
        "submitted_at": datetime.now().isoformat(),
        "similarity": similarity,
        "cv_passed": cv_passed,
        "interview_scheduled_at": "",
        "interview_meet_link": "",
        "interview_notes": "",
        "interview_passed": "",
        "hr_report_sent": False,
        "status": "CV Passed" if cv_passed else "CV Not Passed",
    }
    applications = read_csv(APPLICATIONS_FILE, APPLICATION_COLUMNS)
    applications = pd.concat([applications, pd.DataFrame([row])], ignore_index=True)
    write_csv(APPLICATIONS_FILE, applications)
    return row


@app.patch("/api/applications/{application_id}")
def update_application(
    application_id: str,
    payload: ApplicationPatch,
    user: dict[str, Any] = Depends(require_roles("hr", "pro_vc", "admin")),
) -> dict[str, Any]:
    applications = read_csv(APPLICATIONS_FILE, APPLICATION_COLUMNS)
    match = applications["id"].astype(str) == application_id
    if not match.any():
        raise HTTPException(status_code=404, detail="Application not found.")

    updates = model_payload(payload)
    if user["role"] == "pro_vc":
        allowed_vc_updates = {"status"}
        if set(updates) - allowed_vc_updates:
            raise HTTPException(status_code=403, detail="VC users may only approve or reject applications.")
        if updates.get("status") not in {"Approved", "Rejected"}:
            raise HTTPException(status_code=400, detail="VC status must be Approved or Rejected.")
    elif user["role"] == "hr" and updates.get("status") in {"Approved", "Rejected"}:
        raise HTTPException(status_code=403, detail="Only VC or admin users can approve or reject applications.")

    for key, value in updates.items():
        applications.loc[match, key] = value

    if "interview_scheduled_at" in updates and not updates.get("status"):
        applications.loc[match, "status"] = "Interview Scheduled"
    if "interview_passed" in updates and not updates.get("status"):
        applications.loc[match, "status"] = "HR Recommended" if updates["interview_passed"] else "Interview Not Passed"

    write_csv(APPLICATIONS_FILE, applications)
    return clean_records(applications[match])[0]
