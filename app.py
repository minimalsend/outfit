import logging
import requests
import asyncio
import time
import httpx
import json
from io import BytesIO
from collections import defaultdict
from functools import wraps
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from cachetools import TTLCache
from PIL import Image, ImageDraw, ImageFont
from proto import FreeFire_pb2, main_pb2, AccountPersonalShow_pb2
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
import base64
from flask_caching import Cache
from typing import Tuple, Optional
import my_pb2
import output_pb2
import requests
import binascii
from Crypto.Util.Padding import pad, unpad
from datetime import datetime, timezone
import random
from colorama import init
import warnings
from urllib3.exceptions import InsecureRequestWarning
from protobuf_decoder.protobuf_decoder import Parser
from requests.exceptions import RequestException

# === Settings ===
MAIN_KEY = base64.b64decode('WWcmdGMlREV1aDYlWmNeOA==')
MAIN_IV = base64.b64decode('Nm95WkRyMjJFM3ljaGpNJQ==')
RELEASEVERSION = "OB49"
USERAGENT = "Dalvik/2.1.0 (Linux; U; Android 13; CPH2095 Build/RKQ1.211119.001)"
SUPPORTED_REGIONS = {"IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EUROPE"}
TIMEOUT = httpx.Timeout(30.0, connect=60.0)
AES_KEY = b'Yg&tc%DEuh6%Zc^8'
AES_IV = b'6oyZDr22E3ychjM%'
ACCOUNT_API_URL = "https://app.thundersharma.shop/profile_info/{uid}/{region}/Akiru483744672"

# Configure logging
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)
cache = TTLCache(maxsize=100, ttl=300)
cached_tokens = defaultdict(dict)

# Constants
BG_IMAGE_URL = "https://i.ibb.co/NdyDyhQT/Gemini-Generated-Image-61lm4761lm4761lm.png"
OVERLAY_LAYER_URL = "https://i.ibb.co/mVrbzkPp/Gemini-Generated-Image-pqx7fipqx7fipqx7-removebg-preview.png"
GITHUB_BASE_URL = "https://get-image-vert.vercel.app/get_image?id={id}"

