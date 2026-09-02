FROM python:3.10-slim

WORKDIR /app

# Dependencies install karo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code copy karo
COPY app.py .

# Flask port expose karo
EXPOSE 10000

# Bot + Flask dono ek saath chalenge
CMD ["python", "app.py"]
