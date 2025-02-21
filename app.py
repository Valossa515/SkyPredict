from flask import Flask
from routes.previsao import previsao_bp
from routes.sugerir_rota import sugerir_rota_bp
from routes.graficos import graficos_bp
from routes.analise import analise_bp
from routes.exportar import exportar_bp

app = Flask(__name__)

# Registrar os Blueprints das rotas
app.register_blueprint(previsao_bp)
app.register_blueprint(sugerir_rota_bp)
app.register_blueprint(graficos_bp)
app.register_blueprint(analise_bp)
app.register_blueprint(exportar_bp)

if __name__ == '__main__':
    app.run(debug=True)