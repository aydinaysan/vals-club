FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=5000
ENV SECRET_KEY=change-this-in-production
EXPOSE 5000
CMD ["python","app.py"]
