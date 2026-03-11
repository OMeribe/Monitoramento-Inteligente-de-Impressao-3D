# 🖨️ Monitoramento Inteligente de Impressão 3D (YOLO + Edge Computing)

Este repositório contém o código-fonte de um sistema de Visão Computacional industrial desenvolvido para o monitoramento e interrupção autônoma de falhas em impressoras 3D (FDM). 

O sistema utiliza o algoritmo **YOLO** para detecção de anomalias em tempo real e atua como um dispositivo de borda (*Edge Computing*), enviando comandos de parada (*Kill Switch*) via **MQTT** ou **Serial** para evitar desperdício de filamento.

## ✨ Principais Funcionalidades

* **🧠 Visão Computacional (YOLO):** Detecção de defeitos críticos de extrusão, como *Blobbing*, *Spaghetti*, *Stringing*, *Under Extrusion* e *Over Extrusion*.
* **⚡ Processamento Assíncrono (3 Threads):** Arquitetura paralela não-bloqueante que separa a captura de vídeo, a inferência da IA e a renderização da interface (UI). Garante a interface rodando a ~25 FPS enquanto a IA processa a ~2 FPS, sem gargalos.
* **🎯 Seleção Dinâmica de ROI:** Ferramenta interativa na UI para selecionar a "Região de Interesse", reduzindo o custo computacional e aumentando a precisão ao focar apenas na mesa de impressão.
* **🛑 Ação Autônoma (*Kill Switch*):** Integração direta com o *broker* da Bambu Lab (via Paho MQTT) e impressoras baseadas em Marlin (via G-Code Serial) para pausar a máquina automaticamente ao confirmar uma falha.
* **🛡️ Mitigação de Falsos Positivos:** Sistema de persistência temporal (exige confirmação da falha por 30 frames consecutivos) e botão de "Falso Positivo" para intervenção humana.
* **📱 Alertas Multicanal:** Envio autônomo de alertas com *snapshots* (capturas de tela) da falha via **Telegram** e **E-mail**, com sistema de *Cooldown* configurável para evitar *spam*.
* **📊 Log de Dados:** Registro automático de ocorrências em arquivo `.csv` para futura análise de qualidade.

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.8+
* **Inteligência Artificial:** YOLO (Ultralytics)
* **Visão Computacional:** OpenCV (`cv2`)
* **Interface Gráfica (GUI):** CustomTkinter / Tkinter
* **Comunicação IoT:** Paho-MQTT, PySerial, Requests

## 🚀 Como Executar

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/OMeribe/tcc-impressao3d-ia.git](https://github.com/OMeribe/tcc-impressao3d-ia.git)
   cd tcc-impressao3d-ia

2. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt

3. **Execute o sistema:**
   ```bash
   python detectar_webcam.py

## 🤝 Contexto

Projeto desenvolvido no contexto de Trabalho de Conclusão de Curso focado na aplicação de IA na Manufatura Aditiva (Indústria 4.0), operando no Laboratório de Informática Industrial (Labind).