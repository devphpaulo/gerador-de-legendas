import pika
from time import sleep
import json
import os
import redis
import firebase_admin
from firebase_admin import credentials, storage
import shutil

from generator import gerar_legenda

cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'gerador-de-legendas'
})

pika_conn = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq', heartbeat=600))
channel = pika_conn.channel()


def callback(ch, method, properties, body):
     try:
        body_str = body.decode('utf-8')
        body = json.loads(body_str)

        idiomas = body['idiomas'].split(' ')
        idioma_original = body["original"]

        # Atualizar andamento no DB :
        r = redis.Redis(host='redis', port=6379, db=0)
        r.json().set(body['token'], '$.andamento', 1)

        print('Received: ', body["filename"])

        # Salvar o vídeo temporariamente
        bucket = storage.bucket()
        file = bucket.get_blob(f'videos/{body["token"]}')
        file.download_to_filename(f'videos/{body["token"]}')

        # Gerar Legenda e salvar arquivos .srt
        legendas = gerar_legenda(body["token"], idiomas, idioma_original)

        for i, l in zip(idiomas, legendas):
            with open(f'legendas/{body["token"]}-{i}.srt',  'w') as file:
                file.write(l)

        # Comprimir os arquivos ei enviar o zip para a nuvem
        shutil.make_archive(f'zip/{body["token"]}', 'zip', 'legendas')

        zipf = bucket.blob(f'zip/{body["token"]}.zip')
        zipf.upload_from_filename(f'zip/{body["token"]}.zip')

        # Registrar Conclusão no D:B 
        r.json().set(body['token'], '$.andamento', 2)

        # Retirar processo da frabbitmq ila 
        channel.basic_ack(delivery_tag = method.delivery_tag)

        # Limpar diretórios
        os.system("rm -rf legendas/*")
        os.system("rm -rf videos/*")
        os.system("rm -rf audios/*")
        os.system("rm -rf zip/*")

        print('Finalizado: ' + body["filename"])
     except:
        print("Erro processando: " + body["filename"])

        return

channel.queue_declare('processos', durable=True)
channel.basic_consume(queue='processos', on_message_callback=callback)
channel.start_consuming()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

