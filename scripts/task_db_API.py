import os
import json
import tempfile
import io
import zipfile
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from pymongo.errors import AutoReconnect, ConnectionFailure, PyMongoError, OperationFailure
from flask import Flask, flash, request, redirect, url_for, render_template, send_from_directory
from typing import (
    List,
    Any,
    Dict,
)

# папка для сохранения загруженных файлов
# UPLOAD_FOLDER = os.path.dirname(os.path.realpath(__file__))
UPLOAD_FOLDER = tempfile.gettempdir()
# UPLOAD_FOLDER = os.path.dirname(os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir)))
# расширения файлов, которые разрешено загружать
ALLOWED_EXTENSIONS = {'txt', 'ttl', 'json'}

DB_NAME = "tasks_db"
COLLECTION = "library_tasks"
CLIENT = "mongodb://localhost:27017"


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

class MongoDB(object):
    def __init__(self, db_name: str = None, collection: str = None):
        self._client = MongoClient('localhost', 27017)
        self._collection = self._client[db_name][collection]
        
def allowed_file(filename):
    """ Функция проверки расширения файла """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
           
db = MongoDB(db_name=DB_NAME, collection=COLLECTION)
collection = db._collection

@app.route('/home/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        index = request.form['index']
        if index == "1":
            return redirect(url_for("upload_in_mongo"))
        elif index == "2":
            return redirect(url_for("get_from_mongo"))
    return'''
    <!doctype html>
    <form action="/home/" method="POST">
        <!-- скрытый параметр -->
        <input type="hidden" name="index" value="1">
        <input type="submit" class="btn btn-dark" value="Загрузить в БД">
    </form>

    <form action="/home/" method="POST">
        <!-- скрытый параметр -->
        <input type="hidden" name="index" value="2">
        <input type="submit" class="btn btn-dark" value="Получить из БД">
    </form>
    </html>
    '''
        

# @app.route('/process_data/<index>/', methods=['POST'])
# def doit(index):
#     # ... обработать данные ...

@app.route('/upload_in_mongo', methods=['GET', 'POST'])
def upload_in_mongo():
    
    # db = MongoDB(db_name=DB_NAME, collection=COLLECTION)
    # collection = db._collection
    
    if request.method == 'POST':
        # проверим, передается ли в запросе файл 
        if 'file1' not in request.files or 'file2' not in request.files:
            # После перенаправления на страницу загрузки
            # покажем сообщение пользователю 
            flash('Не могу прочитать файл')
            return redirect(request.url)
        
        task_name = request.form.get('task_name')
        
        files = []
        files.append(request.files['file1'])
        files.append(request.files['file2'])
        # Если файл не выбран, то браузер может
        # отправить пустой файл без имени.
        if files[0].filename == '' or files[1].filename == '':
            flash('Нет выбранного файла')
            return redirect(request.url)
        for file in files:
            if file and allowed_file(file.filename):
                # безопасно извлекаем оригинальное имя файла
                filename = secure_filename(file.filename)
                # сохраняем файл
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                # если все прошло успешно, то перенаправляем  
                # на функцию-представление `download_file` 
                # для скачивания файла
                
        if collection.find_one({'task_name': task_name}) is not None:
            flash('Данная задача уже существует')
            return redirect(request.url)
        
        ttl_file = ""
        with open(os.path.join(UPLOAD_FOLDER, request.files['file1'].filename), 'r', encoding='utf-8') as f:
            ttl_file = f.read()
            print(ttl_file)

        json_file = ""
        with open(os.path.join(UPLOAD_FOLDER, request.files['file2'].filename), 'r', encoding='utf-8') as f:
            json_file = f.read()
            print(json_file)
            
        collection.insert_one({'task_name': task_name, 'ttl_file': ttl_file, 'json_file': json_file})
                
        return redirect(url_for("home"))
    return '''
    <!doctype html>
    <title>Добавить новую задачу в БД</title>
    
    <h1>Название задачи</h1>
    <form method=post enctype=multipart/form-data>
        <input type="text" name="task_name">

    <h1>Добавить новый файл .ttl</h1>
    <form method=post enctype=multipart/form-data>
        <input type=file name=file1>

    <h1>Добавить новый файл .json</h1>
    <form method=post enctype=multipart/form-data>
        <input type=file name=file2>

    <h1>Загрузить файлы</h1>
    <form method=post enctype=multipart/form-data>
        <input type=submit value=Upload>

    </form>
    </html>
    '''
    
@app.route('/get_from_mongo/', methods=['GET', 'POST'])
def get_from_mongo():
    
    json_task: Dict[str, Any] = {}
    
    if request.method == 'POST':
        
        if 'index' not in request.form:
            if 'task_name' not in request.form:
                # После перенаправления на страницу загрузки
                # покажем сообщение пользователю 
                flash('Не могу прочитать файл')
                return redirect(request.url)
        
        index = request.form['index']
        task_name = request.form.get('task_name')
        
        if index == '1':
            return redirect(url_for("home"))
        else:
            try:  
                json_task = collection.find_one({'task_name': task_name}) 
            except OperationFailure as e:
                return {'Successful_status': False, 'Info': "TypeError: MongoDB find error. Document not found."}
            
            ttl_file = json_task['ttl_file']
            json_file = json_task['json_file']
            
            with open(os.path.join(UPLOAD_FOLDER, f'{task_name}.ttl'), 'w', encoding='utf-8') as f:
                f.write(ttl_file)
                
            with open(os.path.join(UPLOAD_FOLDER, f'{task_name}.json'), 'w', encoding='utf-8') as f:
                f.write(json_file)
                
            with zipfile.ZipFile(os.path.join(UPLOAD_FOLDER, f'{task_name}_archive.zip'), 'w') as zip_arch:
                zip_arch.write(os.path.join(UPLOAD_FOLDER, f'{task_name}.ttl'), arcname=f'{task_name}.ttl', compress_type=zipfile.ZIP_DEFLATED)
                zip_arch.write(os.path.join(UPLOAD_FOLDER, f'{task_name}.json'), arcname=f'{task_name}.json', compress_type=zipfile.ZIP_DEFLATED)
                
            return send_from_directory(directory=UPLOAD_FOLDER, path=f'{task_name}_archive.zip', as_attachment=True)

    return '''
    <!doctype html>
    <title>Получить задачу из БД</title>
    
    <h1>Название задачи</h1>
    <form action="/get_from_mongo/" method="POST">
        <div><input type="text" name="task_name"></label></div>
        <input type="hidden" name="index" value="0">
        <input type="submit" class="btn btn-dark" value="Submit">
    </form>
    
    <form action="/get_from_mongo/" method="POST">
        <!-- скрытый параметр -->
        <input type="hidden" name="index" value="1">
        <input type="submit" class="btn btn-dark" value="Вернуться в /home">
    </form>
    </html>
    '''

if __name__ == '__main__':
    print(os.getenv('PORT'))
    app.secret_key = 'super secret key'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(host='0.0.0.0', use_reloader=False)