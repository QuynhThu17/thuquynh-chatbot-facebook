from flask import Flask, request, redirect
import os
import requests
import dotenv 

dotenv.load_dotenv()

app = Flask(__name__)

CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")  # https://...ngrok.../api/v1/socials/facebook/connect

# Bước 1: URL login Facebook
@app.route("/login")
def login():
    fb_auth_url = (
        f"https://www.facebook.com/v16.0/dialog/oauth?"
        f"client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=email,public_profile"
    )
    return redirect(fb_auth_url)

# Bước 2: Nhận code từ Facebook
@app.route("/api/v1/socials/facebook/connect", methods=["GET"])
def fb_callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400
    
    # Lấy access token từ Facebook
    token_url = (
        f"https://graph.facebook.com/v16.0/oauth/access_token?"
        f"client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&client_secret={CLIENT_SECRET}&code={code}"
    )
    token_resp = requests.get(token_url).json()
    access_token = token_resp.get("access_token")
    
    return f"Access Token: {access_token}"

    
if __name__ == "__main__":
    app.run(port=1975)
