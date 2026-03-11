import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
import json
import time

# --- DADOS EXTRAÍDOS DAS SUAS FOTOS ---
IP_IMPRESSORA = "192.168.100.81"  #
ACCESS_CODE = "49888f6a"          #
SERIAL_NO = "00M09D4B0301455"      #

def disparar_pausa():
    # Usando a versão mais recente da API para evitar warnings
    client = mqtt.Client(CallbackAPIVersion.VERSION2)
    
    # Configuração de segurança para LAN Mode
    client.tls_set(cert_reqs=mqtt.ssl.CERT_NONE)
    client.username_pw_set("bblp", ACCESS_CODE)

    try:
        print(f"🔄 Conectando à impressora no IP {IP_IMPRESSORA}...")
        client.connect(IP_IMPRESSORA, 8883, 60)
        client.loop_start()

        # Tópico correto para envio de comandos
        topic = f"device/{SERIAL_NO}/request"
        
        # Payload formatado para o firmware atual
        payload = {
            "print": {
                "sequence_id": "1", # ID para identificar novo comando
                "command": "pause",
                "param": ""
            }
        }
        
        print("📤 Enviando comando de PAUSA...")
        resultado = client.publish(topic, json.dumps(payload), qos=1)
        
        # Aguarda a confirmação de que o pacote saiu do PC
        resultado.wait_for_publish()
        
        print("✅ Comando entregue com sucesso!")
        time.sleep(2) # Tempo para a impressora processar a instrução
        
        client.loop_stop()
        client.disconnect()
        print("🏁 Teste concluído. Verifique o estado da impressora.")

    except Exception as e:
        print(f"❌ Falha na conexão: {e}")

if __name__ == "__main__":
    disparar_pausa()