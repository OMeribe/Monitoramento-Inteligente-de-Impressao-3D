# ==============================================================================
# 1. INSTALAÇÃO E CONFIGURAÇÃO
# ==============================================================================
#!pip install -q ultralytics roboflow

import os
import yaml
from ultralytics import YOLO
from roboflow import Roboflow
from google.colab import drive

# --- PASSO 1: MONTAR DRIVE ---
print("📂 Montando Google Drive...")
drive.mount('/content/drive', force_remount=True)

# --- PASSO 2: CONFIGURAR CAMINHOS ---
PASTA_RAIZ = "/content/drive/MyDrive/tcc1/treino_automatico"
NOME_PROJETO_ATUAL = "tcc_continuacao_final"
caminho_peso_atual = f"{PASTA_RAIZ}/{NOME_PROJETO_ATUAL}/weights/last.pt"
caminho_peso_antigo = f"{PASTA_RAIZ}/yolov11_tcc/weights/last.pt"

# --- PASSO 3: BAIXAR DATASET BASE DO ROBOFLOW ---
print("\n📦 Baixando dataset base do Roboflow...")
rf = Roboflow(api_key="lKlzPAGShtufNtaQHPbt")
project = rf.workspace("sylucauc").project("3d-printing-failure-detection")
version = project.version(3)
dataset = version.download("yolov11")

# --- PASSO 4: INJEÇÃO DO MAKESENSE (Filtro CLAHE) ---
print("\n💉 Injetando imagens novas no dataset principal...")
# Descompacta os zips que você subiu na raiz do Colab (/content)
!unzip -q -o /content/fotos_clahe.zip -d /content/fotos_temp
!unzip -q -o /content/labels_makesense.zip -d /content/labels_temp

# Copia tudo para dentro da pasta de TREINO do dataset que o Roboflow baixou
!cp -r /content/fotos_temp/* {dataset.location}/train/images/
!cp -r /content/labels_temp/* {dataset.location}/train/labels/
print("✅ Injeção concluída! Dataset fundido com sucesso.")

# --- PASSO 5: RECRIANDO O MAPA (DATA.YAML) NA FORÇA BRUTA ---
# Isso impede o YOLO de se perder e baixar o dataset de cachorros/cavalos
dados_yaml = {
    'path': dataset.location,
    'train': 'train/images',
    'val': 'valid/images',
    'nc': 1,
    'names': ['Spaghetti'] # Se a sua classe no MakeSense for diferente, mude aqui!
}

caminho_novo_yaml = '/content/meu_data_corrigido.yaml'
with open(caminho_novo_yaml, 'w') as f:
    yaml.dump(dados_yaml, f)
print(f"✅ Arquivo YAML recriado blindado em: {caminho_novo_yaml}")

# ==============================================================================
# 2. LÓGICA INTELIGENTE DE RETOMADA E TREINO
# ==============================================================================
print(f"\n🔍 Verificando arquivos em: {PASTA_RAIZ}")

# CENÁRIO A: O treino novo (100 épocas) já começou e caiu no meio
if os.path.exists(caminho_peso_atual):
    print(f"✅ ENCONTRADO TREINO EM ANDAMENTO!")
    print(f"   Arquivo: {caminho_peso_atual}")
    print("   🔄 Ação: Retomando exatamente de onde parou (RESUME)...")

    model = YOLO(caminho_peso_atual)
    model.train(resume=True)

# CENÁRIO B: Iniciar a extensão para 100 épocas usando o modelo base antigo
elif os.path.exists(caminho_peso_antigo):
    print(f"⚠️ Treino atual não encontrado, mas achei o modelo base antigo.")
    print(f"   Base: {caminho_peso_antigo}")
    print("   🚀 Ação: Iniciando Transfer Learning para 100 épocas...")

    model = YOLO(caminho_peso_antigo)
    model.train(
        data=caminho_novo_yaml, # Aqui usamos o mapa blindado!
        epochs=100,
        patience=15,
        imgsz=640,
        device=0,
        project=PASTA_RAIZ,
        name=NOME_PROJETO_ATUAL,
        exist_ok=True,
        augment=True
    )

# CENÁRIO C: Pânico (Caminhos errados)
else:
    print("\n❌ ERRO CRÍTICO: Não encontrei nem o treino novo nem o base!")
    print(f"   Procurado: {caminho_peso_antigo}")