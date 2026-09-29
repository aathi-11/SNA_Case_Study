"""
Launcher script for Interactive Football Passing Dashboard.
Ensures data export is present, starts a local HTTP server on http://localhost:8000/dashboard/,
and opens the dashboard in the browser.
"""

import os
import sys
import webbrowser
import http.server
import socketserver
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = BASE_DIR / "dashboard"
DATA_JSON = DASHBOARD_DIR / "data" / "dashboard_data.json"


def ensure_data():
    """Verify or export dashboard dataset."""
    if not DATA_JSON.exists():
        print("Dashboard dataset not found. Running data exporter...")
        from src.export_dashboard_data import export_dashboard_json
        export_dashboard_json()
    else:
        print(f"Dashboard data found: {DATA_JSON}")


def run_server(port=8000):
    """Start HTTP Server and open browser."""
    ensure_data()
    os.chdir(BASE_DIR)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    with socketserver.TCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}/dashboard/index.html"
        print(f"\n=======================================================")
        print(f" Interactive Football Dashboard is live at:")
        print(f" {url}")
        print(f"=======================================================\n")
        
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


if __name__ == "__main__":
    run_server()
