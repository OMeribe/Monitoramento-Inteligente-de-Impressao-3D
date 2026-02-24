@echo off
title Monitor LabInd - Inicializacao Automatica
color 0A

:: --- BLOCO 1: VERIFICAÇÃO E INSTALAÇÃO ---
if not exist "venv" (
    echo [AVISO] Primeira vez detectada! Configurando o sistema...
    echo Criando ambiente virtual...
    python -m venv venv
    
    echo Ativando e instalando bibliotecas...
    call .\venv\Scripts\activate
    
    :: Instala sem perguntar nada
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    cls
    echo [SUCESSO] Instalacao concluida! Iniciando o sistema...
) else (
    :: Se ja existe, so ativa
    call .\venv\Scripts\activate
)

:: --- BLOCO 2: EXECUÇÃO ---
echo Iniciando Inteligencia Artificial...
python src\detectar_webcam.py

:: Se der erro, nao fecha a janela na cara
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [ERRO] O programa fechou inesperadamente.
    pause
)