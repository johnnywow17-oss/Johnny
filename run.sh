#!/bin/bash

echo "🚀 Iniciando ChatBot Pet do Toco no Render..."

# Inicia o agendador em background
python agendador.py &

# Aguarda 2 segundos
sleep 2

# Inicia o bot principal com gunicorn
# IMPORTANTE: main:app significa "arquivo main.py, objeto app"
echo "✅ Iniciando servidor web..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --access-logfile - --error-logfile - main:app
