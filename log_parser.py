# filename: log_parser.py

import os
import re
import mysql.connector
import logging
import time
from datetime import datetime, timedelta

# --- Configuration ---
# Update these with your MySQL connection details
MYSQL_HOST = "localhost"
MYSQL_USER = "root"
# IMPORTANT: Replace "your_secure_password" with your actual MySQL root password.
MYSQL_PASSWORD = "your_secure_password"
# The full path to your server log file
LOG_FILE_PATH = r"C:\Users\xBlur\AppData\Roaming\norisk\NoRiskClientV3\data\profiles\1.8.9\logs\latest.log"
# The interval (in seconds) to check for new log entries
POLLING_INTERVAL = 5

# --- Logging Setup ---
# Configure logging to write to a file, so you can check it for errors later.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='log_parser.log',
    filemode='a'
)
logging.info("--- Starting new session ---")

# --- Database Functions ---

def create_database(db_config):
    """
    Attempts to connect to the MySQL server and creates the 'minecraft_logs' database
    if it does not already exist.
    """
    db_name = "minecraft_logs"
    print(f"Connecting to MySQL server to create database '{db_name}'...")
    try:
        conn = mysql.connector.connect(
            host=db_config["host"],
            user=db_config["user"],
            password=db_config["password"]
        )
        cursor = conn.cursor()
        logging.info("Connected to MySQL server to create database.")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        logging.info(f"Database '{db_name}' ensured to exist.")
        print(f"Database '{db_name}' ensured to exist.")
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        logging.error(f"Error creating database: {err}")
        print(f"Error creating database: {err}")
        return False
    return True

def get_db_connection():
    """
    Establishes a database connection. If the 'minecraft_logs' database does not exist,
    it attempts to create it first.
    """
    db_config = {
        "host": MYSQL_HOST,
        "user": MYSQL_USER,
        "password": MYSQL_PASSWORD,
        "database": "minecraft_logs"
    }
    try:
        conn = mysql.connector.connect(**db_config)
        logging.info("Successfully connected to database 'minecraft_logs'.")
        print("Successfully connected to database 'minecraft_logs'.")
        return conn
    except mysql.connector.errors.DatabaseError as err:
        if err.errno == 1049:  # Error 1049: Unknown database
            logging.warning("Database 'minecraft_logs' not found. Attempting to create it.")
            print("Database 'minecraft_logs' not found. Attempting to create it.")
            if create_database(db_config):
                conn = mysql.connector.connect(**db_config)
                logging.info("Successfully connected to the newly created database.")
                print("Successfully connected to the newly created database.")
                return conn
            else:
                logging.error("Failed to create the database. Exiting.")
                print("Failed to create the database. Exiting.")
                return None
        else:
            logging.error(f"Error connecting to MySQL: {err}")
            print(f"Error connecting to MySQL: {err}")
            return None
    except mysql.connector.Error as err:
        logging.error(f"Error connecting to MySQL: {err}")
        print(f"Error connecting to MySQL: {err}")
        return None

def create_tables(conn):
    """
    Creates all necessary tables that match the Flask API expectations.
    """
    try:
        cursor = conn.cursor()
        logging.info("Checking and creating tables...")
        print("Checking and creating tables...")

        # Table schemas that match your Flask API
        tables = {
            "players": """
                CREATE TABLE IF NOT EXISTS players (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE,
                    first_seen DATETIME,
                    last_seen DATETIME,
                    is_banned BOOLEAN DEFAULT FALSE,
                    is_muted BOOLEAN DEFAULT FALSE,
                    INDEX idx_username (username)
                )
            """,
            "chat_messages": """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255),
                    message TEXT,
                    message_type ENUM('normal', 'swear_filtered', 'advertise_filtered') DEFAULT 'normal',
                    server_name VARCHAR(255),
                    chat_timestamp DATETIME,
                    INDEX idx_username (username),
                    INDEX idx_timestamp (chat_timestamp)
                )
            """,
            "punishments": """
                CREATE TABLE IF NOT EXISTS punishments (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255),
                    punishment_type ENUM('Ban', 'Mute'),
                    duration VARCHAR(255),
                    reason TEXT,
                    moderator_name VARCHAR(255),
                    punishment_timestamp DATETIME,
                    expires_at DATETIME,
                    INDEX idx_username (username),
                    INDEX idx_timestamp (punishment_timestamp)
                )
            """,
            "reports": """
                CREATE TABLE IF NOT EXISTS reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    reporter_name VARCHAR(255),
                    reported_name VARCHAR(255),
                    reason TEXT,
                    server_name VARCHAR(255),
                    report_timestamp DATETIME,
                    INDEX idx_reporter (reporter_name),
                    INDEX idx_reported (reported_name),
                    INDEX idx_timestamp (report_timestamp)
                )
            """,
            "kill_events": """
                CREATE TABLE IF NOT EXISTS kill_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    killer VARCHAR(255),
                    killed VARCHAR(255),
                    timestamp DATETIME,
                    INDEX idx_killer (killer),
                    INDEX idx_killed (killed),
                    INDEX idx_timestamp (timestamp)
                )
            """
        }

        for table_name, table_sql in tables.items():
            cursor.execute(table_sql)
            logging.info(f"Table '{table_name}' checked/created successfully.")
            print(f"Table '{table_name}' checked/created successfully.")
        
        conn.commit()
        cursor.close()
    except mysql.connector.Error as err:
        logging.error(f"Error creating tables: {err}")
        print(f"Error creating tables: {err}")

