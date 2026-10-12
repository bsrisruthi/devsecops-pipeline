from flask import Flask
app = Flask(__name__)
@app.route("/health", methods=["GET"])
def health():
    return "ok", 200, {"Content-Type": "text/plain"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)