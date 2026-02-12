"""
Sistema de Lembrete Automático - Pet do Toco
Envia mensagens suaves a cada 28 dias para clientes inativos
"""

import json
import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import random

# ================= CONFIG =================
WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_SEND_URL = "https://gate.whapi.cloud/messages/text"
ARQUIVO_CLIENTES = "clientes.json"

# Configurações
DIAS_SEM_INTERACAO = 28
MAX_ENVIOS_POR_DIA = 50
INTERVALO_MIN_SEGUNDOS = 3
INTERVALO_MAX_SEGUNDOS = 5

# ================= FUNÇÕES =================
def carregar_clientes():
    if os.path.exists(ARQUIVO_CLIENTES):
        try:
            with open(ARQUIVO_CLIENTES, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_clientes(clientes):
    with open(ARQUIVO_CLIENTES, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=2)

def dentro_horario_atendimento():
    """Verifica se está dentro do horário comercial"""
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    dia = agora.weekday()
    hora = agora.hour
    
    if dia <= 4:  # Seg-Sex
        return 8 <= hora < 19
    if dia == 5:  # Sábado
        return 8 <= hora < 18
    return False

def precisa_lembrete(cliente):
    """Verifica se cliente precisa receber lembrete"""
    # Verifica opt-out
    if cliente.get("opt_out"):
        return False
    
    # Verifica última interação
    try:
        ultima = datetime.strptime(cliente["ultima_interacao"], "%Y-%m-%d")
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        dias_sem_interacao = (agora - ultima).days
        
        # Precisa ter passado exatamente 28 dias (ou mais, se perdeu o dia)
        return dias_sem_interacao >= DIAS_SEM_INTERACAO
    except:
        return False

def gerar_mensagem_lembrete(cliente):
    """Gera mensagem personalizada e amigável"""
    primeiro_nome = cliente["nome"].split()[0]
    pets = cliente.get("pets", [])
    
    if pets:
        pet = pets[0]
        nome_pet = pet["nome"]
        
        mensagens = [
            (
                f"Olá, {primeiro_nome}! Tudo bem? 😊\n\n"
                f"Como está o(a) {nome_pet}? Esperamos que estejam bem!\n\n"
                f"Se precisar de algo, estamos aqui no Pet do Toco! 🐾\n\n"
                "Abraço da equipe! 💚"
            ),
            (
                f"Oi, {primeiro_nome}! 🐾\n\n"
                f"Sentimos saudades suas e do(a) {nome_pet}!\n\n"
                f"Qualquer coisa que precise, pode contar com a gente aqui no Pet do Toco!\n\n"
                "Um abraço! 😊"
            ),
            (
                f"{primeiro_nome}, tudo bem? 😊\n\n"
                f"Passou um tempinho! Como está o(a) {nome_pet}?\n\n"
                f"Estamos aqui para o que precisar! 🐾\n\n"
                "Equipe Pet do Toco 💚"
            )
        ]
    else:
        mensagens = [
            (
                f"Olá, {primeiro_nome}! Tudo bem? 😊\n\n"
                f"Sentimos sua falta aqui no Pet do Toco!\n\n"
                f"Se precisar de algo para seu pet, estamos aqui! 🐾\n\n"
                "Abraço da equipe! 💚"
            )
        ]
    
    # Escolhe uma mensagem aleatória para variar
    return random.choice(mensagens)

def enviar_mensagem(numero, texto):
    """Envia mensagem via Whapi"""
    try:
        headers = {"Authorization": f"Bearer {WHAPI_TOKEN}"}
        payload = {"to": f"{numero}@s.whatsapp.net", "body": texto}
        response = requests.post(WHAPI_SEND_URL, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def registrar_log(mensagem):
    """Registra log de atividades"""
    timestamp = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")
    with open("lembrete_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {mensagem}\n")
    print(f"[{timestamp}] {mensagem}")

# ================= MAIN =================
def executar_lembretes():
    """Função principal que envia os lembretes"""
    
    # Verifica horário
    if not dentro_horario_atendimento():
        registrar_log("Fora do horário de atendimento. Abortando.")
        return
    
    registrar_log("=== INICIANDO ENVIO DE LEMBRETES ===")
    
    # Carrega clientes
    clientes = carregar_clientes()
    registrar_log(f"Total de clientes cadastrados: {len(clientes)}")
    
    # Filtra quem precisa receber lembrete
    clientes_para_lembrete = [c for c in clientes if precisa_lembrete(c)]
    registrar_log(f"Clientes que precisam de lembrete: {len(clientes_para_lembrete)}")
    
    if not clientes_para_lembrete:
        registrar_log("Nenhum cliente precisa de lembrete hoje.")
        return
    
    # Limita envios por dia
    clientes_para_lembrete = clientes_para_lembrete[:MAX_ENVIOS_POR_DIA]
    
    # Envia lembretes
    sucesso = 0
    falhas = 0
    
    for cliente in clientes_para_lembrete:
        nome = cliente["nome"]
        telefone = cliente["telefone"]
        
        # Gera mensagem
        mensagem = gerar_mensagem_lembrete(cliente)
        
        # Envia
        registrar_log(f"Enviando para {nome} ({telefone})...")
        if enviar_mensagem(telefone, mensagem):
            sucesso += 1
            
            # Atualiza última interação para não enviar de novo
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            cliente["ultima_interacao"] = agora.strftime("%Y-%m-%d")
            cliente["ultima_interacao_completa"] = agora.strftime("%Y-%m-%d %H:%M:%S")
            
            registrar_log(f"✓ Enviado com sucesso para {nome}")
        else:
            falhas += 1
            registrar_log(f"✗ Falha ao enviar para {nome}")
        
        # Intervalo aleatório entre mensagens (anti-spam)
        intervalo = random.uniform(INTERVALO_MIN_SEGUNDOS, INTERVALO_MAX_SEGUNDOS)
        time.sleep(intervalo)
    
    # Salva atualizações
    salvar_clientes(clientes)
    
    # Relatório final
    registrar_log("=== RELATÓRIO FINAL ===")
    registrar_log(f"Enviados com sucesso: {sucesso}")
    registrar_log(f"Falhas: {falhas}")
    registrar_log(f"Total processado: {sucesso + falhas}")
    registrar_log("======================")

if __name__ == "__main__":
    executar_lembretes()
