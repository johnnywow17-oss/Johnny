import json
import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request
import time
from zoneinfo import ZoneInfo

app = Flask(__name__)

# ================= CONFIG =================
WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_SEND_URL = "https://gate.whapi.cloud/messages/text"
ARQUIVO_CLIENTES = "clientes.json"
NOME_NEGOCIO = "Pet do Toco"

# Configurações de tempo
TIMEOUT_HUMANO_HORAS = 2
TEMPO_INTERACAO_RECENTE_HORAS = 6
DIAS_PARA_MARKETING = 30  # Seguro para WhatsApp

# ================= MEMÓRIA =================
clientes = []
estados_conversa = {}

# ================= CLIENTES =================
def carregar_clientes():
    global clientes
    if os.path.exists(ARQUIVO_CLIENTES):
        try:
            with open(ARQUIVO_CLIENTES, "r", encoding="utf-8") as f:
                clientes = json.load(f)
            print(f"[DEBUG] Arquivo carregado: {len(clientes)} clientes")
        except Exception as e:
            print(f"[ERRO] Falha ao carregar clientes: {e}")
            clientes = []
    else:
        print(f"[DEBUG] Arquivo {ARQUIVO_CLIENTES} não existe ainda")
        clientes = []

def salvar_clientes():
    with open(ARQUIVO_CLIENTES, "w", encoding="utf-8") as f:
        json.dump(clientes, f, ensure_ascii=False, indent=2)

carregar_clientes()

def normalizar_telefone(telefone):
    """Normaliza telefone: remove caracteres especiais e adiciona 55 se necessário"""
    # Remove caracteres especiais
    tel_limpo = telefone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    
    # Se não começa com 55 e tem 10 ou 11 dígitos (telefone BR sem código do país)
    if not tel_limpo.startswith("55") and len(tel_limpo) in [10, 11]:
        tel_limpo = "55" + tel_limpo
    
    return tel_limpo

def buscar_cliente_por_telefone(telefone):
    """Busca cliente por telefone (normalizado com 55)"""
    # Recarrega clientes do arquivo para garantir dados atualizados
    carregar_clientes()
    
    print(f"[DEBUG] Buscando telefone: {telefone}")
    print(f"[DEBUG] Total de clientes no arquivo: {len(clientes)}")
    
    # Normaliza o telefone buscado
    telefone_normalizado = normalizar_telefone(telefone)
    print(f"[DEBUG] Telefone normalizado: {telefone_normalizado}")
    
    for i, c in enumerate(clientes):
        # Normaliza o telefone do cliente
        tel_cliente = normalizar_telefone(c.get("telefone", ""))
        print(f"[DEBUG] Comparando com cliente {i+1}: {tel_cliente} == {telefone_normalizado}?")
        
        if tel_cliente == telefone_normalizado:
            print(f"[DEBUG] ✓ Cliente ENCONTRADO: {c.get('nome')} - {telefone}")
            return c
    
    print(f"[DEBUG] ✗ Cliente NÃO encontrado: {telefone}")
    return None

# ================= HORÁRIOS =================
def dentro_horario_atendimento():
    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    dia = agora.weekday()
    hora = agora.hour
    if dia <= 4:  # Seg-Sex
        return 8 <= hora < 19
    if dia == 5:  # Sábado
        return 8 <= hora < 18
    return False

def is_urgente(mensagem):
    palavras = ["urgente", "emergência", "socorro", "dor", "sangue"]
    return any(p in mensagem.lower() for p in palavras)

# ================= CEP =================
def validar_cep(cep):
    cep = cep.replace("-", "").replace(".", "").strip()
    return cep.isdigit() and len(cep) == 8

def consultar_cep(cep):
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=8)
        if r.status_code != 200:
            return None
        dados = r.json()
        if "erro" in dados:
            return None
        return dados
    except:
        return None

# ================= TEMPO =================
def is_interacao_recente(cliente):
    """Verifica se última interação foi há menos de 6 horas"""
    try:
        ultima_str = cliente.get("ultima_interacao_completa")
        if not ultima_str:
            return False
        ultima = datetime.strptime(ultima_str, "%Y-%m-%d %H:%M:%S")
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        return agora - ultima < timedelta(hours=TEMPO_INTERACAO_RECENTE_HORAS)
    except:
        return False

# ================= ATENDIMENTO =================
def transferir_para_humano(telefone, cliente):
    """Transfere para atendente e salva timestamp"""
    estados_conversa[telefone] = "HUMANO"
    if cliente:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        cliente["timestamp_humano"] = agora.strftime("%Y-%m-%d %H:%M:%S")
        salvar_clientes()

