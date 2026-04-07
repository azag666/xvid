@bot.callback_query_handler(func=lambda call: call.data.startswith('pix_'))
def handle_pix_click(call):
    # 1. Tentar apagar a mensagem do vídeo imediatamente para limpar o chat
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        print(f"Erro ao apagar mensagem: {e}")

    # 2. Extrair valor e gerar PIX
    try:
        valor_centavos = int(call.data.split('_')[1])
    except:
        valor_centavos = 1699
        
    valor_reais = valor_centavos / 100
    
    # Notificação temporária no topo do ecrã do utilizador
    bot.answer_callback_query(call.id, "Gerando seu acesso VIP...")

    data = gerar_pix_pushinpay(valor_centavos)
    
    if data:
        pix_code = data.get('qr_code') or data.get('qr_code_text') or data.get('brcode')
        
        mensagem = (
            f"⚡ <b>ACESSO SOLICITADO!</b>\n\n"
            f"👤 <b>Cliente:</b> @{call.from_user.username if call.from_user.username else 'Utilizador'}\n"
            f"💰 <b>Valor:</b> R$ {valor_reais:.2f}\n\n"
            f"👇 <b>CÓDIGO PIX COPIA E COLA:</b>\n\n"
            f"<code>{pix_code}</code>\n\n"
            f"<i>💡 Toque no código acima para copiar. Após o pagamento, o conteúdo será libertado aqui no grupo.</i>"
        )
        
        # Envia a nova mensagem no lugar da antiga
        bot.send_message(call.message.chat.id, mensagem, parse_mode="HTML")
    else:
        bot.send_message(call.message.chat.id, "❌ Erro ao gerar PIX. Tente novamente mais tarde.")
