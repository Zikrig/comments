FROM python:3.11-slim

WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY bot.py .

# Запускаем бота
CMD ["python", "bot.py"]



