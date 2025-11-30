import sqlite3
import os

# 데이터베이스 파일 경로 설정
DB_DIR = 'database'
DB_FILE = 'nutrition_data.db'
DB_PATH = os.path.join(DB_DIR, DB_FILE)

def create_connection(db_path=DB_PATH):
    """지정된 경로에 SQLite 데이터베이스 연결을 생성하고 반환합니다."""
    try:
        # DB 파일이 없으면 생성
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.Error as e:
        print(f"❌ 데이터베이스 연결 오류: {e}")
        return None

def create_tables(conn):
    """
    Menu_Master와 Ingredients_Parsed 테이블을 생성합니다.
    Menu_Master에 'allergens_scraped' 컬럼이 추가되었습니다.
    """
    cursor = conn.cursor()

    # 1. Menu_Master 테이블 생성 (알레르기 유발 재료 컬럼 추가)
    master_table_ddl = """
    CREATE TABLE IF NOT EXISTS Menu_Master (
        menu_id TEXT PRIMARY KEY,
        store_name TEXT NOT NULL,
        menu_name TEXT NOT NULL,
        price INTEGER NOT NULL,
        
        -- 필수 영양 성분 9가지
        calories REAL DEFAULT 0,
        carbs REAL DEFAULT 0,
        sugars REAL DEFAULT 0,
        protein REAL DEFAULT 0,
        fat REAL DEFAULT 0,
        saturated_fat REAL DEFAULT 0,
        trans_fat REAL DEFAULT 0,
        cholesterol REAL DEFAULT 0,
        sodium REAL DEFAULT 0,
        
        ingredients_raw TEXT DEFAULT '',
        allergens_scraped TEXT DEFAULT '', -- [NEW] 크롤링된 알레르기 유발 재료 목록 (예: "밀, 대두")
        category TEXT
    );
    """
    cursor.execute(master_table_ddl)
    print("✅ 'Menu_Master' 테이블 준비 완료 (allergens_scraped 컬럼 포함)")
    
    # 2. Ingredients_Parsed 테이블 생성 (기존 유지 - LLM/다양성 분석용)
    parsed_table_ddl = """
    CREATE TABLE IF NOT EXISTS Ingredients_Parsed (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        menu_id TEXT,
        std_ingredient TEXT NOT NULL,
        is_allergen INTEGER DEFAULT 0,
        category_tag TEXT,
        FOREIGN KEY (menu_id) REFERENCES Menu_Master(menu_id)
    );
    """
    cursor.execute(parsed_table_ddl)
    print("✅ 'Ingredients_Parsed' 테이블 준비 완료")
    
    conn.commit()

if __name__ == '__main__':
    # 1. database 폴더가 없으면 생성
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    # 2. DB 연결 및 테이블 생성 실행
    conn = create_connection()
    if conn:
        create_tables(conn)
        conn.close()
        print(f"\n🎉 데이터베이스 파일 '{DB_PATH}'가 성공적으로 생성되었습니다!")