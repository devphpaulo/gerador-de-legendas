from flask import Flask, render_template, request, redirect, flash, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid
import pika
import json
import redis
import os
import firebase_admin
from firebase_admin import credentials, storage
import threading


app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('secret')

cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'gerador-de-legendas'
})


def upload(processo):
    bucket = storage.bucket()
    blob = bucket.blob(f'videos/{processo["token"]}')
    blob.upload_from_filename(f'videos/{processo["filename"]}')

    # Colocar processo na Fila
    pika_conn = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = pika_conn.channel()
    channel.queue_declare('processos', durable=True)
    channel.queue_bind(exchange='amq.direct', queue='processos')
    channel.basic_publish(exchange='amq.direct', routing_key='processos', body=json.dumps(processo))

    pika_conn.close()

    # Limpar Diretório temporário
    os.system('rm -rf videos/*')



@app.route('/')
def main():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    idiomas = " ".join([i for i in request.form if i != 'original']) # Retorna algo como 'pt en' ou 'en'

    idioma_original = request.form["original"]

    file = request.files['video']
    # Checa se o arquivo realmente foi enviado
    if file.filename == '':
        flash('Arquivo Inválido!') 
        return redirect('/')

    filename = secure_filename(file.filename)
    
    token = str(uuid.uuid4()) # Esse token será usado para acompanhar o processo
    processo = {
        'token': token,
        'filename': filename,
        'idiomas': idiomas,
        'original': idioma_original,
        'data_inicio': datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        'andamento': 0, #  0 Não Iniciado 1 Iniciado 2 Finalizado
    }

    # Salva o arquivo e faz o upload assíncrono para a nuvem
    file.save(f'videos/{filename}') 
    thread = threading.Thread(target=lambda: upload(processo))
    thread.start()

      
    # Colocar Processo no DB 
    r = redis.Redis(host='redis', port=6379, db=0)
    r.json().set(token, '$', processo) 

    flash(f'Acompanhe o processo utilizando o token {token}')
    return redirect('/')


@app.route('/processos', methods=['GET'])
def processos():
    return render_template('processos.html')

@app.route('/info/<token>')
def info(token):
    r = redis.Redis(host='redis', port=6379, db=0)
    proccess = r.json().get(token)

    return proccess 

@app.route('/downloads/<token>')
def downloads(token):
    bucket = storage.bucket()
    blob = bucket.get_blob(f'zip/{token}.zip')
    blob.download_to_filename(f"zip/{token}.zip")

    return send_from_directory('zip', f"{token}.zip")
              

if __name__ == "__main__":
        app.run(debug=True, port=5000, host='0.0.0.0')