# HTTP session + cache
session = requests.Session()
download_cache = {}
def fetch_attversion():
    url = "https://raw.githubusercontent.com/minimalsend/release/refs/heads/main/version.json"  # Link com JSON simples

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        def buscar_attversion(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == "attversion":
                        return v
                    resultado = buscar_attversion(v)
                    if resultado is not None:
                        return resultado
            elif isinstance(d, list):
                for item in d:
                    resultado = buscar_attversion(item)
                    if resultado is not None:
                        return resultado
            return None
        
        attversion = buscar_attversion(data)
        if attversion is not None:
            print(f"attversion: {attversion}")
            return attversion
        else:
            print("Parâmetro 'attversion' não encontrado.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição: {e}")
    except ValueError:
        print("Erro ao decodificar o JSON.")


def fetch_image(url):
    """Fetch image with in-memory caching (no timeout)."""
    if not url:
        return None
    if url in download_cache:
        return download_cache[url].copy()
    try:
        resp = session.get(url)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        download_cache[url] = img
        return img.copy()
    except Exception as e:
        logging.error(f"Failed to fetch %s: %s", url, e)
        return None

# Preload base assets
CACHED_BG = fetch_image(BG_IMAGE_URL)
CACHED_OVERLAY = fetch_image(OVERLAY_LAYER_URL)

# Layout positions
IMAGE_POSITIONS = {
    "HEADS":      {"x":365, "y":100,  "w":80, "h":80},
    "FACEPAINTS": {"x":410, "y":185, "w":85,  "h":85},
    "MASKS":      {"x":345, "y":330, "w":80, "h":80},
    "TOPS":       {"x":55,  "y":105, "w":80, "h":80},
    "SECOND_TOP": {"x":15,  "y":190, "w":80, "h":80},
    "BOTTOMS":    {"x":55,  "y":265, "w":85, "h":80},
    "SHOES":      {"x":110, "y":345, "w":70, "h":70},
    "ARMS":       {"x":365, "y":265, "w":90, "h":55},
    "TRAN":       {"x":160, "y":135, "w":180, "h":180},
    "CHARACTER":  {"x":155, "y":130, "w":200, "h":300},
}

# Special avatar positions
SPECIAL_CHARACTER_POSITIONS = {
    "101000001": {"x":-50, "y":0, "w":775, "h":650},
    "102000004": {"x":-50, "y":0, "w":775, "h":650},
}

# Fallback outfit IDs
FALLBACK_ITEMS = {
    "HEADS": "211000000",
    "MASKS": "208000000",
    "FACEPAINTS": "214000000",
    "TOPS": "203000000",
    "SECOND_TOP": "212000000",
    "BOTTOMS": "204000000",
    "SHOES": "205000000",
    "ARMS": "212000000",
    "TRAN": "914000001",
}

# Character definitions
characters = [  
  {  
    "itemID": 101000001,  
    "name": "Nulla",  
    "skill_id": 0,  
    "png_image": "https://i.ibb.co/gLr02bzX/Picsart-25-04-28-20-04-44-957.png"
  },  
  {  
    "itemID": 101000005,  
    "name": "Olivia",  
    "skill_id": "106",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202211/435b2230bb59c6a7f087d841e7dc8590.png"  
  },  
  {  
    "itemID": 101000006,  
    "name": "Kelly",  
    "skill_id": "206",  
    "png_image": "https://i.postimg.cc/BnpRPsjv/Kelly-The-Swift.png"  
  },  
  {  
    "itemID": 101000007,  
    "name": "Nikita",  
    "skill_id": "506",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/93bac478d8b64e0a6b31fee8c75220d9.png"  
  },  
  {  
    "itemID": 101000008,  
    "name": "Misha",  
    "skill_id": "606",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/33110529f97da7fc1bf681e61a1de2bb.png"  
  },  
  {  
    "itemID": 101000009,  
    "name": "Paloma",  
    "skill_id": "906",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/93a87a41a13af14c2346379a0d917d36.png"  
  },  
  {  
    "itemID": 101000010,  
    "name": "Caroline",  
    "skill_id": "1106",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/aa43b9f99d6a367a5123dbae9f6cd5c6.png"  
  },  
  {  
    "itemID": 101000011,  
    "name": "Moco",  
    "skill_id": "1406",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/769ceca68c62ec35cdbf90f1c0d7c73f.png"  
  },  
  {  
    "itemID": 101000012,  
    "name": "Laura",  
    "skill_id": "1706",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/a742beadf78c01fb9e05aabc51c9369e.png"  
  },  
  {  
    "itemID": 101000013,  
    "name": "A124",  
    "skill_id": "1906",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/ab1469c59a10c4669482e1ab625357dd.png"  
  },  
  {  
    "itemID": 101000014,  
    "name": "Shani",  
    "skill_id": "2106",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20229/2a790a2ca70a797b5384a122ad7d8d10.png"  
  },  
  {  
    "itemID": 101000016,  
    "name": "Notora",  
    "skill_id": "2406",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/fab6aa1cb1c6ce92652a3f184d265b76.png"  
  },  
  {  
    "itemID": 101000017,  
    "name": "Steffie",  
    "skill_id": "2606",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/809499ee33234f1c72c6a3ab120e85dd.png"  
  },  
  {  
    "itemID": 101000018,  
    "name": "Kapella",  
    "skill_id": "2806",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/9c6b10d2984125fbdd96fae9e0a84518.png"  
  },  
  {  
    "itemID": 101000019,  
    "name": "Clu",  
    "skill_id": "3106",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/81def6541fb94bd20887bad6b5a725cf.png"  
  },  
  {  
    "itemID": 101000020,  
    "name": "Dasha",  
    "skill_id": "3506",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/8d2bc4db79fe889ab6541ae2dd7cd2cb.png"  
  },  
  {  
    "itemID": 101000022,  
    "name": "Xayne",  
    "skill_id": "4406",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20229/ea05dd27c4f4faf3267679d5f90cdaec.png"  
  },  
  {  
    "itemID": 101000023,  
    "name": "Moco Enigma",  
    "skill_id": "4806",  
    "png_image": "https://i.postimg.cc/FznQS4Wc/Moco-Rebirth.png"  
  },  
  {  
    "itemID": 101000024,  
    "name": "A-Patroa",  
    "skill_id": 0,  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/f5a466acec3ed5bd7cdd149e26288ad1.png"
  },  
  {  
    "itemID": 101000025,  
    "name": "Iris",  
    "skill_id": "5606",  
    "png_image": "https://photos.app.goo.gl/tP89GY8ZDZ9mydCKA"  
  },  
  {  
    "itemID": 101000026,  
    "name": "Luna",  
    "skill_id": "5306",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202211/9d03033ed89089d1f25c6be01817ebca.png"  
  },  
  {  
    "itemID": 101000027,  
    "name": "Sonia",  
    "skill_id": "6506",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20238/8f978bdbe46d3d2366b82713082d6683.png"  
  },  
  {  
    "itemID": 101000028,  
    "name": "Suzy",  
    "skill_id": "6606",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20246/2cdde4e7d5010be2a35971e19f2285e4.png"  
  },  
  {  
    "itemID": 101000049,  
    "name": "Kassie",  
    "skill_id": "7006",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20246/8d87fe1959e300741eda601e800c0f40.png"  
  },  
  {  
    "itemID": 101000050,  
    "name": "Lila",  
    "skill_id": "7106",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20249/b09e7f93ec7c7a47dccbd704d8e4d879.png"  
  },  
  {  
    "itemID": 102000004,  
    "name": "Primis",  
    "skill_id": 0,  
    "png_image": "https://i.ibb.co/0VVSXDbW/Primis.png"
  },  
  {  
    "itemID": 102000005,  
    "name": "Andrew",  
    "skill_id": "406",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/564762d9a1137afaf2c9abb0ea8862b7.png"  
  },  
  {  
    "itemID": 102000006,  
    "name": "Ford",  
    "skill_id": "306",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202211/e4eba268be6b474381acc6c4b282f5ea.png"  
  },  
  {  
    "itemID": 102000007,  
    "name": "Maxim",  
    "skill_id": "706",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/59dc42433e877fa0cc3bb69b74dbf2c8.png"  
  },  
  {  
    "itemID": 102000008,  
    "name": "Kla",  
    "skill_id": "806",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/1655985bf74931458766921ee6bb6e0a.png"  
  },  
  {  
    "itemID": 102000009,  
    "name": "Miguel",  
    "skill_id": "1006",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/041a8586fe9d5461a7f28510fb5786d0.png"  
  },  
  {  
    "itemID": 102000010,  
    "name": "Antonio",  
    "skill_id": "1306",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/c87a2bcb4b4ab665908df11672aa191d.png"  
  },  
  {  
    "itemID": 102000011,  
    "name": "Wukong",  
    "skill_id": "1206",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20229/c0f1547f51f4c2b99e28ef4ec52db084.png"  
  },  
  {  
    "itemID": 102000012,  
    "name": "Hayato",  
    "skill_id": "1506",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/d8800f78f00e9831fc157a04aa3078aa.png"  
  },  
  {  
    "itemID": 102000013,  
    "name": "Rafael",  
    "skill_id": "1806",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/738a885af3eb66c1415a0ac61bfd304b.png"  
  },  
  {  
    "itemID": 102000014,  
    "name": "Joseph",  
    "skill_id": "2006",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/07d65d842e613a0cc22794f953c44be3.png"  
  },  
  {  
    "itemID": 102000015,  
    "name": "Alok",  
    "skill_id": "2206",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/c62e709e3ad8387f5484bb12e1cc81a9.png"  
  },  
  {  
    "itemID": 102000016,  
    "name": "Alvaro",  
    "skill_id": "2306",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/d5c0af0ac8632385f2cdb0500874b2a5.png"  
  },  
  {  
    "itemID": 102000017,  
    "name": "Jota",  
    "skill_id": "2706",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20229/5ae1530683a65bdfd81f6f7f7552650c.png"  
  },  
  {  
    "itemID": 102000018,  
    "name": "Luqueta",  
    "skill_id": "2906",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20229/28b704e964e8057d7fc76e1a2cca7d26.png"  
  },  
  {  
    "itemID": 102000019,  
    "name": "Wolfrahh",  
    "skill_id": "3006",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/e4169a44d8a6e83549b3b7f8a7820c1e.png"  
  },  
  {  
    "itemID": 102000021,  
    "name": "Jai",  
    "skill_id": "3306",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202412/077ccf77edb55d6b9d529e4afc1ae965.png"  
  },  
  {  
    "itemID": 102000022,  
    "name": "K",  
    "skill_id": "3406",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/cace792e96191c1623da45de2e52a589.png"  
  },  
  {  
    "itemID": 102000024,  
    "name": "Chrono",  
    "skill_id": "3806",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202412/6d5de642b070e208a38b037d8233df85.png"  
  },  
  {  
    "itemID": 102000025,  
    "name": "Skyler",  
    "skill_id": "4006",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/547dea01d82886891297443e8e9d270f.png"  
  },  
  {  
    "itemID": 102000026,  
    "name": "Shirou",  
    "skill_id": "4106",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/dbe25891f13c5752e84ad7daf57106cc.png"  
  },  
  {  
    "itemID": 102000027,  
    "name": "Andrew the Fierce",  
    "skill_id": "4206",  
    "png_image": "https://i.postimg.cc/ZK1Gzj1T/Andrew-The-Fierce.png"  
  },  
  {  
    "itemID": 102000028,  
    "name": "Maro",  
    "skill_id": "4306",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/8af9a328d62a330a76221b79670daf37.png"  
  },  
  {  
    "itemID": 102000030,  
    "name": "Thiva",  
    "skill_id": "4606",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/217c0184667efa92bcec0caa73af73b9.png"  
  },  
  {  
    "itemID": 102000031,  
    "name": "Dimitri",  
    "skill_id": "4706",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/024c98913571304db2cba9d257e7291a.png"  
  },  
  {  
    "itemID": 102000032,  
    "name": "Leon",  
    "skill_id": "4906",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/b79f47950001fb7f7130a6b3752b3446.png"  
  },  
  {  
    "itemID": 102000033,  
    "name": "Otho",  
    "skill_id": "5006",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/d0ea6553e85abbf0a8b718e29900b7f5.png"  
  },  
  {  
    "itemID": 102000034,  
    "name": "Nairi",  
    "skill_id": "5206",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/e21eb41a3705ff817156dd5758157274.png"  
  },  
  {  
    "itemID": 102000036,  
    "name": "Kenta",  
    "skill_id": "5406",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/f867281184a63b0ac1bd9cc03a484bce.png"  
  },  
  {  
    "itemID": 102000037,  
    "name": "Homer",  
    "skill_id": "5506",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/26d226fa08410cc418959e3cc30095c7.png"  
  },  
  {  
    "itemID": 102000038,  
    "name": "J.Biebs",  
    "skill_id": "5706",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202412/d3eb3130503cd726a5b7bce881d46c93.png"  
  },  
  {  
    "itemID": 102000039,  
    "name": "Tatsuya",  
    "skill_id": "5806",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20229/e37e48adf72a2c014c2bfa8ed483f5b5.png"  
  },  
  {  
    "itemID": 102000040,  
    "name": "Santino",  
    "skill_id": "6006",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20233/a3810f993d32077e88c5226625bb55a9.png"  
  },  
  {  
    "itemID": 102000041,  
    "name": "Orion",  
    "skill_id": "6206",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20238/4f4fc6c6d43fc3bb5ef4617f9f5340f7.png"  
  },  
  {  
    "itemID": 102000042,  
    "name": "Alvaro Rageblast",  
    "skill_id": "6306",  
    "png_image": "https://i.postimg.cc/k5k6x0H0/Alvaro-Rageblast.png"  
  },  
  {  
    "itemID": 102000043,  
    "name": "Awakened Alok",  
    "skill_id": "22016",  
    "png_image": "https://i.postimg.cc/KvHMG3Nc/Awakend-Alok.png"  
  },  
  {  
    "itemID": 102000044,  
    "name": "Ignis",  
    "skill_id": "6706",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202311/a393f95f57bdaa3d2031a052b6acef24.png"  
  },  
  {  
    "itemID": 102000045,  
    "name": "Ryden",  
    "skill_id": "6806",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20241/fb808bb7cfc4820384c7a52fee3201ea.png"  
  },  
  {  
    "itemID": 102000046,  
    "name": "Kairos",  
    "skill_id": "6906",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20246/ed1e34b6c47b37675eae84daffdf63b1.png"  
  },  
  {  
    "itemID": 102000051,  
    "name": "Koda",  
    "skill_id": "7206",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/202412/b2f635a96ed787a8e540031402ea751b.png"  
  },  
  {  
    "itemID": 102000052,  
    "name": "Oscar",  
    "skill_id": "7306",  
    "png_image": "https://dl.dir.freefiremobile.com/common/web_event/official2.ff.garena.all/20252/d5d04e40eb00900e96a28828decdaff0.png"  
  },  
  {  
    "itemID": 101000015,  
    "name": "Kelly The Swift",  
    "skill_id": "2506",  
    "png_image": "https://i.postimg.cc/BnpRPsjv/Kelly-The-Swift.png"  
  },  
  {  
    "itemID": 102000020,  
    "name": "Elite Hayato",  
    "skill_id": "3206",  
    "png_image": "https://i.postimg.cc/KzH9r8bZ/Hayato-Firebrand.png"  
  },  
  {  
    "itemID": 102000029,  
    "name": "D-Bee",  
    "skill_id": "4506",  
    "png_image": "https://freefiremobile-a.akamaihd.net/common/web_event/official2.ff.garena.all/img/20228/f1a09717ed71e7302da8d4cc889d2e33.png"  
  }  
]  

def assign_outfits(clothes):
    """Categorize clothes list; fallback occurs at image load."""
    # Inicializa todas as chaves
    outfits = {k: [] if k in ["HEADS", "MASKS"] else None for k in IMAGE_POSITIONS if k != "CHARACTER"}

    top_count = 0
    for cid in clothes or []:
        s = str(cid)  # garante string
        prefix = s[:3]
        if prefix == "211":
            outfits["HEADS"].append(s)
            outfits["MASKS"].append(s)
        elif prefix == "214" and outfits["FACEPAINTS"] is None:
            outfits["FACEPAINTS"] = s
        elif prefix == "203":
            top_count += 1
            key = "TOPS" if top_count == 1 else "SECOND_TOP"
            outfits[key] = s
        elif prefix == "204" and outfits["BOTTOMS"] is None:
            outfits["BOTTOMS"] = s
        elif prefix == "205" and outfits["SHOES"] is None:
            outfits["SHOES"] = s
        elif prefix == "907" and outfits["ARMS"] is None:
            outfits["ARMS"] = s
        elif prefix == "914" and outfits["TRAN"] is None:
            outfits["TRAN"] = s

    return outfits


def load_outfit_image(category, candidate_ids, fallback_id):
    """Load outfit image; if missing, load fallback."""
    folder = "TOPS" if category == "SECOND_TOP" else category
    ids = candidate_ids or []
    if not isinstance(ids, list): ids = [ids]
    for cid in ids:
        if cid:
            img = fetch_image(GITHUB_BASE_URL.format(folder=folder, id=cid))
            if img: return img
    return fetch_image(GITHUB_BASE_URL.format(folder=folder, id=fallback_id))


def get_character_image(avatar_id):
    """Return character image or None."""
    for char in characters:
        if char.get("itemID") == avatar_id:
            return fetch_image(char.get("png_image"))
    return None


def overlay_images(outfits, avatar_id, custom_bg_url=None):
    bg = fetch_image(custom_bg_url) if custom_bg_url else (CACHED_BG.copy() if CACHED_BG else None)
    if not bg:
        raise RuntimeError("Background load failed.")

    if CACHED_OVERLAY:
        ol = CACHED_OVERLAY.copy()
        bg = bg.resize(ol.size, Image.LANCZOS)
        bg.paste(ol, (0, 0), ol)

    # Paste outfits
    for cat, pos in IMAGE_POSITIONS.items():
        if cat == "CHARACTER": continue
        img = load_outfit_image(cat, outfits.get(cat), FALLBACK_ITEMS[cat])
        img = img.resize((pos['w'], pos['h']), Image.LANCZOS)
        bg.paste(img, (pos['x'], pos['y']), img)

    # Paste character
    char_img = get_character_image(avatar_id)
    if char_img:
        pos = SPECIAL_CHARACTER_POSITIONS.get(str(avatar_id), IMAGE_POSITIONS['CHARACTER'])
        char_img = char_img.resize((pos['w'], pos['h']), Image.LANCZOS)
        bg.paste(char_img, (pos['x'], pos['y']), char_img)

    buf = BytesIO()
    bg.save(buf, 'PNG')
    buf.seek(0)
    return buf

# === Crypto & Protobuf Helpers ===
def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    instance = message_type()
    instance.ParseFromString(encoded_data)
    return instance

def json_to_proto(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

def get_token(password: str, uid: str, max_retries: int = 3) -> Optional[dict]:
   
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": "GarenaMSDK/4.0.19P4(G011A ;Android 9;en;US;)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close"
    }
    data = {
        "uid": str(uid),
        "password": str(password),
        "response_type": "token",
        "client_type": "2",
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": "100067"
    }

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                wait_time = min((2 ** attempt) + random.uniform(0, 1), 10)
                time.sleep(wait_time)

            res = requests.post(url, headers=headers, data=data, timeout=15)
            
            if res.status_code == 200:
                token_json = res.json()
                if "access_token" in token_json and "open_id" in token_json:
                    return token_json
            
            elif res.status_code == 429:
                retry_after = res.headers.get('Retry-After', 5)
                time.sleep(float(retry_after))
                continue
            
        except (RequestException, ValueError) as e:
            continue

    return None

def get_single_response() -> str:
    """Get authentication token."""
    uid = '3790435245'
    password = 'B8623E3106EDB07BD6D58B0D7688E5B7193854527368C9AF143984381BAFDBCE'
    versionob = fetch_attversion()
    token_data = get_token(password, uid)
    if not token_data:
        raise ValueError("Failed to get token: Wrong UID or Password")

    game_data = my_pb2.GameData()
    game_data.timestamp = "2024-12-05 18:15:32"
    game_data.game_name = "free fire"
    game_data.game_version = 1
    game_data.version_code = "1.108.3"
    game_data.os_info = "Android OS 9 / API-28 (PI/rel.cjw.20220518.114133)"
    game_data.device_type = "Handheld"
    game_data.network_provider = "Verizon Wireless"
    game_data.connection_type = "WIFI"
    game_data.screen_width = 1280
    game_data.screen_height = 960
    game_data.dpi = "240"
    game_data.cpu_info = "ARMv7 VFPv3 NEON VMH | 2400 | 4"
    game_data.total_ram = 5951
    game_data.gpu_name = "Adreno (TM) 640"
    game_data.gpu_version = "OpenGL ES 3.0"
    game_data.user_id = "Google|74b585a9-0268-4ad3-8f36-ef41d2e53610"
    game_data.ip_address = "172.190.111.97"
    game_data.language = "en"
    game_data.open_id = token_data['open_id']
    game_data.access_token = token_data['access_token']
    game_data.platform_type = 4
    game_data.device_form_factor = "Handheld"
    game_data.device_model = "Asus ASUS_I005DA"
    game_data.field_60 = 32968
    game_data.field_61 = 29815
    game_data.field_62 = 2479
    game_data.field_63 = 914
    game_data.field_64 = 31213
    game_data.field_65 = 32968
    game_data.field_66 = 31213
    game_data.field_67 = 32968
    game_data.field_70 = 4
    game_data.field_73 = 2
    game_data.library_path = "/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/lib/arm"
    game_data.field_76 = 1
    game_data.apk_info = "5b892aaabd688e571f688053118a162b|/data/app/com.dts.freefireth-QPvBnTUhYWE-7DMZSOGdmA==/base.apk"
    game_data.field_78 = 6
    game_data.field_79 = 1
    game_data.os_architecture = "32"
    game_data.build_number = "2019117877"
    game_data.field_85 = 1
    game_data.graphics_backend = "OpenGLES2"
    game_data.max_texture_units = 16383
    game_data.rendering_api = 4
    game_data.encoded_field_89 = "\u0017T\u0011\u0017\u0002\b\u000eUMQ\bEZ\u0003@ZK;Z\u0002\u000eV\ri[QVi\u0003\ro\t\u0007e"
    game_data.field_92 = 9204
    game_data.marketplace = "3rd_party"
    game_data.encryption_key = "KqsHT2B4It60T/65PGR5PXwFxQkVjGNi+IMCK3CFBCBfrNpSUA1dZnjaT3HcYchlIFFL1ZJOg0cnulKCPGD3C3h1eFQ="
    game_data.total_storage = 111107
    game_data.field_97 = 1
    game_data.field_98 = 1
    game_data.field_99 = "4"
    game_data.field_100 = "4"

    try:
        serialized_data = game_data.SerializeToString()
        encrypted_data = aes_cbc_encrypt(AES_KEY, AES_IV, serialized_data)
        edata = binascii.hexlify(encrypted_data).decode()

        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Content-Type': "application/octet-stream",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': f'{versionob}'
        }

        response = requests.post(
            "https://loginbp.common.ggbluefox.com/MajorLogin",
            data=bytes.fromhex(edata),
            headers=headers,
            verify=False
        )

        if response.status_code == 200:
            example_msg = output_pb2.Garena_420()
            example_msg.ParseFromString(response.content)
            response_dict = parse_response(str(example_msg))
            
            return response_dict.get("token")
        
        raise ValueError(f"HTTP {response.status_code} - {response.reason}")

    except Exception as e:
        raise ValueError(f"Token generation failed: {str(e)}")


