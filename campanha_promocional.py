"""
Sistema de Campanhas Promocionais - Pet do Toco
Envia mensagens segmentadas com imagem para clientes específicos
"""

import json
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
import time
import random

# ================= CONFIG =================
WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_SEND_TEXT_URL = "https://gate.whapi.cloud/messages/text"
WHAPI_SEND_IMAGE_URL = "https://gate.whapi.cloud/messages/image"
ARQUIVO_CLIENTES = "clientes.json"

# Configurações anti-spam
MAX_ENVIOS_POR_EXECUCAO = 100
INTERVALO_MIN_SEGUNDOS = 4
INTERVALO_MAX_SEGUNDOS = 7

# ================= FUNÇÕES =================
def carregar_clientes():
    """Carrega base de clientes"""
    if os.path.exists(ARQUIVO_CLIENTES):
        try:
            with open(ARQUIVO_CLIENTES, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def salvar_log_campanha(campanha_info, resultados):
    """Salva log da campanha executada"""
    timestamp = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo = f"campanha_log_{timestamp}.txt"
    
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("RELATÓRIO DE CAMPANHA PROMOCIONAL\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Data/Hora: {datetime.now(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"Segmentação: {campanha_info['segmentacao']}\n")
        f.write(f"Tem imagem: {'Sim' if campanha_info['tem_imagem'] else 'Não'}\n\n")
        
        f.write("MENSAGEM ENVIADA:\n")
        f.write("-" * 60 + "\n")
        f.write(campanha_info['mensagem'] + "\n")
        f.write("-" * 60 + "\n\n")
        
        f.write("RESULTADOS:\n")
        f.write(f"✓ Enviados com sucesso: {resultados['sucesso']}\n")
        f.write(f"✗ Falhas: {resultados['falhas']}\n")
        f.write(f"📊 Total processado: {resultados['total']}\n\n")
        
        f.write("DETALHES DOS ENVIOS:\n")
        f.write("-" * 60 + "\n")
        for detalhe in resultados['detalhes']:
            f.write(f"{detalhe}\n")
        f.write("-" * 60 + "\n")
    
    print(f"\n📄 Relatório salvo em: {nome_arquivo}")
    return nome_arquivo

def filtrar_clientes_por_segmentacao(clientes, segmentacao):
    """Filtra clientes baseado na segmentação escolhida"""
    clientes_filtrados = []
    
    for cliente in clientes:
        # Pula quem fez opt-out
        if cliente.get("opt_out"):
            continue
            
        pets = cliente.get("pets", [])
        if not pets:
            continue
        
        # Verifica segmentação
        if segmentacao == "todos":
            clientes_filtrados.append(cliente)
        
        elif segmentacao == "caes":
            tem_cao = any(pet.get("especie", "").lower() == "cachorro" for pet in pets)
            if tem_cao:
                clientes_filtrados.append(cliente)
        
        elif segmentacao == "gatos":
            tem_gato = any(pet.get("especie", "").lower() == "gato" for pet in pets)
            if tem_gato:
                clientes_filtrados.append(cliente)
        
        elif segmentacao.startswith("porte_"):
            porte_desejado = segmentacao.replace("porte_", "")
            tem_porte = any(pet.get("porte", "").lower() == porte_desejado for pet in pets)
            if tem_porte:
                clientes_filtrados.append(cliente)
        
        elif segmentacao.startswith("raca_"):
            raca_desejada = segmentacao.replace("raca_", "").lower()
            tem_raca = any(raca_desejada in pet.get("raca", "").lower() for pet in pets)
            if tem_raca:
                clientes_filtrados.append(cliente)
    
    return clientes_filtrados

def enviar_mensagem_texto(numero, texto):
    """Envia mensagem de texto via Whapi"""
    try:
        headers = {"Authorization": f"Bearer {WHAPI_TOKEN}"}
        payload = {
            "to": f"{numero}@s.whatsapp.net",
            "body": texto
        }
        response = requests.post(WHAPI_SEND_TEXT_URL, json=payload, headers=headers, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar texto: {e}")
        return False

def enviar_mensagem_imagem(numero, url_imagem, caption):
    """Envia imagem com legenda via Whapi"""
    try:
        headers = {"Authorization": f"Bearer {WHAPI_TOKEN}"}
        payload = {
            "to": f"{numero}@s.whatsapp.net",
            "media": url_imagem,
            "caption": caption
        }
        response = requests.post(WHAPI_SEND_IMAGE_URL, json=payload, headers=headers, timeout=15)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar imagem: {e}")
        return False

def executar_campanha(segmentacao, mensagem, url_imagem=None):
    """
    Executa campanha promocional
    
    Parâmetros:
        segmentacao (str): "todos", "caes", "gatos", "porte_pequeno", "porte_medio", "porte_grande", "raca_poodle"
        mensagem (str): Texto da mensagem
        url_imagem (str): URL pública da imagem (opcional)
    """
    
    print("\n" + "=" * 60)
    print("🚀 INICIANDO CAMPANHA PROMOCIONAL")
    print("=" * 60)
    
    # Info da campanha
    campanha_info = {
        "segmentacao": segmentacao,
        "mensagem": mensagem,
        "tem_imagem": url_imagem is not None
    }
    
    # Carrega clientes
    clientes = carregar_clientes()
    print(f"📊 Total de clientes na base: {len(clientes)}")
    
    # Filtra por segmentação
    clientes_filtrados = filtrar_clientes_por_segmentacao(clientes, segmentacao)
    print(f"🎯 Clientes na segmentação '{segmentacao}': {len(clientes_filtrados)}")
    
    if not clientes_filtrados:
        print("⚠️  Nenhum cliente encontrado para esta segmentação!")
        return
    
    # Limita envios
    clientes_filtrados = clientes_filtrados[:MAX_ENVIOS_POR_EXECUCAO]
    print(f"📤 Serão enviadas {len(clientes_filtrados)} mensagens")
    print()
    
    # Confirmação
    print("⏰ Aguarde... Iniciando envios em 3 segundos...")
    time.sleep(3)
    
    # Envia mensagens
    resultados = {
        "sucesso": 0,
        "falhas": 0,
        "total": len(clientes_filtrados),
        "detalhes": []
    }
    
    for i, cliente in enumerate(clientes_filtrados, 1):
        nome = cliente["nome"]
        telefone = cliente["telefone"]
        
        print(f"[{i}/{len(clientes_filtrados)}] Enviando para {nome} ({telefone})...")
        
        # Envia (com ou sem imagem)
        if url_imagem:
            sucesso = enviar_mensagem_imagem(telefone, url_imagem, mensagem)
        else:
            sucesso = enviar_mensagem_texto(telefone, mensagem)
        
        if sucesso:
            resultados["sucesso"] += 1
            resultados["detalhes"].append(f"✓ {nome} ({telefone})")
            print(f"   ✓ Enviado com sucesso!")
        else:
            resultados["falhas"] += 1
            resultados["detalhes"].append(f"✗ {nome} ({telefone})")
            print(f"   ✗ Falha no envio")
        
        # Intervalo anti-spam
        if i < len(clientes_filtrados):
            intervalo = random.uniform(INTERVALO_MIN_SEGUNDOS, INTERVALO_MAX_SEGUNDOS)
            print(f"   ⏳ Aguardando {intervalo:.1f}s...\n")
            time.sleep(intervalo)
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 CAMPANHA FINALIZADA")
    print("=" * 60)
    print(f"✓ Enviados com sucesso: {resultados['sucesso']}")
    print(f"✗ Falhas: {resultados['falhas']}")
    print(f"📊 Total processado: {resultados['total']}")
    print(f"📈 Taxa de sucesso: {(resultados['sucesso']/resultados['total']*100):.1f}%")
    
    # Salva log
    arquivo_log = salvar_log_campanha(campanha_info, resultados)
    print(f"\n💾 Log completo salvo: {arquivo_log}")
    print("=" * 60 + "\n")

# ================= EXEMPLOS DE USO =================
if __name__ == "__main__":
    """
    EXEMPLOS DE COMO USAR:
    
    1) CAMPANHA PARA TODOS:
    executar_campanha(
        segmentacao="todos",
        mensagem="🎉 PROMOÇÃO ESPECIAL! Banho + Tosa por apenas R$ 80 nesta semana!",
        url_imagem="https://seusite.com/banner-promocao.jpg"
    )
    
    2) CAMPANHA APENAS PARA QUEM TEM CÃES:
    executar_campanha(
        segmentacao="caes",
        mensagem="🐶 Antipulgas para cães com 30% OFF! Válido até sexta-feira!",
        url_imagem="https://seusite.com/antipulgas-cao.jpg"
    )
    
    3) CAMPANHA APENAS PARA QUEM TEM GATOS:
    executar_campanha(
        segmentacao="gatos",
        mensagem="🐱 Ração premium para gatos com desconto especial!",
        url_imagem="https://seusite.com/racao-gato.jpg"
    )
    
    4) CAMPANHA POR PORTE:
    executar_campanha(
        segmentacao="porte_pequeno",
        mensagem="🐕 Produtos especiais para pets pequenos!",
        url_imagem="https://seusite.com/banner-pequeno.jpg"
    )
    
    5) CAMPANHA SEM IMAGEM:
    executar_campanha(
        segmentacao="todos",
        mensagem="Oi! Estamos com novidades na loja. Passa aqui! 😊"
    )
    """
    
    print("=" * 60)
    print("SISTEMA DE CAMPANHAS PROMOCIONAIS - PET DO TOCO")
    print("=" * 60)
    print()
    print("📋 SEGMENTAÇÕES DISPONÍVEIS:")
    print("   • todos          - Todos os clientes")
    print("   • caes           - Apenas quem tem cachorro")
    print("   • gatos          - Apenas quem tem gato")
    print("   • porte_pequeno  - Apenas pets pequenos")
    print("   • porte_medio    - Apenas pets médios")
    print("   • porte_grande   - Apenas pets grandes")
    print("   • raca_[nome]    - Ex: raca_poodle, raca_labrador")
    print()
    print("💡 COMO USAR:")
    print("   1) Edite este arquivo no final")
    print("   2) Descomente um dos exemplos")
    print("   3) Coloque sua URL de imagem e mensagem")
    print("   4) Execute: python campanha_promocional.py")
    print()
    print("⚠️  IMPORTANTE:")
    print("   • A imagem precisa estar hospedada (URL pública)")
    print("   • Máximo de 100 envios por execução")
    print("   • Intervalo de 4-7s entre mensagens (anti-spam)")
    print()
    print("=" * 60)
    print()
    print("❌ Nenhuma campanha configurada.")
    print("📝 Edite este arquivo e descomente um exemplo para começar!")
    print()
