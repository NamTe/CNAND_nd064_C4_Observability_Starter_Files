import pymongo
import logging
from flask import Flask, jsonify, render_template, request
from flask_opentracing import FlaskTracing
from flask_pymongo import PyMongo
from jaeger_client import Config
from jaeger_client.metrics.prometheus import PrometheusMetricsFactory
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from prometheus_flask_exporter import PrometheusMetrics

logging.getLogger('').handlers = []
logging.basicConfig(format='%(message)s', level=logging.DEBUG)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

metrics = PrometheusMetrics(app)
metrics.info("backend", "Backend Application info", version="1.0.3")

config = Config(
    config={
        "sampler": {"type": "const", "param": 1},
        "logging": True,
        "reporter_batch_size": 1,
    },
    service_name="backend",
    metrics_factory=PrometheusMetricsFactory(service_name_label="backend"),
)
jaeger_tracer = config.initialize_tracer()
tracing = FlaskTracing(jaeger_tracer, True, app)


app.config["MONGO_DBNAME"] = "example-mongodb"
app.config[
    "MONGO_URI"
] = "mongodb://example-mongodb-svc.default.svc.cluster.local:27017/example-mongodb"

nt_requests_by_status = metrics.summary(
    "requests_by_status",
    "Request latencies by status",
    labels={"status": lambda r: r.status_code},
)

mongo = PyMongo(app)


@app.route("/")
@nt_requests_by_status
def homepage():
    with jaeger_tracer.start_span("backend-homepage") as span:
        span.set_tag("method", "homepage")
        return "Hello World"


@app.route("/api")
@nt_requests_by_status
def my_api():
    with jaeger_tracer.start_span("backend-api") as span:
        span.set_tag("method", "my_api")
        answer = "something"
        return jsonify(repsonse=answer)


@app.route("/star", methods=["POST"])
@nt_requests_by_status
def add_star():
    with jaeger_tracer.start_span("backend-star") as span:
        span.set_tag("method", "add_star")
        star = mongo.db.stars
        name = request.json["name"]
        distance = request.json["distance"]
        star_id = star.insert({"name": name, "distance": distance})
        new_star = star.find_one({"_id": star_id})
        output = {"name": new_star["name"], "distance": new_star["distance"]}
        return jsonify({"result": output})


if __name__ == "__main__":
    app.run()
