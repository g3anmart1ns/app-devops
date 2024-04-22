# -*- coding: utf-8 -*-

import os
import pika
from flask import Flask, request, jsonify
from prometheus_client import make_wsgi_app, Counter, Histogram
from werkzeug.middleware.dispatcher import DispatcherMiddleware
import time

app = Flask(__name__)

# Configuração do RabbitMQ
host = os.getenv("RABBITMQ_HOST", "localhost")
port = os.getenv("RABBITMQ_PORT", 5672)
queue = os.getenv("RABBITMQ_QUEUE", "hello")

# Configuração do Prometheus
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})
REQUEST_COUNT = Counter(
    'app_request_count',
    'Application Request Count',
    ['method', 'endpoint', 'http_status']
)
REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds',
    'Application Request Latency',
    ['method', 'endpoint']
)

html = """ 
<br>Type your favourite <i>pudim</i> flavour: 
<br>
<form method='POST' action='/'>
    <input type='text' name='flavour'>
    <input type='submit'>
</form>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        app.logger.info(request.form.get("flavour"))
        enqueue(request.form.get("flavour"))
    return html

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"})

def enqueue(value):
    app.logger.info("Received message: %s", value)
    params = pika.ConnectionParameters(host=host, port=port)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='', routing_key=queue, body=value)
    connection.close()
    app.logger.info("Enqueued message on host %s:%s queue %s: %s", host, port,
                    queue, value)

# Função para registrar métricas do Prometheus
@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    latency = time.time() - request.start_time
    REQUEST_COUNT.labels(request.method, request.path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, request.path).observe(latency)
    return response

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)