# ================= MARKETING =================
def precisa_enviar_marketing(cliente):
    """Verifica se deve enviar marketing (30 dias sem interação)"""
    if not cliente or cliente.get("opt_out"):
        return False
    try:
        ultima = datetime.strptime(cliente["ultima_interacao"], "%Y-%m-%d")
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
        return agora - ultima >= timedelta(days=DIAS_PARA_MARKETING)
    except:
        return False

def mensagem_marketing_personalizada(cliente):
    """Cria mensagem de marketing baseada nos pets do cliente"""
    primeiro_nome = cliente["nome"].split()[0]
    pets = cliente.get("pets", [])
    
    if not pets:
        return (
            f"Olá, {primeiro_nome}! 🐾\n\n"
            f"Sentimos sua falta aqui no {NOME_NEGOCIO}!\n\n"
            "Temos novidades incríveis:\n"
            "🐶 Rações premium com desconto\n"
            "🐱 Novos petiscos naturais\n"
            "🛁 Promoção de banho e tosa\n\n"
            "Quer saber mais? Responda *OI* 😊"
        )
    
    # Pega o primeiro pet
    pet = pets[0]
    nome_pet = pet.get("nome", "seu pet")
    especie = pet.get("especie", "").lower()
    
    if especie == "cao":
        return (
            f"Olá, {primeiro_nome}! 🐾\n\n"
            f"Como está o {nome_pet}? Sentimos saudades de vocês!\n\n"
            f"💡 *Lembrete importante:*\n"
            f"Já passou um tempo... A ração do {nome_pet} pode estar acabando! 🍖\n\n"
            f"Também temos:\n"
            f"• Vermífugos (recomendado a cada 3 meses)\n"
            f"• Tapetes higiênicos\n"
            f"• Petiscos naturais\n\n"
            "Precisa de algo? Responda *OI* que te ajudo! 😊"
        )
    elif especie == "gato":
        return (
            f"Olá, {primeiro_nome}! 🐾\n\n"
            f"Como está o {nome_pet}? Sentimos saudades de vocês!\n\n"
            f"💡 *Lembrete importante:*\n"
            f"A areia e a ração do {nome_pet} podem estar no fim! 🐱\n\n"
            f"Também temos:\n"
            f"• Vermífugos (recomendado a cada 3 meses)\n"
            f"• Petiscos premium\n"
            f"• Arranhadores e brinquedos\n\n"
            "Precisa de algo? Responda *OI* que te ajudo! 😊"
        )
    else:
        return (
            f"Olá, {primeiro_nome}! 🐾\n\n"
            f"Como está o {nome_pet}? Sentimos saudades!\n\n"
            "Temos muitas novidades e promoções esperando por você! 💚\n\n"
            "Responda *OI* para ver nossas ofertas! 😊"
        )

# ================= ENVIO =================
def enviar_mensagem(numero, texto):
    headers = {"Authorization": f"Bearer {WHAPI_TOKEN}"}
    payload = {"to": numero, "body": texto}
    requests.post(WHAPI_SEND_URL, json=payload, headers=headers)
    time.sleep(0.3)