def update_player_status(conn, username):
    """
    Updates or inserts a player in the players table and updates their status.
    """
    cursor = conn.cursor()
    now = datetime.now()
    
    try:
        # Check if player exists
        cursor.execute("SELECT id, first_seen FROM players WHERE username = %s", (username,))
        player = cursor.fetchone()
        cursor.fetchall()  # Consume any remaining results
        
        if player:
            # Update existing player
            cursor.execute("""
                UPDATE players 
                SET last_seen = %s 
                WHERE username = %s
            """, (now, username))
        else:
            # Insert new player
            cursor.execute("""
                INSERT INTO players (username, first_seen, last_seen, is_banned, is_muted) 
                VALUES (%s, %s, %s, FALSE, FALSE)
            """, (username, now, now))
        
        # Update ban/mute status based on active punishments
        cursor.execute("""
            SELECT punishment_type FROM punishments 
            WHERE username = %s AND (expires_at IS NULL OR expires_at > %s)
        """, (username, now))
        
        active_punishments = cursor.fetchall()
        is_banned = any(p[0] == 'Ban' for p in active_punishments)
        is_muted = any(p[0] == 'Mute' for p in active_punishments)
        
        cursor.execute("""
            UPDATE players 
            SET is_banned = %s, is_muted = %s 
            WHERE username = %s
        """, (is_banned, is_muted, username))
        
        conn.commit()
        
    except mysql.connector.Error as err:
        logging.error(f"Error updating player status for {username}: {err}")
        print(f"DB Error updating player: {err}")
    finally:
        cursor.close()

def parse_duration_to_datetime(duration_str, base_time):
    """
    Parse duration strings like '7d', '1h', '30m', 'permanent' into datetime objects.
    Returns None for permanent bans/mutes.
    """
    if not duration_str or duration_str.lower() in ['permanent', 'perm', 'forever']:
        return None
    
    duration_str = duration_str.lower().strip()
    
    # Extract number and unit
    import re
    match = re.match(r'(\d+)([dhms])', duration_str)
    if not match:
        return None
    
    amount, unit = match.groups()
    amount = int(amount)
    
    if unit == 'd':  # days
        return base_time + timedelta(days=amount)
    elif unit == 'h':  # hours
        return base_time + timedelta(hours=amount)
    elif unit == 'm':  # minutes
        return base_time + timedelta(minutes=amount)
    elif unit == 's':  # seconds
        return base_time + timedelta(seconds=amount)
    
    return None

def check_duplicate_and_insert(conn, table, check_conditions, insert_query, insert_params, log_message):
    """
    Helper function to check for duplicates and insert if not exists.
    Returns True if inserted, False if duplicate found.
    """
    cursor = conn.cursor()
    try:
        # Build the duplicate check query
        where_clause = " AND ".join([f"{col} = %s" for col in check_conditions.keys()])
        check_query = f"SELECT id FROM {table} WHERE {where_clause}"
        
        cursor.execute(check_query, tuple(check_conditions.values()))
        result = cursor.fetchone()
        cursor.fetchall()  # Consume any remaining results
        
        if result:
            print(f"LOG: Duplicate {table} entry skipped - {log_message}")
            return False
        else:
            cursor.execute(insert_query, insert_params)
            conn.commit()
            logging.info(f"Inserted {table.upper()}: {log_message}")
            print(f"LOG: New {table} - {log_message}")
            return True
            
    except mysql.connector.Error as err:
        logging.error(f"Error in check_duplicate_and_insert for {table}: {err}")
        print(f"DB Error in {table}: {err}")
        return False
    finally:
        cursor.close()

