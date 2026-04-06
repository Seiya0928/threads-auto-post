import requests
from dotenv import load_dotenv
import os

load_dotenv('config/.env')
token = os.environ.get('THREADS_ACCESS_TOKEN', '')
if not token:
    print("ERROR: THREADS_ACCESS_TOKEN が見つかりません")
    exit(1)

print(f"現在のトークン: {token[:20]}...")

r = requests.get(
    'https://graph.threads.net/refresh_access_token',
    params={'grant_type': 'th_refresh_token', 'access_token': token}
)
print(f"ステータス: {r.status_code}")
print(f"レスポンス: {r.json()}")
