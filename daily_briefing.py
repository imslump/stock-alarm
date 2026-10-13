import yfinance as yf
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from datetime import datetime
import pytz
import os

# ==========================================
# 1. 깃허브 비밀 금고(Secrets)에서 정보 가져오기
# ==========================================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Gemini AI 설정
genai.configure(api_key=GEMINI_API_KEY)

def get_market_data():
    """국내외 주요 지수 및 환율/원자재 데이터 수집"""
    tickers = {
        '🇺🇸 S&P 500': '^GSPC', 
        '🇺🇸 나스닥': '^IXIC',
        '🇰🇷 코스피': '^KS11',
        '🇰🇷 코스닥': '^KQ11',
        '💵 원/달러 환율': 'KRW=X',
        '🛢️ WTI 원유': 'CL=F',
        '🥇 금': 'GC=F'
    }
    
    report = "📊 [주요 글로벌 지수 및 지표]\n"
    data_for_ai = "" # AI에게 분석을 맡길 원본 데이터
    
    for name, ticker in tickers.items():
        try:
            data = yf.Ticker(ticker)
            hist = data.history(period="2d")
            
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[0]
                current_close = hist['Close'].iloc[1]
                change = current_close - prev_close
                change_percent = (change / prev_close) * 100
                
                sign = "+" if change > 0 else ""
                line = f"{name}: {current_close:,.2f} ({sign}{change_percent:.2f}%)\n"
                report += line
                data_for_ai += line
            else:
                report += f"{name}: 데이터 없음\n"
        except Exception:
            pass
            
    return report, data_for_ai

def get_news_headlines():
    """구글 뉴스 RSS를 활용한 주요 증시 뉴스 크롤링"""
    url = "https://news.google.com/rss/search?q=증시&hl=ko&gl=KR&ceid=KR:ko"
    report = "\n📰 [오늘의 증시 주요 뉴스]\n"
    news_for_ai = ""
    
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('item')[:5] # 최신 뉴스 5개만 가져오기
        
        for i, item in enumerate(items, 1):
            title = item.title.text
            report += f"{i}. {title}\n"
            news_for_ai += f"- {title}\n"
    except Exception as e:
        report += "뉴스 데이터를 불러오지 못했습니다.\n"
        
    return report, news_for_ai

def get_gemini_analysis(market_data, news_data):
    """Gemini AI를 이용한 시황 요약 및 투자 인사이트 도출"""
    prompt = f"""
    당신은 세계 최고의 월스트리트 주식 애널리스트입니다.
    아래에 제공된 오늘 아침의 [시장 데이터]와 [주요 뉴스]를 종합적으로 분석하여,
    오늘 한국 증시(코스피/코스닥)의 예상 흐름과 주목해야 할 특징적인 섹터를 3~4줄로 명확하게 브리핑해 주세요.
    가독성 좋게 이모지도 섞어서 전문적이고 정중한 말투로 작성해 주세요.

    [시장 데이터]
    {market_data}

    [주요 뉴스]
    {news_data}
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return f"\n🤖 [Gemini AI 시황 분석 및 전략]\n{response.text}\n"
    except Exception as e:
        return f"\n🤖 [AI 분석 실패]: {e}\n"

def send_telegram_message(message):
    """텔레그램 발송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': message})

if __name__ == "__main__":
    tz_kr = pytz.timezone('Asia/Seoul')
    today = datetime.now(tz_kr).strftime("%Y년 %m월 %d일")
    
    market_report, market_data = get_market_data()
    news_report, news_data = get_news_headlines()
    ai_report = get_gemini_analysis(market_data, news_data)
    
    final_message = f"🌅 {today} 인공지능 시황 브리핑\n\n"
    final_message += market_report
    final_message += news_report
    final_message += ai_report
    final_message += "\n오늘도 성공적인 투자 되세요! 🚀"
    
    send_telegram_message(final_message)
