import os
import json
from flask import Flask, request, redirect, session
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

load_dotenv()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]

GOOGLE_CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = os.environ["REDIRECT_URI"]   # Render URL + /oauth2callback
YT_CHANNEL_ID = os.environ["YT_CHANNEL_ID"]

DATA_FILE = "data.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "codes": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_verified(discord_id: int):
    data = load_data()
    uid = str(discord_id)
    if uid not in data["users"]:
        data["users"][uid] = {}
    data["users"][uid]["verified"] = True
    save_data(data)


@app.route("/")
def index():
    return "T3AZ Bot doğrulama sistemi çalışıyor."


@app.route("/verify")
def verify():
    discord_id = request.args.get("discord_id")
    if not discord_id:
        return "discord_id yok!", 400

    session["discord_id"] = discord_id

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
    )

    flow.redirect_uri = REDIRECT_URI

    auth_url, state = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="consent",
    )

    session["state"] = state
    return redirect(auth_url)


@app.route("/oauth2callback")
def oauth2callback():
    state = session.get("state")
    discord_id = session.get("discord_id")

    if not state or not discord_id:
        return "Oturum kayboldu, Discord'dan tekrar komutu çalıştır.", 400

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
        state=state,
    )

    flow.redirect_uri = REDIRECT_URI
    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    youtube = build("youtube", "v3", credentials=creds)

    # Kullanıcının tüm aboneliklerini tara
    subscribed = False
    page_token = None

    while True:
        sub_req = youtube.subscriptions().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=page_token
        )
        response = sub_req.execute()

        for item in response.get("items", []):
            cid = item["snippet"]["resourceId"]["channelId"]
            if cid == YT_CHANNEL_ID:
                subscribed = True
                break

        if subscribed:
            break

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    if subscribed:
        set_verified(int(discord_id))
        return "✅ Aboneliğin doğrulandı! Artık Discord'da `!kod-al` yazabilirsin."

    return "❌ Bu Google hesabı hedef kanala abone değil."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
