# Running Waitlist V2 on Windows with Visual Studio 2026

## Prerequisites

1.  **Visual Studio 2026**
    *   Ensure the **Python development** workload is installed.
    *   Ensure the **Node.js development** workload is installed.
2.  **Node.js (LTS)**
    *   Install from [nodejs.org](https://nodejs.org/). Required to build the React frontend.
3.  **Redis**
    *   Required for WebSocket notifications (Channels) and Background Tasks (Celery).
    *   **Recommended:** Install via **WSL2** (Windows Subsystem for Linux):
        ```bash
        wsl --install
        # Inside Ubuntu/WSL:
        sudo apt update && sudo apt install redis-server
        sudo service redis-server start
        ```
    *   *Alternative:* Use a Windows port like Memurai (Developer Edition).

## Setup Instructions

### 1. Database & Environment
1.  Navigate to `Waitlist_Dev.v2/` in File Explorer.
2.  Copy `.env.example` to `.env`.
3.  Open `.env` and set `USE_SQLITE=True` for local development to avoid setting up MySQL.
    ```ini
    USE_SQLITE=True
    DEBUG=True
    CELERY_BROKER_URL=redis://127.0.0.1:6379/0
    ```

### 2. Frontend Build (React)
The Django backend expects the React app to be built into `static/dist`.

1.  Open a terminal (PowerShell or Command Prompt).
2.  Navigate to the frontend directory:
    ```powershell
    cd Waitlist_Dev.v2/frontend
    ```
3.  Install dependencies:
    ```powershell
    npm install
    ```
4.  Build the project:
    ```powershell
    npm run build
    ```
    *   *Note:* You must re-run `npm run build` whenever you make changes to React files (`.jsx`), unless you set up a split-terminal dev environment proxying to Vite.

### 3. Backend Setup (Visual Studio)
1.  Open `Waitlist_Dev.v2.sln` in Visual Studio 2026.
2.  In **Solution Explorer**, right-click **Python Environments** (or the project node) and select **Add Environment** if one is not detected.
3.  Install packages from `requirements.txt`:
    *   Right-click `requirements.txt` -> **Install from requirements.txt**.
    *   *Or via terminal:* `pip install -r requirements.txt`
4.  Initialize the Database:
    *   Right-click the project -> **Python** -> **Django Migrate**.
    *   *Or via terminal:* `python manage.py migrate`

## Running the Application

1.  **Start Redis** (if not running):
    *   WSL: `redis-server`
2.  **Start Debugging**:
    *   Press **F5** (Start Debugging) in Visual Studio.
    *   This typically runs `manage.py runserver`.
    *   Since `daphne` is installed, this should support WebSockets automatically.
3.  **Access the App**:
    *   Go to `http://localhost:8000/`.
    *   You should see the new React Landing Page.

## Troubleshooting

*   **"Template Not Found" or Blank Page:**
    *   Ensure you ran `npm run build` in the `frontend` folder.
    *   Check `Waitlist_Dev.v2/static/dist/index.html` exists.
*   **WebSocket Errors:**
    *   Ensure Redis is running (`redis-cli ping` should return `PONG`).
    *   Check console logs for connection refusals to `ws://localhost:8000`.
