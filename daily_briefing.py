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

genai.configure(api_key=GEMINI_API_KEY)

# 네이버 차단 방지용 헤더
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://finance.naver.com/'
}

def get_market_data():
    """국내외 증시 수집 (네이버 실패 시 야후 파이낸스 자동 대체)"""
    report = "📊 [국내외 주요 지수 및 지표]\n"
    data_for_ai = ""
    
    us_tickers = {'🇺🇸 S&P 500': '^GSPC', '🇺🇸 나스닥': '^IXIC'}
    for name, ticker in us_tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                prev = hist['Close'].iloc[0]
                curr = hist['Close'].iloc[1]
                change_percent = ((curr - prev) / prev) * 100
                sign = "+" if change_percent > 0 else ""
                report += f"{name}: {curr:,.2f} ({sign}{change_percent:.2f}%)\n"
                data_for_ai += f"{name}: {sign}{change_percent:.2f}% 변동\n"
        except:
            pass
            
    # 국내 증시 (네이버 금융 시세 전용 페이지)
    try:
        url = "https://finance.naver.com/sise/"
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        kospi = soup.select_one('#KOSPI_now').text
        kospi_change = soup.select_one('#KOSPI_change').text.strip()
        kosdaq = soup.select_one('#KOSDAQ_now').text
        kosdaq_change = soup.select_one('#KOSDAQ_change').text.strip()
        
        report += f"🇰🇷 코스피: {kospi} ({kospi_change})\n"
        report += f"🇰🇷 코스닥: {kosdaq} ({kosdaq_change})\n"
        data_for_ai += f"코스피: {kospi}, 코스닥: {kosdaq}\n"
    except Exception:
        try:
            for name, ticker in {'🇰🇷 코스피': '^KS11', '🇰🇷 코스닥': '^KQ11'}.items():
                hist = yf.Ticker(ticker).history(period="2d")
                if len(hist) >= 2:
                    prev = hist['Close'].iloc[0]
                    curr = hist['Close'].iloc[1]
                    change_percent = ((curr - prev) / prev) * 100
                    sign = "+" if change_percent > 0 else ""
                    report += f"{name}: {curr:,.2f} ({sign}{change_percent:.2f}%)\n"
                    data_for_ai += f"{name}: {sign}{change_percent:.2f}% 변동\n"
        except:
            report += "🇰🇷 국내 증시 데이터를 불러오지 못했습니다.\n"

    return report, data_for_ai

def get_naver_popular_stocks():
    """네이버 인기 검색 종목"""
    url = "https://finance.naver.com/sise/lastsearch2.naver"
    report = "\n🔥 [네이버 금융 인기 검색 종목 TOP 5]\n"
    stock_data = ""
    try:
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            if 'item/main.naver?code=' in link['href'] and link.text.strip():
                title = link.text.strip()
                report += f"{count+1}. {title}\n"
                stock_data += f"{title}, "
                count += 1
                if count == 5: break
    except:
        report += "인기 종목을 불러오지 못했습니다.\n"
        
    return report, stock_data

def get_news_headlines():
    url = "https://news.google.com/rss/search?q=증시+OR+주식+OR+금리&hl=ko&gl=KR&ceid=KR:ko"
    report = "\n📰 [오늘의 증시/경제 주요 뉴스]\n"
    news_for_ai = ""
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all('item')[:5] 
        for i, item in enumerate(items, 1):
            title = item.title.text
            report += f"{i}. {title}\n"
            news_for_ai += f"- {title}\n"
    except:
        pass
    return report, news_for_ai

def get_gemini_analysis(market_data, popular_stocks, news_data):
    # AI에게 내리는 명령(프롬프트)을 더욱 구체화했습니다.
    prompt = f"""
    당신은 상위 1% VIP 자산가를 전담하는 최고급 웰스매니저이자 주식 애널리스트입니다.
    아래 데이터를 분석하여, 오늘 한국 시장 참여자에게 전달할 구체적이고 실전적인 투자 전략을 제시해 주세요.

    [시장 데이터]: {market_data}
    [국내 인기 종목]: {popular_stocks}
    [주요 뉴스]: {news_data}

    반드시 아래 5가지 양식에 맞추어 전문적이고 명확하게 작성해 주세요 (마크다운 및 이모지 적극 활용):
    
    1. 🎯 오늘의 투자 방향성 (현재 장세에 대한 뷰와 한 줄 평)
    2. 🏆 오늘의 국내 주식 TOP 5 (가장 유망한 섹터와 구체적인 종목명 5가지를 순위별로 추천 사유와 함께 명시)
    3. 🌎 오늘의 해외 주식 TOP 5 (미국 등 글로벌 유망 섹터와 구체적인 종목명 5가지를 순위별로 추천 사유와 함께 명시)
    4. 📊 ETF 투자 아이디어 (현재 장세에 맞는 구체적인 ETF 테마 및 티커 추천)
    5. 🛡️ 연금 및 채권 전략 (개인연금/퇴직연금 비중 조절 및 채권 투자 매력도)
    """
    
    try:
        model = genai.GenerativeModel('gemini-3.8-flash')
        response = model.generate_content(prompt)
        return f"\n🤖 [AI 웰스매니저의 실전 투자 가이드]\n{response.text}\n"
    except Exception as e:
        return f"\n🤖 [AI 분석 실패]: {e}\n"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': message})

if __name__ == "__main__":
    tz_kr = pytz.timezone('Asia/Seoul')
    today = datetime.now(tz_kr).strftime("%Y년 %m월 %d일")
    
    market_report, market_data = get_market_data()
    popular_report, popular_stocks = get_naver_popular_stocks()
    news_report, news_data = get_news_headlines()
    
    ai_report = get_gemini_analysis(market_data, popular_stocks, news_data)
    
    final_message = f"🌅 {today} 프리미엄 투자 브리핑\n\n"
    final_message += market_report
    final_message += popular_report
    final_message += news_report
    final_message += ai_report
    final_message += "\n오늘도 성공적인 투자 되세요! 🚀"
    
    send_telegram_message(final_message)
