# 📌 API de Previsão Meteorológica e Sugestão de Rotas

## 🚀 Sobre a API
Esta API fornece previsões meteorológicas detalhadas, análise de risco para voos e sugestões de rotas aéreas baseadas em condições climáticas.  

Ela utiliza:
- 🔹 **Meteostat API** para dados históricos e previsão meteorológica.
- 🔹 **AeroAPI** para informações sobre aeroportos e rotas de voo.
- 🔹 **Machine Learning** com RandomForest para previsão de risco climático.
- 🔹 **Flask** para estruturação dos endpoints.
- 🔹 **Docker** para criar uma imagem/container

---

## 📦 Instalação e Configuração
### 🔧 Pré-requisitos
Antes de iniciar, certifique-se de ter instalado:
- Python 3.8+
- `pip` para gerenciamento de pacotes
- Dependências listadas em `requirements.txt`

### 📥 Instalação
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/SkyPredict.git

# Acesse a pasta do projeto
cd SkyPredict

# Crie um ambiente virtual (opcional, mas recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt
```

### 📥 Instalação do MongoDB
Siga as instruções para a instalação em https://www.mongodb.com/pt-br/docs/manual/installation/

### 🛠️ Configurando o docker
Rode o comando abaixo para criar um container docker:
- ```bash
    docker-compose up -d
  ```
- Caso precise alterar alguma propriedade é necessario ajustar os arquivos **dockercompose.yml** e **Dockerfile**


### 🔑 Configuração das Chaves de API
Crie um arquivo `.env` na raiz do projeto e adicione suas credenciais:
```ini
METEOSTAT_API_KEY=suachave_meteostat
METEOSTAT_API_HOST=suahost_meteostat
AEROAPI_KEY=suachave_aeroapi
MONGO_URI=api_mongodb
MONGOD_DATASET=base_de_dados
MONGO_COLLECTION=coleção
```
---

## 🛠️ Endpoints da API

### 1️⃣ Previsão Meteorológica
**Endpoint:** `GET /previsao`  
Obtém a previsão do tempo para uma coordenada geográfica.

📤 **Exemplo de Requisição:**
```bash
curl "http://localhost:5000/previsao?lat=-23.5505&lon=-46.6333&data=2024-10-15"
```

📥 **Resposta (JSON):**
```json
{
  "localizacao": { "latitude": -23.5505, "longitude": -46.6333 },
  "data": "2024-10-15",
  "previsao": {
    "tavg": 22.3,
    "tmin": 18.5,
    "tmax": 28.1,
    "prcp": 5.2,
    "wspd": 12.3,
    "pres": 1012.5
  },
  "risco": "Baixo"
}
```

### 2️⃣ Sugestão de Rotas Aéreas
**Endpoint:** `GET /sugerir_rota`  
Sugere a melhor rota entre dois aeroportos considerando o risco meteorológico.

📤 **Exemplo de Requisição:**
```bash
curl "http://localhost:5000/sugerir_rota?origem_id=GRU&destino_id=JFK&data=2024-10-15"
```

📥 **Resposta (JSON):**
```json
{
  "origem": "GRU",
  "destino": "JFK",
  "data": "2024-10-15",
  "risco_origem": "Baixo",
  "risco_destino": "Alto",
  "rotas": ["GRU → MIA → JFK", "GRU → ATL → JFK"],
  "sugestao": "Evitar voo devido a alto risco meteorológico."
}
```

### 3️⃣ Geração de Gráficos
**Endpoint:** `GET /graficos`  
Gera gráficos de previsão climática e os retorna como imagem PNG.

📤 **Exemplo de Requisição:**
```bash
curl "http://localhost:5000/graficos?lat=-23.5505&lon=-46.6333&data=2024-10-15" -o grafico.png
```
**Endpoint:** `GET /analise/graficos`
Gera gráficos de uma determinada analise

📤 **Exemplo de Requisição:**

```bash
curl "http://localhost:5000/analise/graficos?lat=-23.5505&lon=-46.6333" -o grafico.png
```

### 4️⃣ Análise do Modelo
**Endpoint:** `GET /analise`  
Retorna métricas de performance do modelo de machine learning.

📤 **Exemplo de Requisição:**
```bash
curl "http://localhost:5000/analise?lat=-23.5505&lon=-46.6333&"
```

### 5️⃣ Exportação de Dados
**Endpoint:** `GET /exportar_excel`  
Exporta os dados meteorológicos para um arquivo Excel.

📤 **Exemplo de Requisição:**
```bash
curl "http://localhost:5000/exportar_excel?lat=-23.5505&lon=-46.6333" -o dados.xlsx
```

---

## 🧠 Cache de Modelos (RandomForest + Prophet)
A API mantém um cache em memória por par de coordenadas `(lat, lon)` para reaproveitar:
- O **RandomForestClassifier** usado na previsão de risco.
- Os **modelos Prophet** por variável (`tavg`, `tmin`, `tmax`, `prcp`, `wspd`, `pres`).

### ✅ Validade e invalidação automática
O cache é invalidado automaticamente após **24 horas** (padrão).  
Você pode ajustar esse tempo com a variável de ambiente:
```ini
MODEL_CACHE_TTL_HOURS=24
```

### ♻️ Como limpar/invalidar manualmente
Há duas formas simples de limpar o cache:
1. **Reiniciar a aplicação** (limpa todo o cache em memória).
2. **Limpeza programática** (em um script ou console Python):
```python
from services.model_service import clear_model_cache

# Limpa tudo
clear_model_cache()

# Limpa apenas um par (lat, lon)
clear_model_cache(lat=-23.5505, lon=-46.6333)
```

---

## 🚀 Como Rodar a API
### 🔥 Modo de Desenvolvimento
1️⃣ Execute o seguinte comando:
```bash
python app.py
```
2️⃣ A API estará disponível em:
```bash
http://localhost:5000
```

---

## ☕ Serviço Java
Para manter a separação entre a API Python e uma futura API Java, o serviço Java deve ficar em um repositório próprio. Este repositório permanece focado no microserviço Python.

## 🛠 Tecnologias Utilizadas
- **Python 3.8+**
- **Flask** (Framework para API)
- **scikit-learn** (Machine Learning)
- **Prophet** (Modelagem preditiva)
- **Meteostat API** (Dados meteorológicos)
- **AeroAPI** (Informações de aeroportos e rotas)
- **MongoDb e MongoDb Compass** (Banco de dados e seu gerenciador)

---

## 👨‍💻 Contribuição
Sinta-se à vontade para abrir **issues** e enviar **pull requests**! 🚀

1. **Fork** este repositório  
2. Crie uma nova branch: `git checkout -b minha-feature`  
3. Faça suas alterações e commit: `git commit -m 'Adicionando nova feature'`  
4. Envie para o repositório remoto: `git push origin minha-feature`  
5. Abra um **Pull Request** 🎉  

---

## 📄 Licença
Este projeto está sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
