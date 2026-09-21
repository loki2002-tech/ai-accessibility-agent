# 🚀 AI Accessibility Testing Agent

A production-grade accessibility testing platform that combines deterministic rule evaluation (axe-core), deep state DOM interaction (Form & Modal testing), and an AI reasoning layer (RAG) for root-cause analysis and remediation.

## 🌟 Features
* **Deep Form Testing:** Automatically submits blank forms to capture injected error messages and validates if they have proper `role="alert"` tags.
* **Smart Keyboard Testing:** Injects custom JavaScript to verify visible focus rings (`kb-focus-visible`) across the entire DOM.
* **AI Remediation (RAG):** Uses the Groq LPU API to analyze failing HTML components and writes exactly the CSS/HTML needed to fix them.
* **Beautiful Reports:** Generates Axe DevTools-style HTML reports with glowing locator boxes, CSS selectors, and full-screen screenshot lightboxes.
* **REST API:** Includes a fully asynchronous FastAPI web server to trigger scans remotely.
* **Docker Ready:** Deploy to any cloud environment instantly.

---

## 🛠️ 1. Setup & Installation

1. **Install the dependencies:**
   ```powershell
   pip install -e .
   pip install fastapi uvicorn
   ```

2. **Install the Playwright Browsers:**
   *(This downloads the invisible browsers used for testing)*
   ```powershell
   playwright install-deps chromium firefox
   playwright install chromium firefox
   ```

3. **Configure the AI Brain (`.env` file):**
   Create a `.env` file in the root directory (or edit the existing one) with your Groq API key:
   ```env
   A11Y_LLM_PROVIDER=groq
   A11Y_GROQ_API_KEYS=gsk_your_api_key_here
   A11Y_LLM_MODEL=openai/gpt-oss-120b
   ```
   *(Note: Ensure you use a valid Groq model like `openai/gpt-oss-120b`!)*

---

## 💻 2. How to run: The Command Line (CLI)
The fastest way to scan a website is via the terminal. This will pop open a browser, run the tests, and save the reports.

```powershell
# Windows PowerShell (Sets the Python path first!)
$env:PYTHONPATH="src"; python -m accessibility_agent.cli scan --url "https://demo.automationtesting.in/Register.html" --agentic
```
* **Check the results:** Open `reports/RUN-XXXX_report.html` in your web browser!

---

## 🌐 3. How to run: The REST API
If you want to connect this tool to a dashboard, a web app, or let other people use it, you can spin it up as a Web Server!

1. **Start the server:**
   ```powershell
   $env:PYTHONPATH="src"; python -m accessibility_agent.cli serve --port 8000
   ```
2. **Open the interactive dashboard:**
   Go to **http://127.0.0.1:8000/docs** in your browser.
3. **Trigger a scan:**
   Click the green **POST /api/v1/scan** button -> Click **Try it out** -> Click **Execute**.
4. **View the live reports:**
   Once completed, you can view the raw JSON at `http://127.0.0.1:8000/api/v1/scans/{run_id}/report`.

---

## 🐳 4. How to run: Docker (Production)
If you want to put this on an AWS Server or a Raspberry Pi without installing Python, use Docker!

1. **Build the container:**
   ```bash
   docker build -t a11y-agent .
   ```
2. **Run the container:**
   ```bash
   docker run -p 8000:8000 -v ./reports:/app/reports a11y-agent
   ```
   *(This starts the API on port 8000 and saves the reports to your local folder!)*

---

## ⚠️ Important Note on Groq Rate Limits
The AI Reasoning Engine reads the *entire source code* of the website to find accessibility contradictions. If you are using the **Free Tier** of the Groq API, you will likely hit their "Tokens Per Minute" limit (HTTP 429) on large websites. 
If this happens, the scanner will elegantly fallback to standard testing and generate the report without the AI remediation blocks.
