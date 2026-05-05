import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BarChart3,
  BriefcaseBusiness,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  FileText,
  Image as ImageIcon,
  LogIn,
  LogOut,
  Mail,
  Phone,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  User,
  Users,
  XCircle
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE || "";
const USER_KEY = "pentecost-modern-user";
const STATUS_COLORS = {
  "CV Passed": "#15803d",
  "CV Not Passed": "#dc2626",
  "Interview Scheduled": "#2563eb",
  "HR Recommended": "#7c3aed",
  "Interview Not Passed": "#b45309",
  "Approved": "#0f766e",
  "Rejected": "#be123c"
};

function assetUrl(path) {
  if (!path) return "";
  return `${API_BASE}/files/${String(path).replaceAll("\\", "/")}`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }
  return response.json();
}

function formatMoney(value) {
  const number = Number(value || 0);
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    maximumFractionDigits: 0
  }).format(number);
}

function scorePercent(value) {
  return Math.round(Number(value || 0) * 100);
}

function jobFor(app, jobs) {
  return jobs.find((job) => String(job.id) === String(app.job_id)) || {};
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem(USER_KEY);
    return stored ? JSON.parse(stored) : null;
  });
  const [jobs, setJobs] = useState([]);
  const [applications, setApplications] = useState([]);
  const [users, setUsers] = useState([]);
  const [view, setView] = useState("jobs");
  const [selectedJob, setSelectedJob] = useState(null);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function refresh() {
    setLoading(true);
    setError("");
    try {
      const [jobsData, appsData, usersData] = await Promise.all([
        api("/api/jobs"),
        api("/api/applications"),
        api("/api/users")
      ]);
      setJobs(jobsData);
      setApplications(appsData);
      setUsers(usersData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  function handleUser(nextUser) {
    setUser(nextUser);
    localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    if (nextUser.role === "hr") setView("review");
    else if (nextUser.role === "pro_vc") setView("vc");
    else if (nextUser.role === "admin") setView("admin");
    else setView("jobs");
  }

  function logout() {
    setUser(null);
    localStorage.removeItem(USER_KEY);
    setView("jobs");
  }

  const visibleApplications = useMemo(() => {
    if (!user) return [];
    if (user.role === "user") {
      return applications.filter((app) => String(app.email).trim().toLowerCase() === user.email.toLowerCase());
    }
    return applications;
  }, [applications, user]);

  return (
    <main className="app-shell">
      <HeroStrip user={user} onLogout={logout} />
      {notice && (
        <button className="toast" onClick={() => setNotice("")}>
          <CheckCircle2 size={18} />
          <span>{notice}</span>
        </button>
      )}
      {error && (
        <div className="error-band">
          <XCircle size={18} />
          <span>{error}</span>
          <button className="icon-button" onClick={refresh} aria-label="Retry">
            <RefreshCw size={18} />
          </button>
        </div>
      )}

      {!user ? (
        <AuthWorkspace jobs={jobs} loading={loading} onLogin={handleUser} onSignup={handleUser} />
      ) : (
        <div className="workspace">
          <Sidebar user={user} view={view} setView={setView} onLogout={logout} />
          <section className="content-area">
            <Toolbar loading={loading} onRefresh={refresh} user={user} />
            {view === "jobs" && (
              <JobsView
                jobs={jobs}
                applications={visibleApplications}
                user={user}
                onApply={setSelectedJob}
                onRefresh={refresh}
              />
            )}
            {view === "applications" && (
              <ApplicationsView applications={visibleApplications} jobs={jobs} title="My Applications" />
            )}
            {view === "review" && (
              <ReviewView applications={applications} jobs={jobs} onRefresh={refresh} onNotice={setNotice} />
            )}
            {view === "vc" && (
              <VcView applications={applications} jobs={jobs} onRefresh={refresh} onNotice={setNotice} />
            )}
            {view === "admin" && (
              <AdminView
                users={users}
                jobs={jobs}
                applications={applications}
                onRefresh={refresh}
                onNotice={setNotice}
              />
            )}
          </section>
        </div>
      )}

      {selectedJob && user && (
        <ApplyPanel
          job={selectedJob}
          user={user}
          onClose={() => setSelectedJob(null)}
          onCreated={async () => {
            setSelectedJob(null);
            setNotice("Application submitted and analyzed.");
            await refresh();
            setView("applications");
          }}
        />
      )}
    </main>
  );
}

function HeroStrip({ user, onLogout }) {
  return (
    <header className="hero-strip">
      <div className="hero-media" />
      <div className="hero-content">
        <div className="brand-mark">
          <img src={assetUrl("pentecost logo.jpg")} alt="Pentecost University" />
          <div>
            <h1>Pentecost Recruiter</h1>
            <p>CV analysis, vacancies, interviews, and approvals</p>
          </div>
        </div>
        {user && (
          <div className="identity-chip">
            <User size={17} />
            <span>{user.username}</span>
            <strong>{user.role.replace("_", " ")}</strong>
            <button className="icon-button light" onClick={onLogout} aria-label="Log out">
              <LogOut size={17} />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

function AuthWorkspace({ jobs, loading, onLogin, onSignup }) {
  const [mode, setMode] = useState("login");
  const [query, setQuery] = useState("");
  const previewJobs = jobs
    .filter((job) => {
      const haystack = `${job.title} ${job.description} ${job.requirements} ${job.department}`.toLowerCase();
      return haystack.includes(query.toLowerCase());
    })
    .slice(0, 6);

  return (
    <section className="auth-grid">
      <div className="auth-panel">
        <div className="segmented">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
            <LogIn size={17} />
            Login
          </button>
          <button className={mode === "signup" ? "active" : ""} onClick={() => setMode("signup")}>
            <Plus size={17} />
            Sign Up
          </button>
        </div>
        {mode === "login" ? <LoginForm onLogin={onLogin} /> : <SignupForm onSignup={onSignup} />}
      </div>
      <div className="guest-jobs">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Live vacancies</p>
            <h2>Explore openings</h2>
          </div>
          {loading && <span className="loading-dot" />}
        </div>
        <label className="search-field">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search title, skill, department" />
        </label>
        <div className="compact-job-list">
          {previewJobs.map((job) => (
            <article key={job.id} className="job-row">
              <div>
                <h3>{job.title}</h3>
                <p>{job.department}</p>
              </div>
              <strong>{formatMoney(job.salary)}</strong>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function LoginForm({ onLogin }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const body = JSON.stringify(form);
      const result = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body
      });
      onLogin(result.user);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      <label>
        Username
        <input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
      </label>
      <label>
        Password
        <input
          type="password"
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />
      </label>
      {message && <p className="form-error">{message}</p>}
      <button className="primary-button" disabled={busy}>
        <LogIn size={18} />
        {busy ? "Checking..." : "Enter Workspace"}
      </button>
    </form>
  );
}

function SignupForm({ onSignup }) {
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const result = await api("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });
      onSignup(result.user);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      <label>
        Username
        <input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
      </label>
      <label>
        Email
        <input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
      </label>
      <label>
        Password
        <input
          type="password"
          value={form.password}
          onChange={(event) => setForm({ ...form, password: event.target.value })}
        />
      </label>
      {message && <p className="form-error">{message}</p>}
      <button className="primary-button" disabled={busy}>
        <Plus size={18} />
        {busy ? "Creating..." : "Create Account"}
      </button>
    </form>
  );
}

function Sidebar({ user, view, setView, onLogout }) {
  const items = [
    { id: "jobs", label: "Vacancies", icon: BriefcaseBusiness, roles: ["user", "hr", "pro_vc", "admin"] },
    { id: "applications", label: "My Apps", icon: ClipboardList, roles: ["user"] },
    { id: "review", label: "HR Review", icon: BarChart3, roles: ["hr", "admin"] },
    { id: "vc", label: "VC Board", icon: ShieldCheck, roles: ["pro_vc", "admin"] },
    { id: "admin", label: "Admin", icon: Users, roles: ["admin"] }
  ].filter((item) => item.roles.includes(user.role));

  return (
    <nav className="sidebar">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id)}>
            <Icon size={19} />
            <span>{item.label}</span>
          </button>
        );
      })}
      <button onClick={onLogout}>
        <LogOut size={19} />
        <span>Logout</span>
      </button>
    </nav>
  );
}

function Toolbar({ loading, onRefresh, user }) {
  return (
    <div className="toolbar">
      <div>
        <p className="eyebrow">Workspace</p>
        <h2>{user.role === "user" ? "Applicant Portal" : "Recruitment Operations"}</h2>
      </div>
      <button className="secondary-button" onClick={onRefresh}>
        <RefreshCw size={17} className={loading ? "spin" : ""} />
        Refresh
      </button>
    </div>
  );
}

function JobsView({ jobs, applications, user, onApply, onRefresh }) {
  const [query, setQuery] = useState("");
  const [faculty, setFaculty] = useState("All");
  const [department, setDepartment] = useState("All");
  const [sort, setSort] = useState("match");

  const faculties = useMemo(() => ["All", ...unique(jobs.map((job) => job.faculty))], [jobs]);
  const departments = useMemo(() => ["All", ...unique(jobs.map((job) => job.department))], [jobs]);

  const filteredJobs = useMemo(() => {
    return jobs
      .filter((job) => {
        const haystack = `${job.title} ${job.description} ${job.requirements} ${job.faculty} ${job.department}`.toLowerCase();
        return haystack.includes(query.toLowerCase());
      })
      .filter((job) => faculty === "All" || job.faculty === faculty)
      .filter((job) => department === "All" || job.department === department)
      .sort((a, b) => {
        if (sort === "salary") return Number(b.salary || 0) - Number(a.salary || 0);
        if (sort === "title") return String(a.title).localeCompare(String(b.title));
        return String(a.department).localeCompare(String(b.department));
      });
  }, [jobs, query, faculty, department, sort]);

  const appliedJobIds = new Set(applications.map((app) => String(app.job_id)));

  return (
    <section className="flow">
      <div className="filter-bar">
        <label className="search-field grow">
          <Search size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search vacancies" />
        </label>
        <select value={faculty} onChange={(event) => setFaculty(event.target.value)}>
          {faculties.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <select value={department} onChange={(event) => setDepartment(event.target.value)}>
          {departments.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
        <select value={sort} onChange={(event) => setSort(event.target.value)}>
          <option value="match">Department</option>
          <option value="salary">Salary</option>
          <option value="title">Title</option>
        </select>
      </div>
      <div className="job-grid">
        {filteredJobs.map((job) => {
          const alreadyApplied = appliedJobIds.has(String(job.id));
          return (
            <article key={job.id} className="job-card">
              <div className="job-card-top">
                <span className="pill blue">{job.faculty}</span>
                <strong>{formatMoney(job.salary)}</strong>
              </div>
              <h3>{job.title}</h3>
              <p>{job.description}</p>
              <div className="requirement">{job.requirements}</div>
              <div className="job-actions">
                <span className="muted">{job.department}</span>
                {user.role === "user" && (
                  <button className="primary-button compact" onClick={() => onApply(job)} disabled={alreadyApplied}>
                    <Upload size={17} />
                    {alreadyApplied ? "Applied" : "Apply"}
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
      {!filteredJobs.length && (
        <EmptyState icon={Search} title="No vacancies found" action="Clear filters" onAction={() => {
          setQuery("");
          setFaculty("All");
          setDepartment("All");
          onRefresh();
        }} />
      )}
    </section>
  );
}

function ApplyPanel({ job, user, onClose, onCreated }) {
  const [form, setForm] = useState({ name: user.username, email: user.email, phone: "" });
  const [cv, setCv] = useState(null);
  const [image, setImage] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const payload = new FormData();
    payload.append("name", form.name);
    payload.append("email", form.email);
    payload.append("phone", form.phone);
    payload.append("job_id", job.id);
    payload.append("cv", cv);
    payload.append("image", image);
    try {
      await api("/api/applications", { method: "POST", body: payload });
      await onCreated();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <form className="apply-panel" onSubmit={submit}>
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Apply for</p>
            <h2>{job.title}</h2>
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <XCircle size={20} />
          </button>
        </div>
        <div className="two-col">
          <label>
            Name
            <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required />
          </label>
          <label>
            Email
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              required
            />
          </label>
        </div>
        <label>
          Phone
          <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} required />
        </label>
        <div className="upload-grid">
          <label className="upload-box">
            <FileText size={25} />
            <span>{cv ? cv.name : "Upload CV PDF"}</span>
            <input type="file" accept="application/pdf" onChange={(event) => setCv(event.target.files[0])} required />
          </label>
          <label className="upload-box">
            <ImageIcon size={25} />
            <span>{image ? image.name : "Upload photo"}</span>
            <input type="file" accept="image/png,image/jpeg" onChange={(event) => setImage(event.target.files[0])} required />
          </label>
        </div>
        {message && <p className="form-error">{message}</p>}
        <button className="primary-button" disabled={busy}>
          <Upload size={18} />
          {busy ? "Analyzing..." : "Submit Application"}
        </button>
      </form>
    </div>
  );
}

function ApplicationsView({ applications, jobs, title = "Applications" }) {
  const [status, setStatus] = useState("All");
  const statuses = ["All", ...unique(applications.map((app) => app.status))];
  const filtered = status === "All" ? applications : applications.filter((app) => app.status === status);

  return (
    <section className="flow">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Pipeline</p>
          <h2>{title}</h2>
        </div>
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          {statuses.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </div>
      <div className="application-table">
        <div className="table-head">
          <span>Applicant</span>
          <span>Vacancy</span>
          <span>Score</span>
          <span>Status</span>
          <span>Files</span>
        </div>
        {filtered.map((app) => {
          const job = jobFor(app, jobs);
          return (
            <div key={app.id} className="table-row">
              <div>
                <strong>{app.name}</strong>
                <small>{app.email}</small>
              </div>
              <span>{job.title || app.job_id}</span>
              <ScoreRing value={scorePercent(app.similarity)} />
              <StatusPill status={app.status} />
              <div className="row-actions">
                {app.cv_path && (
                  <a className="icon-link" href={assetUrl(app.cv_path)} target="_blank" rel="noreferrer" aria-label="Open CV">
                    <FileText size={18} />
                  </a>
                )}
                {app.image_path && (
                  <a className="icon-link" href={assetUrl(app.image_path)} target="_blank" rel="noreferrer" aria-label="Open photo">
                    <ImageIcon size={18} />
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {!filtered.length && <EmptyState icon={ClipboardList} title="No applications" />}
    </section>
  );
}

function ReviewView({ applications, jobs, onRefresh, onNotice }) {
  const [selectedId, setSelectedId] = useState(applications[0]?.id || "");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("All");
  const [form, setForm] = useState({
    interview_scheduled_at: "",
    interview_meet_link: "",
    interview_notes: ""
  });
  const [busy, setBusy] = useState(false);

  const pipeline = useMemo(() => pipelineData(applications), [applications]);
  const statuses = ["All", ...unique(applications.map((app) => app.status))];
  const filtered = applications
    .filter((app) => status === "All" || app.status === status)
    .filter((app) => {
      const job = jobFor(app, jobs);
      return `${app.name} ${app.email} ${job.title} ${app.status}`.toLowerCase().includes(query.toLowerCase());
    })
    .sort((a, b) => Number(b.similarity || 0) - Number(a.similarity || 0));

  const selected = applications.find((app) => app.id === selectedId) || filtered[0];
  const selectedJob = selected ? jobFor(selected, jobs) : {};

  async function patchSelected(payload, note) {
    if (!selected) return;
    setBusy(true);
    try {
      await api(`/api/applications/${selected.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      onNotice(note);
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flow">
      <DashboardMetrics applications={applications} jobs={jobs} />
      <div className="chart-grid">
        <ChartPanel title="Pipeline Status">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={pipeline}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {pipeline.map((entry) => (
                  <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || "#64748b"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartPanel>
        <ChartPanel title="CV Pass Ratio">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={passRatioData(applications)}
                dataKey="value"
                innerRadius={58}
                outerRadius={88}
                paddingAngle={4}
              >
                <Cell fill="#15803d" />
                <Cell fill="#dc2626" />
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartPanel>
      </div>
      <div className="review-layout">
        <div className="review-list">
          <div className="filter-bar slim">
            <label className="search-field grow">
              <Search size={18} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search applicants" />
            </label>
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              {statuses.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </div>
          {filtered.map((app) => {
            const job = jobFor(app, jobs);
            return (
              <button key={app.id} className={`applicant-line ${selected?.id === app.id ? "active" : ""}`} onClick={() => setSelectedId(app.id)}>
                <img src={assetUrl(app.image_path)} alt="" />
                <span>
                  <strong>{app.name}</strong>
                  <small>{job.title || app.job_id}</small>
                </span>
                <ScoreRing value={scorePercent(app.similarity)} />
              </button>
            );
          })}
        </div>
        {selected && (
          <aside className="detail-panel">
            <div className="detail-profile">
              <img src={assetUrl(selected.image_path)} alt="" />
              <div>
                <h2>{selected.name}</h2>
                <p>{selectedJob.title || selected.job_id}</p>
                <StatusPill status={selected.status} />
              </div>
            </div>
            <div className="contact-grid">
              <a href={`mailto:${selected.email}`}>
                <Mail size={17} />
                {selected.email}
              </a>
              <a href={`tel:${selected.phone}`}>
                <Phone size={17} />
                {selected.phone || "No phone"}
              </a>
              <a href={assetUrl(selected.cv_path)} target="_blank" rel="noreferrer">
                <FileText size={17} />
                CV document
              </a>
            </div>
            <div className="score-panel">
              <ScoreRing value={scorePercent(selected.similarity)} large />
              <span>CV similarity score</span>
            </div>
            <div className="stack-form compact-form">
              <label>
                Interview date and time
                <input
                  type="datetime-local"
                  value={form.interview_scheduled_at}
                  onChange={(event) => setForm({ ...form, interview_scheduled_at: event.target.value })}
                />
              </label>
              <label>
                Meeting link
                <input
                  value={form.interview_meet_link}
                  onChange={(event) => setForm({ ...form, interview_meet_link: event.target.value })}
                />
              </label>
              <label>
                Notes
                <textarea
                  rows="3"
                  value={form.interview_notes}
                  onChange={(event) => setForm({ ...form, interview_notes: event.target.value })}
                />
              </label>
              <button
                className="primary-button"
                disabled={busy || !form.interview_scheduled_at}
                onClick={() => patchSelected(form, "Interview schedule updated.")}
              >
                <CalendarClock size={18} />
                Schedule Interview
              </button>
              <div className="split-buttons">
                <button className="success-button" disabled={busy} onClick={() => patchSelected({ interview_passed: true, hr_report_sent: true }, "Applicant recommended.")}>
                  <CheckCircle2 size={18} />
                  Recommend
                </button>
                <button className="danger-button" disabled={busy} onClick={() => patchSelected({ interview_passed: false, hr_report_sent: true }, "Interview marked as not passed.")}>
                  <XCircle size={18} />
                  Decline
                </button>
              </div>
            </div>
          </aside>
        )}
      </div>
    </section>
  );
}

function VcView({ applications, jobs, onRefresh, onNotice }) {
  const board = applications.filter((app) => ["HR Recommended", "Approved", "Rejected"].includes(app.status));
  async function decide(app, status) {
    await api(`/api/applications/${app.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    });
    onNotice(`Applicant ${status.toLowerCase()}.`);
    await onRefresh();
  }
  return (
    <section className="flow">
      <DashboardMetrics applications={applications} jobs={jobs} />
      <div className="candidate-grid">
        {board.map((app) => {
          const job = jobFor(app, jobs);
          return (
            <article key={app.id} className="candidate-card">
              <img src={assetUrl(app.image_path)} alt="" />
              <div>
                <h3>{app.name}</h3>
                <p>{job.title || app.job_id}</p>
                <ScoreRing value={scorePercent(app.similarity)} />
                <StatusPill status={app.status} />
              </div>
              <div className="split-buttons">
                <button className="success-button" onClick={() => decide(app, "Approved")}>
                  <CheckCircle2 size={18} />
                  Approve
                </button>
                <button className="danger-button" onClick={() => decide(app, "Rejected")}>
                  <XCircle size={18} />
                  Reject
                </button>
              </div>
            </article>
          );
        })}
      </div>
      {!board.length && <EmptyState icon={ShieldCheck} title="No HR recommendations yet" />}
    </section>
  );
}

function AdminView({ users, jobs, applications, onRefresh, onNotice }) {
  return (
    <section className="flow">
      <DashboardMetrics applications={applications} jobs={jobs} users={users} />
      <div className="admin-grid">
        <VacancyManager jobs={jobs} onRefresh={onRefresh} onNotice={onNotice} />
        <div className="admin-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Access</p>
              <h2>Users</h2>
            </div>
          </div>
          <div className="mini-table">
            {users.map((user) => (
              <div key={user.id}>
                <span>{user.username}</span>
                <small>{user.email}</small>
                <StatusPill status={user.role.replace("_", " ")} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <ApplicationsView applications={applications} jobs={jobs} title="All Applications" />
    </section>
  );
}

function VacancyManager({ jobs, onRefresh, onNotice }) {
  const [form, setForm] = useState({ title: "", description: "", requirements: "", salary: "" });
  const [busy, setBusy] = useState(false);

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form)
      });
      setForm({ title: "", description: "", requirements: "", salary: "" });
      onNotice("Vacancy published.");
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  async function remove(job) {
    setBusy(true);
    try {
      await api(`/api/jobs/${job.id}`, { method: "DELETE" });
      onNotice("Vacancy removed.");
      await onRefresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Vacancies</p>
          <h2>Publish Job</h2>
        </div>
      </div>
      <form className="stack-form compact-form" onSubmit={create}>
        <label>
          Title
          <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
        </label>
        <label>
          Description
          <textarea
            rows="3"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            required
          />
        </label>
        <label>
          Requirements
          <textarea
            rows="3"
            value={form.requirements}
            onChange={(event) => setForm({ ...form, requirements: event.target.value })}
            required
          />
        </label>
        <label>
          Salary
          <input value={form.salary} onChange={(event) => setForm({ ...form, salary: event.target.value })} required />
        </label>
        <button className="primary-button" disabled={busy}>
          <Plus size={18} />
          Publish Vacancy
        </button>
      </form>
      <div className="job-removal-list">
        {jobs.slice(0, 8).map((job) => (
          <div key={job.id}>
            <span>{job.title}</span>
            <button className="icon-button" onClick={() => remove(job)} disabled={busy} aria-label={`Remove ${job.title}`}>
              <Trash2 size={17} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardMetrics({ applications, jobs, users = [] }) {
  const passed = applications.filter((app) => String(app.cv_passed).toLowerCase() === "true").length;
  const recommended = applications.filter((app) => app.status === "HR Recommended").length;
  const avgScore = applications.length
    ? Math.round(applications.reduce((sum, app) => sum + scorePercent(app.similarity), 0) / applications.length)
    : 0;
  const metrics = [
    { label: "Vacancies", value: jobs.length, icon: BriefcaseBusiness },
    { label: "Applications", value: applications.length, icon: ClipboardList },
    { label: "CV Passed", value: passed, icon: CheckCircle2 },
    { label: "Recommended", value: recommended, icon: ShieldCheck },
    { label: "Avg Score", value: `${avgScore}%`, icon: BarChart3 }
  ];
  if (users.length) metrics.unshift({ label: "Users", value: users.length, icon: Users });
  return (
    <div className="metric-grid">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <article key={metric.label} className="metric-card">
            <Icon size={20} />
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </article>
        );
      })}
    </div>
  );
}

function ChartPanel({ title, children }) {
  return (
    <section className="chart-panel">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function StatusPill({ status }) {
  return (
    <span className="status-pill" style={{ "--status": STATUS_COLORS[status] || "#475569" }}>
      {status || "Pending"}
    </span>
  );
}

function ScoreRing({ value, large = false }) {
  const score = Number.isFinite(value) ? value : 0;
  return (
    <span className={`score-ring ${large ? "large" : ""}`} style={{ "--score": `${score * 3.6}deg` }}>
      {score}%
    </span>
  );
}

function EmptyState({ icon: Icon, title, action, onAction }) {
  return (
    <div className="empty-state">
      <Icon size={32} />
      <h3>{title}</h3>
      {action && <button className="secondary-button" onClick={onAction}>{action}</button>}
    </div>
  );
}

function pipelineData(applications) {
  const counts = applications.reduce((acc, app) => {
    const status = app.status || "Pending";
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});
  return Object.entries(counts).map(([name, count]) => ({ name, count }));
}

function passRatioData(applications) {
  const passed = applications.filter((app) => String(app.cv_passed).toLowerCase() === "true").length;
  return [
    { name: "Passed", value: passed },
    { name: "Not Passed", value: Math.max(applications.length - passed, 0) }
  ];
}

createRoot(document.getElementById("root")).render(<App />);
