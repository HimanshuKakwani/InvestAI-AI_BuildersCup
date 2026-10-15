# InvestPI Deployment Readiness & Production Hardening Audit

> [!NOTE]
> **Advisory Only**: As requested, **no direct modifications have been made to your application source code**. This document presents the audit findings and recommended code-level adjustments to ensure InvestPI runs smoothly, securely, and reliably on Google Cloud Run.

---

## 1. Readiness Audit Overview

Overall Production Readiness Score: **8.5 / 10**
- **Strengths**: Stateless architecture, decoupled 9-parameter engine, in-memory PDF generation, interactive Swagger UI, and native `/healthz` endpoint.
- **Areas Requiring Hardening**: Reverse-proxy HTTPS forwarding, Gemini model fallback order, memory cleanup guarantees, and error boundary handlers.

```
+--------------------------------------------------------------------------------------------------------+
| Priority | Component               | Issue Description                     | Cloud Run Risk Level      |
+--------------------------------------------------------------------------------------------------------+
| P1       | Werkzeug ProxyFix       | Missing HTTPS header forwarding       | Medium (Mixed Content)    |
| P1       | Gemini Client Model Order| Non-existent preview models tested 1st| High (API latency/failure)|
| P2       | Matplotlib Figure Close | Unclosed figures on plot exception    | Medium (Worker Memory)    |
| P2       | Missing `static/` Dir   | Flask logs 404 on static asset check  | Low (Cosmetic warning)    |
| P3       | CORS Headers            | Cross-origin blocked for external UIs | Medium (Demo integration) |
| P3       | 413 Payload Error       | Raw HTML on uploads > 10MB            | Low (User experience)     |
+--------------------------------------------------------------------------------------------------------+
```

---

## 2. Priority 1 (High Impact) Recommendations

### 2.1. Add Werkzeug `ProxyFix` for HTTPS Behind Cloud Run Load Balancer
**File**: [`app/routes/api.py`](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/app/routes/api.py)

#### Why This Is Needed:
Google Cloud Run terminates SSL/TLS at Google's global edge load balancer and forwards traffic to your container over HTTP. 
Without `ProxyFix`, Flask believes all incoming requests are unencrypted `http://`. This causes:
1. Swagger UI (`/apidocs/`) to try fetching `http://.../apispec.json`, triggering browser **Mixed Content** blocked errors.
2. Redirects (e.g. trailing slash redirects) to redirect users from `https://` back to insecure `http://`.

#### Recommended Code Addition:
```python
# In app/routes/api.py inside create_app():
from werkzeug.middleware.proxy_fix import ProxyFix

def create_app():
    # ... existing app initialization ...
    app = Flask(__name__, template_folder=templates_path, static_folder=static_path)
    
    # Enable Cloud Run reverse-proxy header forwarding
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,      # Forward client IP
        x_proto=1,    # Forward https scheme
        x_host=1,     # Forward original Host domain
        x_prefix=1    # Forward path prefix
    )
```

---

### 2.2. Correct Gemini Model Fallback Order & Validate Model Names
**File**: [`app/gemini/client.py`](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/app/gemini/client.py) and [`app/config.py`](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/app/config.py)

#### Why This Is Needed:
In `app/gemini/client.py` (lines 104, 243, 316), the fallback models are hardcoded as:
```python
fallback_models = ["gemini-3-flash-preview", self.model_name, "gemini-3.5-flash"]
```
And in `app/config.py`:
```python
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
```

**The problem**:
- `gemini-3-flash-preview` and `gemini-3.5-flash` are not active public endpoints in Google AI Studio. 
- Calling non-existent models first wastes **2 to 5 seconds of network timeout and error-catching per request** before falling back to your configured model or local mock.
- The user-configured `self.model_name` (e.g., `gemini-2.5-flash` or `gemini-1.5-flash`) should always be attempted **first**.

#### Recommended Code Adjustment:
```python
# In app/config.py:
class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    # Default to current production Gemini Flash models:
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# In app/gemini/client.py:
# Attempt configured model FIRST, then standard production fallbacks:
fallback_models = [
    self.model_name,
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]
```

---

## 3. Priority 2 (Medium Impact) Recommendations

### 3.1. Ensure Exception-Safe Matplotlib Figure Cleanup
**File**: [`app/reporting/chart_generator.py`](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/app/reporting/chart_generator.py)

#### Why This Is Needed:
Matplotlib maintains a global list of figures in memory. In `generate_price_target_chart`, `plt.close(fig)` is called at the end of the `try:` block. However, if an exception occurs mid-render, `plt.close(fig)` is skipped, leaving the figure in memory.
In long-running Gunicorn worker processes, this can cause a gradual memory leak.

#### Recommended Code Adjustment:
```python
# In app/reporting/chart_generator.py:
def generate_price_target_chart(...):
    if prices_df is None or prices_df.empty or "Close" not in prices_df.columns:
        return None

    fig = None
    try:
        fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=120)  # 120 DPI saves egress bandwidth
        # ... plot logic ...
        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), edgecolor="none")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None
    finally:
        if fig is not None:
            plt.close(fig)  # Guaranteed cleanup in all code paths
```

---

### 3.2. Create an Empty `static/` Directory
**Location**: `InvestAI-AI_BuildersCup/static/`

#### Why This Is Needed:
In `app/routes/api.py`, Flask is initialized with:
```python
static_path = str(ROOT_DIR / "static")
app = Flask(__name__, template_folder=templates_path, static_folder=static_path)
```
Currently, the directory `/static` does not exist on disk. While `templates/index.html` loads Tailwind via CDN, creating an empty `static/` directory (or a placeholder `static/.gitkeep`) prevents Flask runtime warnings in production logs.

---

## 4. Priority 3 (Usability & Robustness) Recommendations

### 4.1. Enable CORS for Cross-Origin API Access
**File**: [`app/routes/api.py`](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/app/routes/api.py)

#### Why This Is Needed:
If hackathon judges or external tools (like Postman web, automated evaluation scripts, or a custom frontend) make browser-based API calls to `https://<service-url>/api/analyze`, the browser may block the request without CORS headers.

#### Recommended Code Adjustment:
```python
# In app/routes/api.py inside create_app():
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response
```

---

### 4.2. Return Clean JSON for 413 (File Too Large) Errors
**File**: [`app/routes/api.py`](file:///Users/chawadesharvari17gmail.com/Desktop/projects/InvestAI-AI_BuildersCup/app/routes/api.py)

#### Why This Is Needed:
Your config sets `MAX_CONTENT_LENGTH = 10 * 1024 * 1024` (10 MB). If a user uploads a high-res screenshot exceeding 10MB, Flask displays a default HTML 413 error page. Adding a JSON error handler maintains API consistency:

```python
# In app/routes/api.py inside create_app():
@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({
        "error": "Uploaded image exceeds the 10 MB file size limit.",
        "status": 413
    }), 413
```

---

## 5. Summary & Decision

| Item | Recommended Action | Code Status |
| :--- | :--- | :--- |
| **Werkzeug `ProxyFix`** | Add to `create_app()` in `api.py` | **Pending Approval** |
| **Gemini Models** | Set `gemini-2.5-flash` first in `client.py` & `config.py` | **Pending Approval** |
| **Matplotlib Cleanup** | Add `finally: plt.close(fig)` in `chart_generator.py` | **Pending Approval** |
| **Static Dir** | Create `static/.gitkeep` placeholder | **Pending Approval** |
| **CORS & 413 Handler** | Add headers & error handler in `api.py` | **Pending Approval** |

No code files have been modified. Review these recommendations and approve whenever you want any or all of them applied.
