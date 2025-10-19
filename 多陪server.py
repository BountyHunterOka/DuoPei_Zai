from fastapi import FastAPI
import threading
import time
import json
import base64
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
# import os
# import platform

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/start")
def start_book():
    thread = threading.Thread(target=start_grabbing, daemon=True)
    thread.start()
    return "开始抢单"


@app.get("/stop")
def stop_book():
    stop_grabbing()
    return "结束抢单"

@app.get("/voice_start")
def start_voice():
    start_talking()
    return "开始连麦单"

@app.get("/voice_stop")
def stop_voice():
    stop_talking()
    return "结束连麦单"

@app.get("/check_running")
def check():
    if running:
     return "运行中"
    else:
     return "已暂停"

# @app.get("/items/{item_id}")
# def read_item(item_id: int, q: Union[str, None] = None):
#     return {"item_id": item_id, "q": q}

# def play_sound():
#     try:
#         system = platform.system()
#         if system == "Darwin":
#             os.system('afplay /System/Library/Sounds/Glass.aiff')
#         elif system == "Windows":
#             import winsound
#             winsound.MessageBeep()
#         else:
#             print("提示音在当前系统不支持")
#     except Exception as e:
#         print(f"[播放提示音失败] {e}")

# ========== 常量 ==========
KEY_HEX = "81b120ef00216c33b266763abb02e6d1"
IV_HEX = "e6a4cc0507dfe344b042289eeb945dce"

HEADERS = {
    "accept": "*/*",
    "content-type": "application/x-www-form-urlencoded",
    "platform": "app",
    "authorization-token": "991ae2a76bc94fc3a970b8d60e525c1d",
    "sid": "47",
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Html5Plus/1.0 (Immersed/20) uni-app",
    "accept-language": "en-GB,en;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "pragma": "no-cache",
    "cache-control": "no-cache"
}

BASE_URL = "https://api.duopei.feiniaowangluo.com"
session = requests.Session()
session.headers.update(HEADERS)

running = False
voice_talking = False

# ========== 日志输出 ==========
def log(text):
    print(text)

# ========== AES 解密 ==========
def decrypt_aes_cbc(encrypted_b64, key_hex, iv_hex):
    try:
        key = bytes.fromhex(key_hex)
        iv = bytes.fromhex(iv_hex)
        encrypted_data = base64.b64decode(encrypted_b64)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
        return decrypted.decode("utf-8")
    except Exception as e:
        log(f"[解密失败] {e}")
        return None

# ========== 刷新订单列表 ==========
def refresh_list():
    url = f"{BASE_URL}/s/c/order/randomList"
    params = {"pageNo": 1, "pageSize": 20}
    try:
        resp = session.get(url, params=params, timeout=3.5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("isEncrypted"):
            return decrypt_aes_cbc(data["response"], KEY_HEX, IV_HEX)
        return json.dumps(data)
    except Exception as e:
        log(f"[刷新失败] {e}")
        return None

# ========== 提取订单 ID ==========
def extract_order_id(decrypted_json_str):
    try:
        data = json.loads(decrypted_json_str)
        order_list = data.get("list", [])
        for order in order_list:
            if order.get("userMemo"):
                log("[跳过订单] 有备注")
                continue
            names = order.get("item", {}).get("names", [])
            if voice_talking and any(keyword in name for keyword in ['连麦','听歌'] for name in names):
                log("[跳过订单] 不要连麦单")
                continue
            return order.get("id")
    except Exception as e:
        log(f"[提取订单 ID 失败] {e}")
    return None

# ========== 抢单 ==========
def confirm_order(order_id):
    url = f"{BASE_URL}/s/c/order/confirm"
    data = {"id": order_id}
    try:
        while running:
            resp = session.post(url, data=data, timeout=1.5)
            da = resp.json()
            confirm_rep = decrypt_aes_cbc(da["response"], KEY_HEX, IV_HEX)
            if not confirm_rep:
                break
            log(f"[抢单结果] {confirm_rep}")
            if '未满足' in confirm_rep:
                time.sleep(2.5)
                log("等待中...继续尝试")
                continue
            break
    except Exception as e:
        log(f"[抢单失败] {e}")

# ========== 主循环 ==========
def run_loop(interval):
    global running
    while running:
        now = datetime.now()
        print("刷新时间 =", now.strftime("%H:%M:%S"))
        decrypted = refresh_list()
        if decrypted:
            order_id = extract_order_id(decrypted)
            if order_id:
                log(f"[发现订单] ID = {order_id}")
                threading.Thread(target=confirm_order, args=(order_id,), daemon=True).start()
                # play_sound()
            else:
                log("[无新订单]")
        else:
            log("[解密失败或网络异常]")
        time.sleep(interval)

# ========== 控制函数 ==========
def start_grabbing():
    global running
    if running:
        return
    try:
        interval = 2.5
        log(f"刷新时间间隔: {interval} 秒")
    except:
        log("请输入有效的数字作为间隔（秒）")
        return
    running = True
    log("[启动抢单]")
    threading.Thread(target=run_loop, args=(interval,), daemon=True).start()

def stop_grabbing():
    global running
    running = False
    log("[已停止抢单]")


def start_talking():
    global voice_talking
    voice_talking = True
    log("[开始连麦单]")


def stop_talking():
    global voice_talking
    voice_talking = False
    log("[结束连麦单]")

