FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8000 8501

# CMD가 없으면 `docker run`으로 이미지를 단독 실행할 때 컨테이너가 즉시 종료된다.
# docker-compose.yml은 서비스별로 command를 지정해 이 기본값을 덮어쓴다
#   - api       : uvicorn api_app:app
#   - dashboard : streamlit run dashboard/streamlit_app.py
CMD ["python", "-m", "uvicorn", "api_app:app", "--host", "0.0.0.0", "--port", "8000"]
