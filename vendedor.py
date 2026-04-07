import os
import requests
import telebot

# Substitua ou use variáveis de ambiente para o seu Token do Bot do Telegram
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'SEU_TELEGRAM_TOKEN_AQUI')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Credenciais da PushinPay extraídas do seu frontend
PUSHINPAY_API_URL = 'https://api.pushinpay.com.br/api'
PUSHINPAY_TOKEN = '63870|0NFpiGh89fCg4FDeU7KnfqqqUdnEKvxeuZ4LLHGv13fd7d0c'

def gerar_pix_pushinpay(valor_centavos):
    """Integração idêntica à do index (3).html"""
    url = f"{PUSHINPAY_API_URL}/pix/cashIn"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {PUSHINPAY_TOKEN}'
    }
    payload = {"value": valor_centavos}
    
    try:
        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code in (200, 201):
            return resp.json()
    except Exception as e:
        print(f"Erro na API PushinPay: {e}")
    return None

# Fica à escuta de qualquer clique nos botões que começam com "pix_"
@bot.callback_query_handler(func=lambda call: call.data.startswith('pix_'))
def handle_pix_click(call):
    # Aviso rápido para o botão parar de rodar no aplicativo do usuário
    bot.answer_callback_query(call.id, "Gerando sua chave PIX, aguarde um instante...")
    
    # Extrai o valor do callback data (ex: 'pix_1699' vira 1699)
    try:
        valor_centavos = int(call.data.split('_')[1])
    except:
        valor_centavos = 1699 # Fallback padrão de segurança
        
    valor_reais = valor_centavos / 100
    
    # Chama a API da PushinPay
    data = gerar_pix_pushinpay(valor_centavos)
    
    if data:
        # Busca a string do Pix Copia e Cola conforme o retorno da sua API
        pix_code = data.get('qr_code') or data.get('qr_code_text') or data.get('brcode')
        
        # Cria a mensagem formatando o PIX dentro da tag <code> para cópia em 1 clique
        mensagem = (
            f"✅ <b>PEDIDO GERADO COM SUCESSO!</b>\n\n"
            f"💳 <b>Valor do Acesso:</b> R$ {valor_reais:.2f}\n\n"
            f"👇 <b>Clique no código abaixo para Copiar:</b>\n\n"
            f"<code>{pix_code}</code>\n\n"
            f"<i>⏳ O acesso é liberado automaticamente após o pagamento via PIX!</i>"
        )
        
        # Envia a chave PIX no grupo, marcando (reply) o vídeo e o usuário que clicou
        bot.send_message(
            call.message.chat.id, 
            mensagem, 
            parse_mode="HTML", 
            reply_to_message_id=call.message.message_id
        )
    else:
        bot.send_message(
            call.message.chat.id, 
            "❌ Servidor de pagamentos ocupado. Tente clicar novamente em alguns segundos.", 
            reply_to_message_id=call.message.message_id
        )

if __name__ == "__main__":
    print("🤖 Bot Vendedor Iniciado! A monitorizar compras no grupo...")
    # Necessário instalar a biblioteca: pip install pyTelegramBotAPI requests
    bot.infinity_polling()
