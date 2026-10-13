import yfinance as yf
import requests
from datetime import datetime
import pytz

# ==========================================
# 1. 텔레그램 정보 입력 (발급받은 정보로 수정하세요)
# ==========================================
TELEGRAM_TOKEN = '8962847594:AAHVPlZJvieTvOgUMX1drTZ7QgpfUU69sto'
CHAT_ID = '8967404817'

def get_us_market_data():
    """야후 파이낸스(yfinance)를 이용해 미국 3대 지수 마감 데이터 수집"""
    tickers = {'🇺🇸 다우존스': '^DJI', '🇺🇸 S&P 500': '^GSPC', '🇺🇸 나스닥': '^IXIC'}
    report = "📊 [밤사이 미국 증시 마감 시황]\n\n"
    
    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker)
            # 최근 2일치 데이터를 가져와서 전일 대비 변동률 계산
            hist = data.history(period="2d")
            
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[0]
                current_close = hist['Close'].iloc[1]
                change = current_close - prev_close
                change_percent = (change / prev_close) * 100
                
                # 상승/하락에 따른 기호 설정
                sign = "+" if change > 0 else ""
                report += f"{name}: {current_close:,.2f} ({sign}{change_percent:.2f}%)\n"
            else:
                report += f"{name}: 데이터 조회 실패\n"
        except Exception as e:
            report += f"{name}: 에러 발생 ({e})\n"
            
    return report

def send_telegram_message(message):
    """텔레그램 봇 API를 통해 메시지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message
    }
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        print("✅ 텔레그램 메시지 전송 성공!")
    else:
        print(f"❌ 전송 실패: {response.text}")

if __name__ == "__main__":
    # 한국 시간 기준으로 오늘 날짜 포맷팅
    tz_kr = pytz.timezone('Asia/Seoul')
    today = datetime.now(tz_kr).strftime("%Y년 %m월 %d일")
    
    # 1. 메시지 내용 조합
    final_message = f"🌅 {today} 아침 시황 브리핑입니다.\n\n"
    final_message += get_us_market_data()
    final_message += "\n오늘도 성공적인 투자 되세요! 🚀"
    
    # 2. 텔레그램으로 발송
    send_telegram_message(final_message)
