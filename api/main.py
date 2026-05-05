from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/files", StaticFiles(directory=str(PROJE_DIR)), name="files")


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data_dir": str(DATA_DIR)}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    users = read_csv(USERS_FILE, USER_COLUMNS)
    username = payload.username.strip()
    password = payload.password.strip()
    matched = users[
        (users["username"].astype(str).str.strip() == username)
        & (users["password"].astype(str).str.strip() == password)
    ]
    if matched.empty:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {"user": public_user(matched.iloc[0])}


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
        "password": payload.password.strip(),
        "role": "user",
    }
    users = pd.concat([users, pd.DataFrame([row])], ignore_index=True)
    write_csv(USERS_FILE, users)
    return {"user": public_user(row)}


@app.get("/api/users")
def list_users() -> list[dict[str, Any]]:
    users = read_csv(USERS_FILE, USER_COLUMNS)
    return [public_user(record) for record in clean_records(users)]


@app.get("/api/jobs")
def list_jobs() -> list[dict[str, Any]]:
    jobs = jobs_frame_with_classification()
    return clean_records(jobs)


@app.post("/api/jobs")
def create_job(payload: JobCreate) -> dict[str, Any]:
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
def delete_job(job_id: str) -> dict[str, str]:
    jobs = read_csv(JOBS_FILE, JOB_COLUMNS)
    remaining = jobs[jobs["id"].astype(str) != str(job_id)]
    if len(remaining) == len(jobs):
        raise HTTPException(status_code=404, detail="Job not found.")
    write_csv(JOBS_FILE, remaining)
    return {"status": "deleted"}


@app.get("/api/applications")
def list_applications(email: str | None = None) -> list[dict[str, Any]]:
    applications = read_csv(APPLICATIONS_FILE, APPLICATION_COLUMNS)
    if email:
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
) -> dict[str, Any]:
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
def update_application(application_id: str, payload: ApplicationPatch) -> dict[str, Any]:
    applications = read_csv(APPLICATIONS_FILE, APPLICATION_COLUMNS)
    match = applications["id"].astype(str) == application_id
    if not match.any():
        raise HTTPException(status_code=404, detail="Application not found.")

    updates = model_payload(payload)
    for key, value in updates.items():
        applications.loc[match, key] = value

    if "interview_scheduled_at" in updates and not updates.get("status"):
        applications.loc[match, "status"] = "Interview Scheduled"
    if "interview_passed" in updates and not updates.get("status"):
        applications.loc[match, "status"] = "HR Recommended" if updates["interview_passed"] else "Interview Not Passed"

    write_csv(APPLICATIONS_FILE, applications)
    return clean_records(applications[match])[0]