def tail_log_file_and_insert_data(conn, log_file_path):
    """
    Continuously tails the log file, processes new lines, and inserts data into the database.
    """
    try:
        if not os.path.exists(log_file_path):
            logging.error(f"Log file not found at: {log_file_path}")
            print(f"Error: Log file not found at: {log_file_path}")
            return

        # Regex patterns for parsing log messages
        # Ban: "? Banned ? <user> has been banned <duration> for <reason>."
        ban_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Client thread/INFO\]: \[CHAT\] \? Banned \? (.+?) has been banned (.+?) for (.+?)\.")
        
        # Mute: "? Muted ? <user> has been muted <duration> for <reason>."
        mute_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Client thread/INFO\]: \[CHAT\] \? Muted \? (.+?) has been muted (.+?) for (.+?)\.")
        
        # Report: "? Report ? <user> reported <user> for <reason> in <server>."
        report_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Client thread/INFO\]: \[CHAT\] \? Report \? (.+?) reported (.+?) for (.+?) in (.+?)\.")
        
        # Chat filter - swears: "<user> swears in <server>: <message>"
        chat_swear_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Server thread/INFO\]: (.+?) swears in (.+?): (.+)")
        
        # Chat filter - advertise: "<user> possibly advertises in <server>: <message>"
        chat_advertise_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Server thread/INFO\]: (.+?) possibly advertises in (.+?): (.+)")
        
        # Normal chat: "<user> » <message>" (also through Client thread/CHAT)  
        # The » character appears as � due to encoding issues
        chat_normal_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Client thread/INFO\]: \[CHAT\] (.+?) � (.+)")
        
        # Kill events: "<user> was killed by <user>"
        kill_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2})\] \[Server thread/INFO\]: (.+?) was killed by (.+)")

        logging.info(f"Tailing log file at {log_file_path}...")
        print(f"Tailing log file at {log_file_path}...")
        
        with open(log_file_path, 'r', encoding='utf-8', errors='replace') as f:
            # For testing: start from beginning to process existing entries
            # Change to f.seek(0, os.SEEK_END) for production (only new entries)
            f.seek(0, os.SEEK_SET)  # Start from beginning for testing
            
            while True:
                # Check current position and file size
                current_pos = f.tell()
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
                if current_pos >= file_size:
                    # No new data, wait and check again
                    time.sleep(POLLING_INTERVAL)
                    continue
                
                # Go back to where we were and read new lines
                f.seek(current_pos)
                line = f.readline()
                
                if not line:
                    time.sleep(POLLING_INTERVAL)
                    continue
                
                print(f"DEBUG: New line detected: {line.strip()}")
                
                line = line.strip()
                if not line:
                    continue
                
                # Get current date for timestamp
                log_date_str = datetime.now().strftime("%Y-%m-%d")
                line_matched = False
                
                try:
                    # Check for ban
                    ban_match = ban_pattern.search(line)
                    if ban_match:
                        print(f"DEBUG: Match: Ban - {ban_match.groups()}")
                        line_matched = True
                        log_time_str, username, duration, reason = ban_match.groups()
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        expires_at = parse_duration_to_datetime(duration, timestamp)
                        
                        check_conditions = {
                            'username': username,
                            'punishment_type': 'Ban',
                            'punishment_timestamp': timestamp,
                            'reason': reason
                        }
                        insert_query = """
                            INSERT INTO punishments (username, punishment_type, duration, reason, punishment_timestamp, expires_at) 
                            VALUES (%s, 'Ban', %s, %s, %s, %s)
                        """
                        insert_params = (username, duration, reason, timestamp, expires_at)
                        
                        if check_duplicate_and_insert(conn, 'punishments', check_conditions, insert_query, insert_params, f"{username} banned for {duration}"):
                            update_player_status(conn, username)

                    # Check for mute
                    mute_match = mute_pattern.search(line)
                    if mute_match:
                        print(f"DEBUG: Match: Mute - {mute_match.groups()}")
                        line_matched = True
                        log_time_str, username, duration, reason = mute_match.groups()
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        expires_at = parse_duration_to_datetime(duration, timestamp)
                        
                        check_conditions = {
                            'username': username,
                            'punishment_type': 'Mute',
                            'punishment_timestamp': timestamp,
                            'reason': reason
                        }
                        insert_query = """
                            INSERT INTO punishments (username, punishment_type, duration, reason, punishment_timestamp, expires_at) 
                            VALUES (%s, 'Mute', %s, %s, %s, %s)
                        """
                        insert_params = (username, duration, reason, timestamp, expires_at)
                        
                        if check_duplicate_and_insert(conn, 'punishments', check_conditions, insert_query, insert_params, f"{username} muted for {duration}"):
                            update_player_status(conn, username)

                    # Check for report
                    report_match = report_pattern.search(line)
                    if report_match:
                        print(f"DEBUG: Match: Report - {report_match.groups()}")
                        line_matched = True
                        log_time_str, reporter, reported, reason, server = report_match.groups()
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        
                        check_conditions = {
                            'reporter_name': reporter,
                            'reported_name': reported,
                            'report_timestamp': timestamp,
                            'reason': reason
                        }
                        insert_query = """
                            INSERT INTO reports (reporter_name, reported_name, reason, server_name, report_timestamp) 
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        insert_params = (reporter, reported, reason, server, timestamp)
                        
                        if check_duplicate_and_insert(conn, 'reports', check_conditions, insert_query, insert_params, f"{reporter} reported {reported}"):
                            update_player_status(conn, reporter)
                            update_player_status(conn, reported)

                    # Check for filtered chat (swear)
                    chat_swear_match = chat_swear_pattern.search(line)
                    if chat_swear_match:
                        print(f"DEBUG: Match: Chat (swear) - {chat_swear_match.groups()}")
                        line_matched = True
                        log_time_str, username, server, message = chat_swear_match.groups()
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        
                        check_conditions = {
                            'username': username,
                            'chat_timestamp': timestamp,
                            'message': message,
                            'message_type': 'swear_filtered'
                        }
                        insert_query = """
                            INSERT INTO chat_messages (username, message, message_type, server_name, chat_timestamp) 
                            VALUES (%s, %s, 'swear_filtered', %s, %s)
                        """
                        insert_params = (username, message, server, timestamp)
                        
                        if check_duplicate_and_insert(conn, 'chat_messages', check_conditions, insert_query, insert_params, f"swear filtered - {username}"):
                            update_player_status(conn, username)

                    # Check for filtered chat (advertise)
                    chat_advertise_match = chat_advertise_pattern.search(line)
                    if chat_advertise_match:
                        print(f"DEBUG: Match: Chat (advertise) - {chat_advertise_match.groups()}")
                        line_matched = True
                        log_time_str, username, server, message = chat_advertise_match.groups()
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        
                        check_conditions = {
                            'username': username,
                            'chat_timestamp': timestamp,
                            'message': message,
                            'message_type': 'advertise_filtered'
                        }
                        insert_query = """
                            INSERT INTO chat_messages (username, message, message_type, server_name, chat_timestamp) 
                            VALUES (%s, %s, 'advertise_filtered', %s, %s)
                        """
                        insert_params = (username, message, server, timestamp)
                        
                        if check_duplicate_and_insert(conn, 'chat_messages', check_conditions, insert_query, insert_params, f"advertise filtered - {username}"):
                            update_player_status(conn, username)

                    # Check for normal chat
                    chat_normal_match = chat_normal_pattern.search(line)
                    if chat_normal_match:
                        print(f"DEBUG: Match: Chat (normal) - {chat_normal_match.groups()}")
                        line_matched = True
                        log_time_str, username, message = chat_normal_match.groups()
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        
                        check_conditions = {
                            'username': username,
                            'chat_timestamp': timestamp,
                            'message': message,
                            'message_type': 'normal'
                        }
                        insert_query = """
                            INSERT INTO chat_messages (username, message, message_type, server_name, chat_timestamp) 
                            VALUES (%s, %s, 'normal', NULL, %s)
                        """
                        insert_params = (username, message, timestamp)
                        
                        if check_duplicate_and_insert(conn, 'chat_messages', check_conditions, insert_query, insert_params, f"chat - {username}"):
                            update_player_status(conn, username)

                    # Check for kills (optional)
                    kill_match = kill_pattern.search(line)
                    if kill_match:
                        print(f"DEBUG: Match: Kill - {kill_match.groups()}")
                        line_matched = True
                        log_time_str, killed, killer = kill_match.groups()  # killed comes first, killer second
                        timestamp = datetime.strptime(f"{log_date_str} {log_time_str}", "%Y-%m-%d %H:%M:%S")
                        
                        check_conditions = {
                            'killer': killer,
                            'killed': killed,
                            'timestamp': timestamp
                        }
                        insert_query = """
                            INSERT INTO kill_events (killer, killed, timestamp) 
                            VALUES (%s, %s, %s)
                        """
                        insert_params = (killer, killed, timestamp)
                        
                        if check_duplicate_and_insert(conn, 'kill_events', check_conditions, insert_query, insert_params, f"{killer} killed {killed}"):
                            update_player_status(conn, killer)
                            update_player_status(conn, killed)
                    
                    # If no patterns matched
                    if not line_matched:
                        print("DEBUG: No Match")

                except Exception as e:
                    logging.error(f"Error processing line: {e}")
                    print(f"Processing error: {e}")
                    
    except Exception as e:
        logging.error(f"An unexpected error occurred during log parsing: {e}")
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    print("Starting continuous log file parser...")
    logging.info("Starting continuous log file parser...")
    conn = get_db_connection()
    if conn:
        create_tables(conn)
        tail_log_file_and_insert_data(conn, LOG_FILE_PATH)
        conn.close()
        print("Database connection closed.")
    else:
        logging.error("Failed to establish a database connection. Exiting.")
        print("Failed to establish a database connection. Exiting.")