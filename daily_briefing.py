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
    """야후 파이낸스(미국/원자재) + 네이버 금융(국내 증시) 혼합 수집"""
    report = "📊 [국내외 주요 지수 및 지표]\n"
    data_for_ai = ""
    
    # 1. 미국 증시 및 원자재 (야후 파이낸스가 가장 정확함)
    us_tickers = {'🇺🇸 S&P 500': '^GSPC', '🇺🇸 나스닥': '^IXIC', '🛢️ WTI 원유': 'CL=F', '🥇 금': 'GC=F'}
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
            
    # 2. 국내 증시 (네이버 금융 직접 크롤링 - 누락 없이 빠름)
    try:
        url = "https://finance.naver.com/"
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        kospi = soup.select_one('.kospi_area .num').text
        kospi_change = soup.select_one('.kospi_area .num2').text
        kosdaq = soup.select_one('.kosdaq_area .num').text
        kosdaq_change = soup.select_one('.kosdaq_area .num2').text
        
        report += f"🇰🇷 코스피 (네이버): {kospi} ({kospi_change})\n"
        report += f"🇰🇷 코스닥 (네이버): {kosdaq} ({kosdaq_change})\n"
        data_for_ai += f"코스피: {kospi}, 코스닥: {kosdaq}\n"
    except Exception as e:
        report += "🇰🇷 국내 증시 데이터를 불러오지 못했습니다.\n"

    return report, data_for_ai

def get_naver_popular_stocks():
    """네이버 금융 실시간 인기 검색 종목 수집"""
    url = "https://finance.naver.com/sise/lastsearch2.naver"
    report = "\n🔥 [네이버 금융 인기 검색 종목 TOP 5]\n"
    stock_data = ""
    try:
        res = requests.get(url)
        soup = BeautifulSoup(res.text, 'html.parser')
        rows = soup.select('table.type_5 tr')
        count = 0
        for row in rows:
            title_tag = row.select_one('a.tltle')
            if title_tag:
                title = title_tag.text
                report += f"{count+1}. {title}\n"
                stock_data += f"{title}, "
                count += 1
                if count == 5: break
    except:
        report += "인기 종목을 불러오지 못했습니다.\n"
        
    return report, stock_data

def get_news_headlines():
    """구글 뉴스 RSS를 활용한 주요 증시 뉴스 크롤링"""
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
    """Gemini AI를 이용한 실전 포트폴리오 추천 가이드"""
    prompt = f"""
    당신은 상위 1% VIP 자산가를 전담하는 세계 최고의 웰스매니저(PB)이자 AI 애널리스트입니다.
    아래의 [시장 데이터], [국내 인기 종목], [주요 뉴스]를 종합적으로 분석하여,
    오늘 아침 투자자에게 전달할 구체적이고 실전적인 포트폴리오 투자 전략을 제시해 주세요.

    [시장 데이터]: {market_data}
    [국내 인기 종목]: {popular_stocks}
    [주요 뉴스]: {news_data}

    반드시 아래 4가지 양식에 맞추어 전문적이고 명확하게 작성해 주세요 (마크다운 및 이모지 활용):
    
    1. 🎯 오늘의 투자 방향성 (현재 장세에 대한 짧고 굵은 한 줄 평)
    2. 📈 주식 전략 및 추천 (국내/해외 유망 섹터와 주목할 만한 관련 테마/종목 언급)
    3. 📊 ETF 투자 아이디어 (현재 장세에서 방어 또는 수익을 낼 수 있는 구체적인 ETF 상품 테마 추천. 예: 배당 ETF, 반도체 ETF 등)
    4. 🛡️ 연금 및 채권 전략 (안전자산 비중 조절 조언, 개인연금/퇴직연금(IRP) 계좌에서의 장기 투자 전략 및 채권 투자 매력도)
    """
    
    try:
        # 모델을 가장 안정적인 gemini-pro로 고정
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return f"\n🤖 [AI 웰스매니저의 실전 투자 가이드]\n{response.text}\n"
    except Exception as e:
        return f"\n🤖 [AI 분석 실패]: {e}\n"

def send_telegram_message(message):
    """텔레그램 발송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': message})

if __name__ == "__main__":
    tz_kr = pytz.timezone('Asia/Seoul')
    today = datetime.now(tz_kr).strftime("%Y년 %m월 %d일")
    
    # 데이터 수집
    market_report, market_data = get_market_data()
    popular_report, popular_stocks = get_naver_popular_stocks()
    news_report, news_data = get_news_headlines()
    
    # AI 분석 (시장 데이터, 네이버 인기 종목, 뉴스 종합 전달)
    ai_report = get_gemini_analysis(market_data, popular_stocks, news_data)
    
    # 최종 메시지 조립
    final_message = f"🌅 {today} 프리미엄 투자 브리핑\n\n"
    final_message += market_report
    final_message += popular_report
    final_message += news_report
    final_message += ai_report
    final_message += "\n오늘도 성공적인 투자 되세요! 🚀"
    
    send_telegram_message(final_message)
