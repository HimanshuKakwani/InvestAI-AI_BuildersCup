"""Run the local InvestPI web development server."""
import os
import sys

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.routes.api import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print(f"Starting InvestPI Web Platform on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
