#!/bin/bash

echo "🚀 Iniciando ChatBot Pet do Toco no Render..."

# Inicia o agendador em background
python agendador.py &

# Aguarda 2 segundos
sleep 2

# Inicia o bot principal com gunicorn
echo "✅ Iniciando servidor web..."
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 main:app
