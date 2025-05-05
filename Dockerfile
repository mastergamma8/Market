# Берём официальный образ Python
FROM python:3.11-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники приложения
COPY . .

# Создаём папки для персистентного хранения
RUN mkdir -p data/static/avatars \
 && mkdir -p data/static/image

# Объявляем том для каталога data
VOLUME ["/app/data"]

# Открываем порт для FastAPI
EXPOSE 8000

# По умолчанию запускаем ваш скрипт (main.py)
CMD ["python", "main.py"]
