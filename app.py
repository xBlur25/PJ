# app.py
from flask import Flask, request, jsonify
import mysql.connector
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- Database Configuration ---
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'your_secure_password',  # !! REPLACE WITH YOUR MYSQL ROOT PASSWORD !!
    'database': 'minecraft_logs'
}

def get_db_connection():
    """Establishes and returns a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        return None

@app.route('/')
def index():
    return "Minecraft Player Data API is running!"

@app.route('/player/<username>', methods=['GET'])
def get_player_info(username):
    """Fetches general player information."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT username, first_seen, last_seen, is_banned, is_muted
            FROM players
            WHERE username = %s
        """, (username,))
        player_info = cursor.fetchone()

        if not player_info:
            return jsonify({"message": "Player not found"}), 404

        # Convert datetime objects to string for JSON serialization
        for key in ['first_seen', 'last_seen']:
            if player_info.get(key):
                player_info[key] = player_info[key].isoformat()

        return jsonify(player_info)

    except mysql.connector.Error as err:
        print(f"Error fetching player info for {username}: {err}")
        return jsonify({"error": "Database query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/player/<username>/chat', methods=['GET'])
def get_player_chat(username):
    """Fetches chat messages for a player."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT message, message_type, server_name, chat_timestamp
            FROM chat_messages
            WHERE username = %s
            ORDER BY chat_timestamp DESC
            LIMIT 100
        """, (username,))
        chat_messages = cursor.fetchall()

        for msg in chat_messages:
            if msg.get('chat_timestamp'):
                msg['chat_timestamp'] = msg['chat_timestamp'].isoformat()

        return jsonify(chat_messages)

    except mysql.connector.Error as err:
        print(f"Error fetching chat messages for {username}: {err}")
        return jsonify({"error": "Database query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/player/<username>/punishments', methods=['GET'])
def get_player_punishments(username):
    """Fetches punishment history for a player."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT punishment_type, duration, reason, punishment_timestamp, moderator_name
            FROM punishments
            WHERE username = %s
            ORDER BY punishment_timestamp DESC
        """, (username,))
        punishments = cursor.fetchall()

        for p in punishments:
            if p.get('punishment_timestamp'):
                p['punishment_timestamp'] = p['punishment_timestamp'].isoformat()

        return jsonify(punishments)

    except mysql.connector.Error as err:
        print(f"Error fetching punishments for {username}: {err}")
        return jsonify({"error": "Database query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/player/<username>/reports_against', methods=['GET'])
def get_player_reports_against(username):
    """Fetches reports made against a player."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT reporter_name, reason, server_name, report_timestamp
            FROM reports
            WHERE reported_name = %s
            ORDER BY report_timestamp DESC
        """, (username,))
        reports = cursor.fetchall()

        for r in reports:
            if r.get('report_timestamp'):
                r['report_timestamp'] = r['report_timestamp'].isoformat()

        return jsonify(reports)

    except mysql.connector.Error as err:
        print(f"Error fetching reports against {username}: {err}")
        return jsonify({"error": "Database query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/player/<username>/reports_by', methods=['GET'])
def get_player_reports_by(username):
    """Fetches reports made by a player."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT reported_name, reason, server_name, report_timestamp
            FROM reports
            WHERE reporter_name = %s
            ORDER BY report_timestamp DESC
        """, (username,))
        reports = cursor.fetchall()

        for r in reports:
            if r.get('report_timestamp'):
                r['report_timestamp'] = r['report_timestamp'].isoformat()

        return jsonify(reports)

    except mysql.connector.Error as err:
        print(f"Error fetching reports by {username}: {err}")
        return jsonify({"error": "Database query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/player/<username>/kills', methods=['GET'])
def get_player_kills(username):
    """Fetches kill history for a player."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT killer, killed, timestamp
            FROM kill_events
            WHERE killer = %s OR killed = %s
            ORDER BY timestamp DESC
        """, (username, username))
        kills = cursor.fetchall()
        
        for k in kills:
            if k.get('timestamp'):
                k['timestamp'] = k['timestamp'].isoformat()
        
        return jsonify(kills)
        
    except mysql.connector.Error as err:
        print(f"Error fetching kill history for {username}: {err}")
        return jsonify({"error": "Database query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()
        
@app.route('/debug/player/<username>', methods=['GET'])
def debug_player_status(username):
    """
    A debug endpoint to check the raw data from the database.
    This bypasses the front-end logic and shows what the Flask app is receiving.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    cursor = conn.cursor(dictionary=True)
    debug_info = {}
    try:
        # Check the 'players' table
        cursor.execute("SELECT is_banned, is_muted FROM players WHERE username = %s", (username,))
        players_table_status = cursor.fetchone()
        debug_info['players_table_status'] = players_table_status

        # Check the 'punishments' table for active punishments
        now = datetime.now()
        cursor.execute("""
            SELECT punishment_type, reason, duration, punishment_timestamp, expires_at
            FROM punishments
            WHERE username = %s AND (expires_at IS NULL OR expires_at > %s)
            ORDER BY punishment_timestamp DESC
        """, (username, now))
        active_punishments = cursor.fetchall()

        # Convert datetime objects to string
        for p in active_punishments:
            if p.get('punishment_timestamp'):
                p['punishment_timestamp'] = p['punishment_timestamp'].isoformat()
            if p.get('expires_at'):
                p['expires_at'] = p['expires_at'].isoformat()

        debug_info['active_punishments'] = active_punishments
        debug_info['now'] = now.isoformat()

        return jsonify(debug_info)

    except mysql.connector.Error as err:
        return jsonify({"error": "Debug query failed", "details": str(err)}), 500
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    # You can run this directly or with a production WSGI server like Gunicorn
    # For local testing:
    app.run(host='0.0.0.0', port=5000, debug=True)
