# Dockerfile

# Используем официальный образ Python
FROM python:3.12-slim

# Рабочая директория
WORKDIR /app

# Копируем только зависимости для кеширования слоёв
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код
COPY . .

# Копируем entrypoint и даём ему права на исполнение
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# По умолчанию запускаем entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
