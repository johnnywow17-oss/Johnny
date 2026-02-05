"""
Agendador - Executa lembrete automático todo dia às 9h
"""

import schedule
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import subprocess

def executar_lembrete():
    """Executa o script de lembrete"""
    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{agora}] Executando lembrete automático...")
    
    try:
        # Executa o script de lembrete
        subprocess.run(["python", "lembrete_automatico.py"], check=True)
        print(f"[{agora}] Lembrete executado com sucesso!")
    except Exception as e:
        print(f"[{agora}] Erro ao executar lembrete: {e}")

# Agenda para executar todo dia às 9h
schedule.every().day.at("09:00").do(executar_lembrete)

print("🤖 Agendador iniciado!")
print("📅 Lembrete automático será executado todo dia às 9h")
print("⏰ Aguardando próxima execução...\n")

# Loop infinito
while True:
    schedule.run_pending()
    time.sleep(60)  # Verifica a cada 1 minuto
