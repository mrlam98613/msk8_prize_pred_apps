FROM python:3.15-slim
LABEL "language"="python"
LABEL "framework"="streamlit"

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Hong_Kong
ENV MEMBER_DATA_DIR=/data/member

# 複製 requirements 並安裝 Python 套件。
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# 複製所有程式碼。
COPY . .

# 建立會員資料目錄；正式資料應由 Dokploy volume 掛載。
RUN mkdir -p /data/member/member_bet_dbs

# Dokploy 對外提供 Streamlit。
EXPOSE 8502

CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