# ================= PROCESSAR ESTADOS =================
def processar_estado(telefone, mensagem, cliente, nome_whats="Cliente"):
    estado_info = estados_conversa.get(telefone)
    if not estado_info:
        return None
    
    mensagem = mensagem.strip()

    # ========================================
    # ESTADOS DO CADASTRO
    # ========================================
    if isinstance(estado_info, dict):
        estado = estado_info["estado"]
        dados = estado_info["dados"]

        # === Nome ===
        if estado == "CADASTRO_NOME":
            if len(mensagem.split()) < 2:
                return "Informe *nome e sobrenome*, por favor."
            dados["nome"] = mensagem.title()
            estado_info["estado"] = "CADASTRO_CEP"
            return "Agora informe seu *CEP* (8 números)."

        # === CEP ===
        elif estado == "CADASTRO_CEP":
            if not validar_cep(mensagem):
                return "CEP inválido. Use apenas números."
            dados_cep = consultar_cep(mensagem)
            if not dados_cep:
                return "Não encontrei esse CEP 😕"
            dados["cep"] = mensagem
            dados["endereco"] = {
                "rua": dados_cep.get("logradouro"),
                "bairro": dados_cep.get("bairro"),
                "cidade": dados_cep.get("localidade"),
                "uf": dados_cep.get("uf"),
            }
            estado_info["estado"] = "CONFIRMAR_ENDERECO"
            e = dados["endereco"]
            return (
                f"{e['rua']}\n{e['bairro']} - {e['cidade']}/{e['uf']}\n\n"
                "Está correto?\n1️⃣ Sim\n2️⃣ Não"
            )

        # === Confirma endereço ===
        elif estado == "CONFIRMAR_ENDERECO":
            if mensagem == "1":
                estado_info["estado"] = "CADASTRO_NUMERO"
                return "Informe o *número* do endereço."
            elif mensagem == "2":
                estado_info["estado"] = "CADASTRO_CEP"
                return "Ok 😊 Envie o CEP novamente."
            else:
                return "Digite:\n1️⃣ Sim\n2️⃣ Não"

        # === Número ===
        elif estado == "CADASTRO_NUMERO":
            dados["endereco"]["numero"] = mensagem
            estado_info["estado"] = "CADASTRO_COMPLEMENTO"
            return "Informe o *complemento* (ou digite 'nenhum')."

        # === Complemento ===
        elif estado == "CADASTRO_COMPLEMENTO":
            if mensagem.lower() in ["nenhum", "não", "nao"]:
                dados["endereco"]["complemento"] = ""
            else:
                dados["endereco"]["complemento"] = mensagem
            estado_info["estado"] = "CONFIRMAR_CADASTRO"
            e = dados["endereco"]
            comp = f" - {e['complemento']}" if e['complemento'] else ""
            return (
                f"*Confirme seus dados:*\n\n"
                f"Nome: {dados['nome']}\n"
                f"Endereço: {e['rua']}, {e['numero']}{comp}\n"
                f"Bairro: {e['bairro']}\n"
                f"Cidade: {e['cidade']}/{e['uf']}\n\n"
                "1️⃣ Confirmar\n2️⃣ Corrigir"
            )

        # === Confirma cadastro ===
        elif estado == "CONFIRMAR_CADASTRO":
            if mensagem == "1":
                # Agora vai para cadastro de PET (obrigatório)
                estado_info["estado"] = "PET_NOME"
                return (
                    "Perfeito! Agora vamos cadastrar seu pet 🐾\n\n"
                    "Qual o *nome* do seu pet?"
                )
            elif mensagem == "2":
                estado_info["estado"] = "CADASTRO_NOME"
                return "Ok 😊 Vamos recomeçar. Informe seu *nome completo*."
            else:
                return "Digite:\n1️⃣ Confirmar\n2️⃣ Corrigir"

        # ========================================
        # CADASTRO DE PET (obrigatório no cadastro)
        # ========================================
        elif estado == "PET_NOME":
            dados["pet_temp"] = {"nome": mensagem.title()}
            estado_info["estado"] = "PET_ESPECIE"
            return "Qual a espécie?\n\n1️⃣ Cachorro\n2️⃣ Gato"

        elif estado == "PET_ESPECIE":
            if mensagem == "1":
                dados["pet_temp"]["especie"] = "cao"
            elif mensagem == "2":
                dados["pet_temp"]["especie"] = "gato"
            else:
                return "Digite:\n1️⃣ Cachorro\n2️⃣ Gato"
            estado_info["estado"] = "PET_GENERO"
            return f"O(a) {dados['pet_temp']['nome']} é:\n\n1️⃣ Macho\n2️⃣ Fêmea"

        elif estado == "PET_GENERO":
            if mensagem == "1":
                dados["pet_temp"]["genero"] = "macho"
            elif mensagem == "2":
                dados["pet_temp"]["genero"] = "femea"
            else:
                return "Digite:\n1️⃣ Macho\n2️⃣ Fêmea"
            estado_info["estado"] = "PET_IDADE"
            
            # Define artigo baseado no gênero
            artigo = "o" if dados["pet_temp"]["genero"] == "macho" else "a"
            return f"Qual a idade d{artigo} {dados['pet_temp']['nome']}? (em anos)"

        elif estado == "PET_IDADE":
            try:
                idade = int(mensagem)
                dados["pet_temp"]["idade"] = idade
            except:
                return "Digite apenas o número da idade (ex: 3)"
            estado_info["estado"] = "PET_CASTRADO"
            
            # Define artigo baseado no gênero
            artigo = "o" if dados["pet_temp"].get("genero") == "macho" else "a"
            castrado_txt = "castrado" if dados["pet_temp"].get("genero") == "macho" else "castrada"
            return f"{artigo.capitalize()} {dados['pet_temp']['nome']} é {castrado_txt}?\n\n1️⃣ Sim\n2️⃣ Não"

        elif estado == "PET_CASTRADO":
            if mensagem == "1":
                dados["pet_temp"]["castrado"] = True
            elif mensagem == "2":
                dados["pet_temp"]["castrado"] = False
            else:
                return "Digite:\n1️⃣ Sim\n2️⃣ Não"
            estado_info["estado"] = "PET_ALERGICO"
            
            # Define artigo baseado no gênero
            artigo = "o" if dados["pet_temp"].get("genero") == "macho" else "a"
            return f"{artigo.capitalize()} {dados['pet_temp']['nome']} tem alguma *alergia*?\n(Digite o nome da alergia ou 'nenhuma')"

        elif estado == "PET_ALERGICO":
            if mensagem.lower() in ["nenhuma", "não", "nao", "nenhum"]:
                dados["pet_temp"]["alergico"] = ""
            else:
                dados["pet_temp"]["alergico"] = mensagem
            
            # ===== VALIDAÇÃO CRÍTICA: TELEFONE JÁ EXISTE? =====
            print(f"[DEBUG] Finalizando cadastro para: {telefone}")
            print(f"[DEBUG] Total de clientes antes: {len(clientes)}")
            
            cliente_existente = buscar_cliente_por_telefone(telefone)
            if cliente_existente:
                # Cliente já existe! Não cadastra de novo
                print(f"[AVISO] Tentativa de cadastro duplicado: {telefone}")
                del estados_conversa[telefone]
                primeiro_nome = cliente_existente["nome"].split()[0]
                return (
                    f"Ops, {primeiro_nome}! Você já tem cadastro conosco! 😊\n\n"
                    "Digite *MENU* para ver as opções."
                )
            
            # Finaliza cadastro
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            
            # Normaliza telefone antes de salvar
            telefone_normalizado = normalizar_telefone(telefone)
            
            dados.update({
                "telefone": telefone_normalizado,  # Salva com 55
                "pets": [dados["pet_temp"]],
                "opt_out": False,
                "ultima_interacao": agora.strftime("%Y-%m-%d"),
                "ultima_interacao_completa": agora.strftime("%Y-%m-%d %H:%M:%S")
            })
            dados.pop("pet_temp")
            
            # Adiciona à lista GLOBAL de clientes
            clientes.append(dados)
            print(f"[DEBUG] Cliente adicionado: {dados['nome']} ({telefone})")
            print(f"[DEBUG] Total de clientes depois: {len(clientes)}")
            
            # Salva no arquivo JSON
            salvar_clientes()
            print(f"[DEBUG] Arquivo salvo com sucesso!")
            
            estados_conversa[telefone] = "MENU_PRINCIPAL"
            
            primeiro_nome = dados["nome"].split()[0]
            nome_pet = dados["pets"][0]["nome"]
            genero_pet = dados["pets"][0].get("genero", "macho")
            registrado_txt = "registrado" if genero_pet == "macho" else "registrada"
            
            return (
                f"Cadastro concluído, {primeiro_nome}! 🐾\n"
                f"{nome_pet} está {registrado_txt} com sucesso!\n\n"
                "Como posso ajudar?\n\n"
                "1️⃣ Fazer um pedido\n"
                "2️⃣ Agendar banho e tosa\n"
                "3️⃣ Falar com atendente\n"
                "0️⃣ Sair"
            )

    # ========================================
    # MENUS
    # ========================================
    
    # === Menu inicial (novo cliente) ===
    elif estado_info == "MENU_INICIAL":
        if mensagem == "1":
            # Verifica se já tem cadastro (segurança extra)
            if cliente:
                primeiro_nome = cliente["nome"].split()[0]
                return (
                    f"{primeiro_nome}, você já tem cadastro! 😊\n\n"
                    "Digite *MENU* para ver as opções."
                )
            
            estados_conversa[telefone] = {
                "estado": "CADASTRO_NOME",
                "dados": {"telefone": telefone}
            }
            return "Perfeito! 😊\nVamos começar seu cadastro.\n\nInforme seu *nome completo*."
        elif mensagem == "2":
            # Vai para menu de dúvidas
            estados_conversa[telefone] = "MENU_DUVIDAS"
            return (
                "Claro! Sobre o que você precisa?\n\n"
                "1️⃣ Dúvida sobre produto\n"
                "2️⃣ Horários da loja\n"
                "3️⃣ Formas de pagamento\n"
                "4️⃣ Outro assunto\n"
                "0️⃣ Voltar"
            )
        elif mensagem == "3":
            transferir_para_humano(telefone, cliente)
            return "Chamando um atendente 👩‍💼"
        elif mensagem == "0":
            del estados_conversa[telefone]
            return "Até logo! 👋"
        else:
            return "Opção inválida. Digite 1, 2, 3 ou 0."

    # === Menu principal ===
    elif estado_info == "MENU_PRINCIPAL":
        tem_status = is_interacao_recente(cliente) if cliente else False
        
        if tem_status:
            # Menu com 4 opções (< 6h)
            if mensagem == "1":
                transferir_para_humano(telefone, cliente)
                return "Entendido! Vou te reconectar com o atendimento. Um momento... 👩‍💼"
            elif mensagem == "2":
                estados_conversa[telefone] = "AGUARDANDO_PEDIDO"
                return "Perfeito! Me diga o que você gostaria de pedir 🛒"
            elif mensagem == "3":
                # Mostrar pets para banho e tosa
                if cliente and cliente.get("pets"):
                    pets = cliente["pets"]
                    texto = "Qual pet você gostaria de agendar? 🐾\n\n"
                    for i, pet in enumerate(pets, 1):
                        icone = "🐶" if pet.get("especie") == "cao" else "🐱"
                        texto += f"{i}️⃣ {icone} {pet['nome']}\n"
                    texto += f"{len(pets)+1}️⃣ Cadastrar novo pet"
                    estados_conversa[telefone] = "SELECIONAR_PET_BANHO"
                    return texto
                else:
                    estados_conversa[telefone] = "AGUARDANDO_BANHO"
                    return "Qual pet você gostaria de agendar? 🐾"
            elif mensagem == "4":
                estados_conversa[telefone] = "MENU_DUVIDAS"
                return (
                    "Claro! Sobre o que você precisa?\n\n"
                    "1️⃣ Dúvida sobre produto\n"
                    "2️⃣ Horários da loja\n"
                    "3️⃣ Formas de pagamento\n"
                    "4️⃣ Outro assunto\n"
                    "0️⃣ Voltar"
                )
            elif mensagem == "0":
                del estados_conversa[telefone]
                primeiro_nome = cliente["nome"].split()[0] if cliente else "Cliente"
                return f"Até logo, {primeiro_nome}! 👋"
            else:
                return "Opção inválida. Digite 1, 2, 3, 4 ou 0."
        else:
            # Menu com 3 opções (> 6h)
            if mensagem == "1":
                estados_conversa[telefone] = "AGUARDANDO_PEDIDO"
                return "Perfeito! Me diga o que você gostaria de pedir 🛒"
            elif mensagem == "2":
                # Mostrar pets
                if cliente and cliente.get("pets"):
                    pets = cliente["pets"]
                    texto = "Qual pet você gostaria de agendar? 🐾\n\n"
                    for i, pet in enumerate(pets, 1):
                        icone = "🐶" if pet.get("especie") == "cao" else "🐱"
                        texto += f"{i}️⃣ {icone} {pet['nome']}\n"
                    texto += f"{len(pets)+1}️⃣ Cadastrar novo pet"
                    estados_conversa[telefone] = "SELECIONAR_PET_BANHO"
                    return texto
                else:
                    estados_conversa[telefone] = "AGUARDANDO_BANHO"
                    return "Qual pet você gostaria de agendar? 🐾"
            elif mensagem == "3":
                estados_conversa[telefone] = "MENU_DUVIDAS"
                return (
                    "Claro! Sobre o que você precisa?\n\n"
                    "1️⃣ Dúvida sobre produto\n"
                    "2️⃣ Horários da loja\n"
                    "3️⃣ Formas de pagamento\n"
                    "4️⃣ Outro assunto\n"
                    "0️⃣ Voltar"
                )
            elif mensagem == "0":
                del estados_conversa[telefone]
                primeiro_nome = cliente["nome"].split()[0] if cliente else "Cliente"
                return f"Até logo, {primeiro_nome}! 👋"
            else:
                return "Opção inválida. Digite 1, 2, 3 ou 0."

    # === Seleção de pet para banho ===
    elif estado_info == "SELECIONAR_PET_BANHO":
        try:
            opcao = int(mensagem)
            if cliente and cliente.get("pets"):
                pets = cliente["pets"]
                if 1 <= opcao <= len(pets):
                    pet_selecionado = pets[opcao - 1]
                    transferir_para_humano(telefone, cliente)
                    return f"Perfeito! Vou agendar banho e tosa para o(a) {pet_selecionado['nome']} 🐾\n\nTransferindo para atendente..."
                elif opcao == len(pets) + 1:
                    # Cadastrar novo pet
                    estados_conversa[telefone] = {
                        "estado": "NOVO_PET_NOME",
                        "dados": {}
                    }
                    return "Vamos cadastrar um novo pet! 🐾\n\nQual o *nome* dele?"
        except:
            pass
        return "Opção inválida. Digite o número do pet."

    # === Cadastro de novo pet ===
    elif isinstance(estado_info, dict) and estado_info.get("estado") == "NOVO_PET_NOME":
        dados = estado_info["dados"]
        dados["nome"] = mensagem.title()
        estado_info["estado"] = "NOVO_PET_ESPECIE"
        return "Qual a espécie?\n\n1️⃣ Cachorro\n2️⃣ Gato"

    elif isinstance(estado_info, dict) and estado_info.get("estado") == "NOVO_PET_ESPECIE":
        dados = estado_info["dados"]
        if mensagem == "1":
            dados["especie"] = "cao"
        elif mensagem == "2":
            dados["especie"] = "gato"
        else:
            return "Digite:\n1️⃣ Cachorro\n2️⃣ Gato"
        estado_info["estado"] = "NOVO_PET_GENERO"
        return f"O(a) {dados['nome']} é:\n\n1️⃣ Macho\n2️⃣ Fêmea"

    elif isinstance(estado_info, dict) and estado_info.get("estado") == "NOVO_PET_GENERO":
        dados = estado_info["dados"]
        if mensagem == "1":
            dados["genero"] = "macho"
        elif mensagem == "2":
            dados["genero"] = "femea"
        else:
            return "Digite:\n1️⃣ Macho\n2️⃣ Fêmea"
        estado_info["estado"] = "NOVO_PET_IDADE"
        artigo = "o" if dados["genero"] == "macho" else "a"
        return f"Qual a *idade* d{artigo} {dados['nome']}? (em anos)"

    elif isinstance(estado_info, dict) and estado_info.get("estado") == "NOVO_PET_IDADE":
        dados = estado_info["dados"]
        try:
            dados["idade"] = int(mensagem)
        except:
            return "Digite apenas o número (ex: 3)"
        estado_info["estado"] = "NOVO_PET_CASTRADO"
        artigo = "o" if dados.get("genero") == "macho" else "a"
        castrado_txt = "castrado" if dados.get("genero") == "macho" else "castrada"
        return f"{artigo.capitalize()} {dados['nome']} é {castrado_txt}?\n\n1️⃣ Sim\n2️⃣ Não"

    elif isinstance(estado_info, dict) and estado_info.get("estado") == "NOVO_PET_CASTRADO":
        dados = estado_info["dados"]
        if mensagem == "1":
            dados["castrado"] = True
        elif mensagem == "2":
            dados["castrado"] = False
        else:
            return "Digite:\n1️⃣ Sim\n2️⃣ Não"
        estado_info["estado"] = "NOVO_PET_ALERGICO"
        artigo = "o" if dados.get("genero") == "macho" else "a"
        return f"{artigo.capitalize()} {dados['nome']} tem alguma *alergia*?\n(Digite o nome ou 'nenhuma')"

    elif isinstance(estado_info, dict) and estado_info.get("estado") == "NOVO_PET_ALERGICO":
        dados = estado_info["dados"]
        if mensagem.lower() in ["nenhuma", "não", "nao", "nenhum"]:
            dados["alergico"] = ""
        else:
            dados["alergico"] = mensagem
        
        # Adiciona pet ao cliente
        if cliente:
            cliente["pets"].append(dados)
            salvar_clientes()
        
        estados_conversa[telefone] = "MENU_PRINCIPAL"
        return (
            f"Pet {dados['nome']} cadastrado com sucesso! 🐾\n\n"
            "Voltando ao menu principal..."
        )

    # === Menu de dúvidas ===
    elif estado_info == "MENU_DUVIDAS":
        if mensagem == "1":
            transferir_para_humano(telefone, cliente)
            return "Vou transferir para um atendente que pode te ajudar com produtos 👩‍💼"
        elif mensagem == "2":
            return (
                "📍 *Nosso horário:*\n\n"
                "Segunda a Sexta: 08h às 19h\n"
                "Sábado: 08h às 18h\n"
                "Domingo: Fechado\n\n"
                "Digite *MENU* para voltar."
            )
        elif mensagem == "3":
            return (
                "💳 *Formas de pagamento:*\n\n"
                "• Dinheiro\n"
                "• Cartão (crédito/débito)\n"
                "• PIX\n"
                "• Transferência bancária\n\n"
                "Digite *MENU* para voltar."
            )
        elif mensagem == "4":
            transferir_para_humano(telefone, cliente)
            return "Claro! Vou te conectar com um atendente 👩‍💼"
        elif mensagem == "0":
            # Volta ao menu apropriado
            if cliente:
                estados_conversa[telefone] = "MENU_PRINCIPAL"
                return "Voltando ao menu..."
            else:
                estados_conversa[telefone] = "MENU_INICIAL"
                primeiro_nome = nome_whats.split()[0]
                return (
                    f"Ok, {primeiro_nome}!\n\n"
                    "1️⃣ Quero me cadastrar\n"
                    "2️⃣ Dúvidas\n"
                    "3️⃣ Falar com atendente\n"
                    "0️⃣ Sair"
                )
        else:
            return "Opção inválida. Digite 1, 2, 3, 4 ou 0."

    # === Outros estados ===
    elif estado_info == "HUMANO":
        return None  # Bot em silêncio
    
    elif estado_info == "AGUARDANDO_PEDIDO":
        transferir_para_humano(telefone, cliente)
        return f"Anotado! Vou transferir seu pedido: '{mensagem}'"
    
    elif estado_info == "AGUARDANDO_BANHO":
        transferir_para_humano(telefone, cliente)
        return f"Vou transferir para agendar banho e tosa: '{mensagem}'"

    return None

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(silent=True)
        if not data or "messages" not in data or not data["messages"]:
            return "OK", 200

        msg = data["messages"][0]
        if "text" not in msg or "body" not in msg["text"]:
            return "OK", 200

        mensagem = msg["text"]["body"].strip()
        numero_full = msg["from"]
        telefone = numero_full.split("@")[0]
        nome_whats = msg.get("pushname", msg.get("from_name", "Cliente")).strip()

        print(f"\n{'='*60}")
        print(f"[WEBHOOK] Mensagem recebida")
        print(f"[WEBHOOK] Telefone: {telefone}")
        print(f"[WEBHOOK] Nome WhatsApp: {nome_whats}")
        print(f"[WEBHOOK] Mensagem: {mensagem}")
        
        cliente = buscar_cliente_por_telefone(telefone)
        
        if cliente:
            print(f"[WEBHOOK] ✓ Cliente ENCONTRADO: {cliente.get('nome')}")
        else:
            print(f"[WEBHOOK] ✗ Cliente NÃO cadastrado")
        print(f"{'='*60}\n")

        # ==================================================
        # VERIFICAR TIMEOUT HUMANO (2h)
        # ==================================================
        if estados_conversa.get(telefone) == "HUMANO":
            try:
                timestamp_str = cliente.get("timestamp_humano") if cliente else None
                if timestamp_str:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
                    tempo_decorrido = agora - timestamp
                    
                    if tempo_decorrido >= timedelta(hours=TIMEOUT_HUMANO_HORAS):
                        del estados_conversa[telefone]
                        if cliente:
                            cliente["ultima_interacao_completa"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                            cliente.pop("timestamp_humano", None)
                            salvar_clientes()
                    else:
                        return "OK", 200
                else:
                    return "OK", 200
            except:
                return "OK", 200

        # ==================================================
        # COMANDOS GLOBAIS
        # ==================================================
        comandos_sair = ["sair", "parar", "stop", "cancelar", "tchau", "bye"]
        if mensagem.lower() in comandos_sair:
            if telefone in estados_conversa:
                del estados_conversa[telefone]
            primeiro_nome = cliente["nome"].split()[0] if cliente else "Cliente"
            enviar_mensagem(
                numero_full,
                f"Entendido, {primeiro_nome}! 👋\n\n"
                "Quando precisar, estarei aqui!"
            )
            return "OK", 200

        if mensagem.lower() == "menu":
            if telefone in estados_conversa:
                del estados_conversa[telefone]
            if cliente:
                estados_conversa[telefone] = "MENU_PRINCIPAL"
                primeiro_nome = cliente["nome"].split()[0]
                agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
                cliente["ultima_interacao_completa"] = agora.strftime("%Y-%m-%d %H:%M:%S")
                
                if is_interacao_recente(cliente):
                    enviar_mensagem(
                        numero_full,
                        f"Ok, {primeiro_nome}!\n\n"
                        "1️⃣ Continuar meu atendimento\n"
                        "2️⃣ Fazer um novo pedido\n"
                        "3️⃣ Agendar banho e tosa\n"
                        "4️⃣ Outro assunto\n"
                        "0️⃣ Sair"
                    )
                else:
                    enviar_mensagem(
                        numero_full,
                        f"Ok, {primeiro_nome}!\n\n"
                        "1️⃣ Fazer um pedido\n"
                        "2️⃣ Agendar banho e tosa\n"
                        "3️⃣ Falar com atendente\n"
                        "0️⃣ Sair"
                    )
            return "OK", 200

        # ==================================================
        # URGÊNCIA
        # ==================================================
        if is_urgente(mensagem):
            transferir_para_humano(telefone, cliente)
            enviar_mensagem(numero_full, "🚨 Entendi que é urgente! Chamando atendente...")
            return "OK", 200

        # ==================================================
        # PROCESSAR ESTADO ATIVO
        # ==================================================
        resposta = processar_estado(telefone, mensagem, cliente, nome_whats)
        if resposta:
            enviar_mensagem(numero_full, resposta)
            return "OK", 200

        # ==================================================
        # FORA DO HORÁRIO
        # ==================================================
        if not dentro_horario_atendimento():
            enviar_mensagem(
                numero_full,
                "⏰ Nosso horário:\n\n"
                "Seg–Sex: 08h às 19h\n"
                "Sábado: 08h às 18h\n\n"
                "Te respondemos assim que abrirmos 😊"
            )
            return "OK", 200

        # ==================================================
        # MARKETING AUTOMÁTICO
        # ==================================================
        if cliente and precisa_enviar_marketing(cliente):
            msg_marketing = mensagem_marketing_personalizada(cliente)
            enviar_mensagem(numero_full, msg_marketing)
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            cliente["ultima_interacao"] = agora.strftime("%Y-%m-%d")
            cliente["ultima_interacao_completa"] = agora.strftime("%Y-%m-%d %H:%M:%S")
            salvar_clientes()
            return "OK", 200

        # ==================================================
        # MENU INICIAL
        # ==================================================
        if cliente:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            cliente["ultima_interacao"] = agora.strftime("%Y-%m-%d")
            cliente["ultima_interacao_completa"] = agora.strftime("%Y-%m-%d %H:%M:%S")
            salvar_clientes()
            
            estados_conversa[telefone] = "MENU_PRINCIPAL"
            primeiro_nome = cliente["nome"].split()[0]
            
            # Pega o nome do pet para mensagem mais carinhosa
            nome_pet = ""
            if cliente.get("pets"):
                nome_pet = cliente["pets"][0]["nome"]
            
            if is_interacao_recente(cliente):
                if nome_pet:
                    resposta = (
                        f"Olá, {primeiro_nome}! Que bom te ver de novo! 😊\n"
                        f"Como está o(a) {nome_pet}? 🐾\n\n"
                        "Como posso ajudar?\n\n"
                        "1️⃣ Continuar meu atendimento\n"
                        "2️⃣ Fazer um novo pedido\n"
                        "3️⃣ Agendar banho e tosa\n"
                        "4️⃣ Outro assunto\n"
                        "0️⃣ Sair"
                    )
                else:
                    resposta = (
                        f"Olá, {primeiro_nome}! 😊\n\n"
                        "Como posso ajudar?\n\n"
                        "1️⃣ Continuar meu atendimento\n"
                        "2️⃣ Fazer um novo pedido\n"
                        "3️⃣ Agendar banho e tosa\n"
                        "4️⃣ Outro assunto\n"
                        "0️⃣ Sair"
                    )
            else:
                if nome_pet:
                    resposta = (
                        f"Olá, {primeiro_nome}! Que alegria te ver! 💚\n"
                        f"Como está o(a) {nome_pet}? 🐾\n\n"
                        "Como posso ajudar hoje?\n\n"
                        "1️⃣ Fazer um pedido\n"
                        "2️⃣ Agendar banho e tosa\n"
                        "3️⃣ Falar com atendente\n"
                        "0️⃣ Sair"
                    )
                else:
                    resposta = (
                        f"Olá, {primeiro_nome}! Que bom te ver! 😊\n\n"
                        "Como posso ajudar?\n\n"
                        "1️⃣ Fazer um pedido\n"
                        "2️⃣ Agendar banho e tosa\n"
                        "3️⃣ Falar com atendente\n"
                        "0️⃣ Sair"
                    )
        else:
            estados_conversa[telefone] = "MENU_INICIAL"
            primeiro_nome = nome_whats.split()[0]
            resposta = (
                f"Olá, {primeiro_nome}! 🐾\n\n"
                "Vejo que ainda não tem cadastro.\n\n"
                "1️⃣ Quero me cadastrar\n"
                "2️⃣ Dúvidas\n"
                "3️⃣ Falar com atendente\n"
                "0️⃣ Sair"
            )

        enviar_mensagem(numero_full, resposta)
        return "OK", 200

    except Exception as e:
        print(f"Erro: {type(e).__name__} → {e}")
        return "Erro interno", 500

# ================= MAIN =================
if __name__ == "__main__":
    # Apenas para desenvolvimento local
    # No Render, o gunicorn gerencia isso
    porta = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=porta, debug=False)

