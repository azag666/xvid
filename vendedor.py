import os
import requests
import telebot
import json

# CONFIGURAÇÃO DE CREDENCIAIS
TELEGRAM_TOKEN = "8670603961:AAE8GeYVYjuNqpouzE7IZv4Knx6XrIZkxYU"
PUSHINPAY_TOKEN = "63870|0NFpiGh89fCg4FDeU7KnfqqqUdnEKvxeuZ4LLHGv13fd7d0c"
PUSHINPAY_API_URL = 'https://api.pushinpay.com.br/api'

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def gerar_pix_pushinpay(valor_centavos):
    url = f"{PUSHINPAY_API_URL}/pix/cashIn"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {PUSHINPAY_TOKEN}'
    }
    payload = {"value": valor_centavos}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"❌ Erro na PushinPay: {e}")
        return None

@bot.callback_query_handler(func=lambda call: call.data.startswith('pix_'))
def handle_pix_click(call):
    # 1. Feedback visual imediato (o botão para de girar no telemóvel do utilizador)
    bot.answer_callback_query(call.id, "A gerar o seu código PIX...")

    # 2. Tentar apagar a mensagem do vídeo (Exige que o Bot seja ADMIN)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"⚠️ Não foi possível apagar a mensagem: {e}. Certifique-se que o bot é ADMIN.")

    # 3. Processar o valor
    valor_centavos = int(call.data.split('_')[1])
    valor_reais = valor_centavos / 100

    # 4. Gerar PIX
    data = gerar_pix_pushinpay(valor_centavos)
    
    if data:
        pix_code = data.get('qr_code') or data.get('qr_code_text') or data.get('brcode')
        
        mensagem = (
            f"✅ <b>PEDIDO INICIADO COM SUCESSO!</b>\n\n"
            f"👤 <b>Utilizador:</b> @{call.from_user.username if call.from_user.username else 'Sem Username'}\n"
            f"💰 <b>Valor a Pagar:</b> R$ {valor_reais:.2f}\n\n"
            f"👇 <b>COPIA E COLA ABAIXO:</b>\n\n"
            f"<code>{pix_code}</code>\n\n"
            f"<i>💡 Toque no código para copiar. O acesso será libertado automaticamente após o pagamento.</i>"
        )
        bot.send_message(call.message.chat.id, mensagem, parse_mode="HTML")
    else:
        bot.send_message(call.message.chat.id, "❌ Erro temporário no sistema de pagamentos. Tente novamente.")

if __name__ == "__main__":
    print("🤖 Bot Vendedor Online e pronto para o ID -1003652772157!")
    bot.infinity_polling()
