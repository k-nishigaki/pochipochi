from flask import Flask, render_template, request, Response
import os
from urllib.parse import urlparse
from pymongo.mongo_client import MongoClient
from datetime import datetime as dt
from flask_httpauth import HTTPBasicAuth
from zoneinfo import ZoneInfo

app = Flask(__name__)

auth = HTTPBasicAuth()

MONGO_URL = os.environ.get('MONGODB_HOST')
MONGO_DB = os.environ.get('MONGODB_NAME')
MONGO_USER = os.environ.get('MONGODB_USER')
MONGO_PASS = os.environ.get('MONGODB_PASS')

if MONGO_URL and MONGO_USER and MONGO_PASS:
    uri = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_URL}/?retryWrites=true&w=majority&appName=Pochipochi"
    print(uri)
    con = MongoClient(uri)
    try:
        con.admin.command('ping')
        print("Pinged your deployment. You successfully connected to MongoDB!")
    except Exception as e:
        print(e)

    db = con[MONGO_DB]
else:
    con = MongoClient('localhost', 27017)
    db = con['pochipochi']

@auth.get_password
def get_pw(username):
    if username == "kamiya":
        return "nao"
    return None

@app.route('/')
def pochipochi():
    return render_template('index.html', title="ポチポチ祭 Ver. beta")

@app.route('/pochipochi', methods=["POST"])
def post(name=''):
    if request.method == 'POST':
        name = request.form.get('name')
        print(name)
    else: 
        name = "NoName"
    
    count_obj = {'name': name, 'date': dt.now(JST)}
    print(count_obj)
    db.count.insert_one(count_obj)
    return Response(name)

JST = ZoneInfo("Asia/Tokyo")
UTC = ZoneInfo("UTC")

@app.route('/count/', methods=["GET"])
@auth.login_required
def count():
    date_str = request.args.get("date")
    begin_t_str = request.args.get("begin_t")
    end_t_str = request.args.get("end_t")

    tz_mode = request.args.get("tz") or "jst"

    # 旧UI/互換:
    begin_dt_str = request.args.get("begin_dt") # "2025-11-28T10:00"
    end_dt_str = request.args.get("end_dt")
    begin_time = request.args.get("begin_time") # "20251128_100000"
    end_time = request.args.get("end_time")

    # 1) 新UI（date + begin_t + end_t）を最優先
    if date_str and begin_t_str and end_t_str:
        try:
            d = dt.strptime(date_str, "%Y-%m-%d").date()
            bt = dt.strptime(begin_t_str, "%H:%M").time()
            et = dt.strptime(end_t_str, "%H:%M").time()

            start_naive = dt.combine(d, bt)
            end_naive = dt.combine(d, et)

            # ★ JST集計ボタンのときは JST として解釈 → UTCに変換して検索
            if tz_mode == "jst":
                start = start_naive.replace(tzinfo=JST).astimezone(UTC).replace(tzinfo=None)
                end   = end_naive.replace(tzinfo=JST).astimezone(UTC).replace(tzinfo=None)
            else:
                # ★ UTC集計ボタンのときはそのまま UTC とみなす（naiveのまま）
                start = start_naive
                end = end_naive

        except ValueError:
            now = dt.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 2) 次点: datetime-local の begin_dt/end_dt（前回のUI互換）
    elif begin_dt_str and end_dt_str:
        try:
            start = dt.strptime(begin_dt_str, "%Y-%m-%dT%H:%M")
            end = dt.strptime(end_dt_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            now = dt.now()
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 3) 旧: date だけ
    elif date_str:
        try:
            target = dt.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            target = dt.now()
        start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

    # 4) 旧: begin_time/end_time
    elif begin_time and end_time:
        start = dt.strptime(begin_time, "%Y%m%d_%H%M%S")
        end = dt.strptime(end_time, "%Y%m%d_%H%M%S")

    # 5) 何もなければ今日
    else:
        now = dt.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59, microsecond=999999)

    # start > end 対策（同日内の逆指定想定）
    if start > end:
        start, end = end, start

    # Mongo 集計（名前別カウント）
    group = {"$group": {"_id": "$name", "count": {"$sum": 1}}}
    match = {"$match": {"date": {"$gte": start, "$lte": end}}}
    sort = {"$sort": {"_id": 1}}
    pipe = [match, group, sort]

    count_obj = db.count.aggregate(pipe)
    count_lst = [{"name": doc["_id"], "count": doc["count"]} for doc in count_obj]

    # 合計回数
    total = sum(c["count"] for c in count_lst)

    # ---- 円グラフ用データ ----
    ORDER = ["i_see", "laugh", "question", "good"]
    count_dict = {c["name"]: c["count"] for c in count_lst}
    labels = [k for k in ORDER if k in count_dict]
    values = [count_dict[k] for k in labels]

    # ---- UI初期値 ----
    date_value = start.strftime("%Y-%m-%d")
    begin_value = start.strftime("%H:%M")
    end_value = end.strftime("%H:%M")

    # タイトル（フォームから来る）
    chart_title = request.args.get("title") or "ポチポチ内訳"

    # ★ 画面表示用に JST/UTC どっちも作る
    #   start/end は “検索に使うUTC naive” なので JSTに戻して表示
    start_utc = start.replace(tzinfo=UTC)
    end_utc = end.replace(tzinfo=UTC)
    start_jst = start_utc.astimezone(JST)
    end_jst = end_utc.astimezone(JST)

    return render_template(
        "count.html",
        title="ポチポチ祭 Ver. beta",
        count=count_lst,
        labels=labels,
        values=values,
        chart_title=chart_title,
        total=total,
        tz_mode=tz_mode,  # ★どのボタンで集計したか

        # ★プレビュー用文字列
        start_jst_str=start_jst.strftime("%Y-%m-%d %H:%M"),
        end_jst_str=end_jst.strftime("%Y-%m-%d %H:%M"),
        start_utc_str=start_utc.strftime("%Y-%m-%d %H:%M"),
        end_utc_str=end_utc.strftime("%Y-%m-%d %H:%M"),

        # 入力欄の初期値（JST基準の見た目にしたいので JST側）
        date_value=start_jst.strftime("%Y-%m-%d"),
        begin_value=start_jst.strftime("%H:%M"),
        end_value=end_jst.strftime("%H:%M"),
    )

if __name__ == '__main__':
    app.run(debug=True)
