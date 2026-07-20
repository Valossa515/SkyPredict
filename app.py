import logging
import os

import certifi

# Backend não-interativo do matplotlib: obrigatório em servidor web
# (evita vazamentos/erros de Tcl/Tk em ambiente multi-thread).
import matplotlib
matplotlib.use("Agg")

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from services.validators import ValidationError

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())


def _configurar_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _registrar_error_handlers(app: Flask):
    logger = logging.getLogger(__name__)

    @app.errorhandler(ValidationError)
    def _handle_validation(err):
        return jsonify({"erro": str(err)}), 400

    @app.errorhandler(ValueError)
    def _handle_value_error(err):
        # Erros de domínio esperados (ex.: dados ausentes na API externa).
        logger.info("Requisição rejeitada: %s", err)
        return jsonify({"erro": str(err)}), 400

    @app.errorhandler(HTTPException)
    def _handle_http(err):
        return jsonify({"erro": err.description}), err.code

    @app.errorhandler(Exception)
    def _handle_unexpected(err):
        # Loga o stacktrace completo, mas não vaza detalhes internos ao cliente.
        logger.exception("Erro inesperado ao processar a requisição.")
        return jsonify({"erro": "Erro interno do servidor."}), 500


def create_app() -> Flask:
    _configurar_logging()

    app = Flask(__name__)

    # Registrar os Blueprints das rotas
    from routes.previsao import previsao_bp
    from routes.sugerir_rota import sugerir_rota_bp
    from routes.graficos import graficos_bp
    from routes.analise import analise_bp
    from routes.exportar import exportar_bp
    from routes.mapa import mapa_bp

    app.register_blueprint(previsao_bp)
    app.register_blueprint(sugerir_rota_bp)
    app.register_blueprint(graficos_bp)
    app.register_blueprint(analise_bp)
    app.register_blueprint(exportar_bp)
    app.register_blueprint(mapa_bp)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    _registrar_error_handlers(app)

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
