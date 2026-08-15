FROM python:3.12-slim
LABEL "language"="python"
LABEL "framework"="streamlit"

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Hong_Kong
ENV MEMBER_DATA_DIR=/data/member

# 安裝必要套件（包括 cron）及 Node.js LTS。
# Node.js 主要預留給日後 Streamlit custom component / 前端 build 使用。
ARG NODE_MAJOR=22
RUN apt-get update \
    && apt-get install -y curl cron ca-certificates gnupg tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && node --version \
    && npm --version \
    && rm -rf /var/lib/apt/lists/*



# 複製 requirements 並安裝 Python 套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼
COPY . .

# 建立日誌及會員資料目錄
RUN mkdir -p /var/log/cron /data/member/member_bet_dbs
RUN echo "/var/log/cron/*.log {\n\
    daily\n\
    rotate 7\n\
    compress\n\
    delaycompress\n\
    missingok\n\
    notifempty\n\
}" > /etc/logrotate.d/cron-logs

# 複製並載入 crontab.txt
COPY crontab.txt /tmp/crontab.txt
RUN crontab /tmp/crontab.txt






# 預設開放 8502 (Streamlit) 及 8080 (Flask/Gunicorn)
EXPOSE 8502 8080

# 啟動 cron 和 Streamlit
# CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0

CMD service cron start && exec streamlit run streamlit_app.py --server.port=${PORT:-8502} --server.address=0.0.0.0
