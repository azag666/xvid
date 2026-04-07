def send_to_telegram(data):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    caption = f"🔞 <b>{data['titulo']}</b>\n\n👇 <b>DESBLOQUEIE O VÍDEO COMPLETO ABAIXO</b> 👇"

    print(f"🚀 A enviar '{data['titulo']}' para o grupo...")
    try:
        with open(data['path'], 'rb') as video_file:
            payload = {
                'chat_id': CHAT_ID,
                'caption': caption,
                'parse_mode': 'HTML',
                'supports_streaming': 'true'
            }
            
            # BOTÕES INTERNOS (Acionam a geração do PIX direto no chat)
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "🔥 DESBLOQUEAR VÍDEO (R$ 16,99)", "callback_data": "pix_1699"}],
                    [{"text": "💎 ACESSO VIP VITALÍCIO (R$ 29,99)", "callback_data": "pix_2999"}]
                ]
            }
            payload['reply_markup'] = json.dumps(reply_markup)

            files = {'video': video_file}
            r = requests.post(api_url, data=payload, files=files, timeout=60)
            res = r.json()
            
        os.remove(data['path'])
        
        if res.get('ok'):
            print("✅ Sucesso no envio do vídeo com botões PIX!")
            return True
        else:
            print(f"❌ Erro Telegram: {res.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Erro no envio da rede: {e}")
        return False
