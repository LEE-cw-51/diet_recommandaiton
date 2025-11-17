"""
프로젝트 설정 파일
"""

class Settings:
    # 영양성분 API (나중에 API 키 발급받으면 여기에 입력)
    NUTRITION_API_KEY = "your-api-key-here"
    
    # DB 설정 (MySQL 설치 후 사용)
    DB_HOST = "localhost"
    DB_USER = "root"
    DB_PASSWORD = ""
    DB_NAME = "diet_app"
    
    # 크롤링 설정
    CRAWL_DELAY = 1        # 페이지 요청 간격 (초)
    MAX_RETRIES = 3        # 실패 시 재시도 횟수
    HEADLESS = True        # True: 브라우저 숨김, False: 브라우저 보임
    
    # 데이터 저장 경로
    DATA_RAW = "data/raw"
    DATA_PROCESSED = "data/processed"
    DATA_TEST = "data/test"

# 전역 설정 객체
settings = Settings()