def parse_response(content: str) -> dict:
    """Parse protobuf response into dictionary."""
    return dict(
        line.split(":", 1)
        for line in content.split("\n")
        if ":" in line
    )

def GetAccountInformation(uid: str, unk: str, region: str, endpoint: str) -> dict:
    """Get player account information."""
    region = region.upper()
    if region not in SUPPORTED_REGIONS:
        raise ValueError(f"Unsupported region: {region}")

    try:
        # Monta o payload protobuf
        proto_message = main_pb2.GetPlayerPersonalShow()
        json_format.ParseDict({'a': uid, 'b': unk}, proto_message)
        payload = proto_message.SerializeToString()

        # Encripta com AES CBC
        data_enc = aes_cbc_encrypt(MAIN_KEY, MAIN_IV, payload)

        # Pega o token JWT e limpa possíveis aspas
        jwtlogin = get_single_response().strip().replace('"', '').replace("'", '')


        print(f"[DEBUG] JWT usado: {jwtlogin}")
        versionob = fetch_attversion()
        headers = {
            'X-Unity-Version': '2018.4.11f1',
            'ReleaseVersion': f'{versionob}',
            'Content-Type': 'application/octet-stream',
            'X-GA': 'v1 1',
            'Authorization': f'Bearer {jwtlogin}',
            'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 7.1.2; ASUS_Z01QD Build/QKQ1.190825.002)',
            'Host': 'clientbp.ggblueshark.com',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip'
        }

        url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"

        with httpx.Client(timeout=TIMEOUT) as client:
            try:
                response = client.post(url, data=data_enc, headers=headers)
                response.raise_for_status()

                # Decodificar a resposta protobuf
                decoded_message = AccountPersonalShow_pb2.AccountPersonalShowInfo()
                decoded_message.ParseFromString(response.content)

                # Converter para JSON legível
                json_data = json.loads(json_format.MessageToJson(decoded_message))

                return json_data

            except httpx.HTTPStatusError as http_err:
                print(f"[HTTP ERROR] Status: {http_err.response.status_code} - {http_err.response.text}")
                raise ValueError(f"HTTP Error {http_err.response.status_code}: {http_err.response.text}")

            except httpx.RequestError as req_err:
                print(f"[REQUEST ERROR] Request to {req_err.request.url} failed: {str(req_err)}")
                raise ValueError(f"Request error: {str(req_err)}")

            except Exception as e:
                print(f"[CLIENT ERROR] Unexpected error in HTTP client: {str(e)}")
                raise ValueError(f"Client error: {str(e)}")

    except Exception as e:
        print(f"[GENERAL ERROR] {str(e)}")
        raise ValueError(f"Failed to get account info: {str(e)}")


