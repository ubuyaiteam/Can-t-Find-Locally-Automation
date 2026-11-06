"""Standalone launcher. To add the engine to your EXISTING Flask app instead, see README (2 lines)."""
from flask import Flask, redirect
from opportunity_research.blueprint import opportunity_bp

app = Flask(__name__)
app.register_blueprint(opportunity_bp)

@app.route("/")
def home():
    return redirect("/opportunity/")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
