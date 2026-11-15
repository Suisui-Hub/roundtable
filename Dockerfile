FROM python:3.12-slim

WORKDIR /app

# 先装依赖，改代码时不必重装
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 平台会用 $PORT 注入端口，run.py 已支持
CMD ["python", "run.py"]
