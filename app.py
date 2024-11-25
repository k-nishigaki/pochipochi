from flask import Flask, render_template, request, Response
import os
from urllib.parse import urlparse
from pymongo import MongoClient
from datetime import datetime as dt
from flask_httpauth import HTTPBasicAuth

app = Flask(__name__)

auth = HTTPBasicAuth()

MONGO_URL = os.environ.get('MONGODB_HOST')
MONGO_DB = os.environ.get('MONGODB_NAME')
MONGO_USER = os.environ.get('MONGODB_USER')
MONGO_PASS = os.environ.get('MONGODB_PASS')

if MONGO_URL and MONGO_USER and MONGO_PASS:
    uri = f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_URL}/?retryWrites=true&w=majority&appName=Pochipochi"
    con = MongoClient(uri)
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
    
    count_obj = {'name': name, 'date': dt.now()}
    print(count_obj)
    db.count.insert_one(count_obj)
    return Response(name)

@app.route('/iphone')
def iphone():
    return render_template('iphone.html', title='pochiopchi iphone')

     
@app.route('/count/', methods=["GET"])
@auth.login_required
def count():
    begin_time = request.args.get('begin_time')
    end_time = request.args.get('end_time')
    print(begin_time)
    print(end_time)
    print('begin', dt.strptime(begin_time, '%Y%m%d_%H%M%S'))
    print('end', dt.strptime(end_time, '%Y%m%d_%H%M%S'))
    group = {"$group": {"_id": "$name", "count": {"$sum": 1}}}
    match = {"$match": { "date": {"$gt": dt.strptime(begin_time, '%Y%m%d_%H%M%S'), "$lt": dt.strptime(end_time, '%Y%m%d_%H%M%S')} }}
    sort = {"$sort": {"_id": 1}}
    pipe = [match, group, sort]
    count_obj = db.count.aggregate(pipe)
    count_lst = []
    for doc in count_obj:
        print(doc)
        count_lst.append({"name": doc["_id"], "count": doc["count"]})

    return render_template('count.html', title="ポチポチ祭 Ver. beta", count=count_lst)

if __name__ == '__main__':
    app.run(debug=True)
