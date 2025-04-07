from flask import Flask, request, jsonify
from flask_cors import CORS
from agent_runner import run_agent

app = Flask(__name__)
CORS(app)  # Enable CORS so Hoppscotch can talk to this server

@app.route("/")
def index():
    return "✅ Agent is running!"

@app.route("/run", methods=["POST"])
def run():
    input_data = request.get_json() or {}
    result = run_agent(input_data)
    return jsonify(result)

if __name__ == "__main__":
    # Debug server only; in production (Render), Gunicorn takes over.
    app.run(host="0.0.0.0", port=10000)