def cached_endpoint(ttl=300):  
    def decorator(fn):  
        @wraps(fn)  
        def wrapper(*a, **k):  
            key = (request.path, tuple(request.args.items()))  
            if key in cache:  
                data = cache[key]  
                return send_file(BytesIO(data), mimetype='image/png')  
            result = fn(*a, **k)  
            # fn returns Response or tuple(bytes, status)  
            if isinstance(result, tuple) and isinstance(result[0], bytes):  
                data, status = result  
            elif isinstance(result, bytes):  
                data, status = result, 200  
            else:  
                return result  
            cache[key] = data  
            return send_file(BytesIO(data), mimetype='image/png'), status  
        return wrapper  
    return decorator  

@app.route('/refresh', methods=['GET','POST'])
def refresh_tokens_endpoint():
    try:
        asyncio.run(initialize_tokens())
        return jsonify({'message':'Tokens refreshed for all regions.'}),200
    except Exception as e:
        return jsonify({'error': f'Refresh failed: {e}'}),500

@app.route('/outfit-image', methods=['GET'])
@cached_endpoint(ttl=300)
def outfit_image():
    uid = request.args.get('uid')
    region = request.args.get('region')
    bg_url = request.args.get('bg')
    if not uid or not region:
        return jsonify({'error': 'uid and region required'}), 400

    
    try:
        data = GetAccountInformation(uid, "7", region, "/GetPlayerPersonalShow")
    except Exception as e:
        logging.error("Fetch error: %s", e)
        return jsonify({'error': 'Invalid uid or region; failed to fetch player data'}), 400
    clothesv = data.get("profileInfo", {}).get("clothes", [])
    weaponSkin = data.get("basicInfo", {}).get("weaponSkinShows", [])
    weaponSkin_filtered = [w for w in weaponSkin if str(w).startswith(("907", "914"))]
    items = clothesv + weaponSkin_filtered
    clothes = list(map(str, items))  # garante que cada item é string
    avatar_id = data.get('profileInfo', {}).get('avatarId')
    outfits = assign_outfits(clothes)
    try:
        img_buf = overlay_images(outfits, avatar_id, bg_url)
        return send_file(img_buf, mimetype='image/png')
    except Exception as e:
        logging.error("Generation error: %s", e)
        return jsonify({'error': 'Failed to generate image'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
