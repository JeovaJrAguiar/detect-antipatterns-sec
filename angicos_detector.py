# angicos_detector.py
from flask import Flask, request, jsonify

app = Flask(__name__)

# Detector remoto que vou simular, está escutando na porta 5001

@app.post("/detector")
def detect():
    data = request.get_json()
    for item in data:
        item["exceeded"] = int(item.get("count", 0)) > 10
    detected = sum(1 for x in data if x["exceeded"])
    return jsonify({"analyzed": len(data), "detected": detected, "data": data})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)