from flask import Flask, request, jsonify
import datetime
import os 
from dotenv import load_dotenv
import sqlite3
import json

load_dotenv()
app = Flask(__name__)
DATABASE_NAME = 'osint_agi.db'
API_KEY_PIMEYES = os.getenv("PIMEYES_API_KEY")

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        event_type TEXT NOT NULL,
                        source_module TEXT,
                        target_subject_name TEXT,
                        query_details TEXT, -- Può contenere JSON con parametri di ricerca
                        result_summary TEXT, -- Breve riassunto del risultato o errore
                        notes TEXT
                    )
                ''')
    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_subject_name TEXT,
                        data_category TEXT, -- es. 'anagrafica', 'social_profile', 'contatto'
                        source_api TEXT, -- es. 'PimEyes', 'OpenSanctions', 'ScrapyAlboMedici'
                        reliability_score TEXT, -- A, B, C
                        retrieved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        content_json TEXT, -- JSON string del dato trovato
                        report_id INTEGER NULL -- Per collegare a un report specifico in futuro
                    )
                    ''')
    conn.commit()
    conn.close()
    print(f"Database '{DATABASE_NAME}' inizializzato")

# FUNZIONE SPOSTATA FUORI DA init_db() - QUESTO ERA IL PROBLEMA!
def log_audit_event(event_type, source_module=None, target_subject_name=None, query_details=None, result_summary=None, notes=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
                INSERT INTO audit_log (event_type, source_module, target_subject_name, query_details, result_summary, notes)
                VALUES (?, ?, ?, ?, ?, ?)
        ''', (event_type, source_module, target_subject_name, json.dumps(query_details) if query_details else None, result_summary, notes))
        conn.commit()
    except Exception as e:
        print(f"Errore durante il logging dell'audit event: {e}")
    finally:
        conn.close()

@app.route('/process_osint_data', methods=['POST'])
def process_osint_data():
    try:
        data = request.json
        print(f"[{datetime.datetime.now()}] Dati ricevuti da Make.com: {data}")
        
        nome = data.get('nome')
        cognome = data.get('cognome')
        subject_identifier = f"{nome} {cognome}".strip() if nome and cognome else "Soggetto Sconosciuto"
        
        log_audit_event(
            event_type="RICHIESTA_RICEVUTA_DA_MAKE",
            source_module="Make.com Webhook",
            target_subject_name=subject_identifier,
            query_details=data,
            result_summary="Dati di input ricevuti"
        )
        
        if not nome or not cognome:
            err_msg = "Nome e cognome sono richiesti"
            log_audit_event(
                event_type="ERRORE_INPUT", 
                target_subject_name=subject_identifier, 
                result_summary=err_msg  # era "result_summery" (typo)
            )
            return jsonify({"status": "errore", "message": err_msg}), 400
            
        print(f"Elaborazione per: {subject_identifier}")
        
        log_audit_event(
            event_type="INIZIO_ELABORAZIONE_SOGGETTO",
            source_module="receiver.py",
            target_subject_name=subject_identifier,
            notes="Avvio pipeline di analisi OSINT"
        )
        
        response_data = {  # era "response_date" (typo)
            "status": "successo",
            "message": f"Dati per {subject_identifier} ricevuti e pronti per l'elaborazione.",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        log_audit_event(
            event_type="RISPOSTA_INVIATA_A_MAKE",
            source_module="receiver.py",
            target_subject_name=subject_identifier,
            result_summary="Elaborazione iniziale completata, risposta OK."
        )
        
        return jsonify(response_data), 200
    
    except Exception as e:
        print(f"Errore durante l'elaborazione: {e}")
        log_audit_event(
            event_type="ERRORE_CRITICO_PROCESSO",
            source_module="receiver.py",
            result_summary=str(e)
        )
        return jsonify({"status": "errore", "message": str(e)}), 500

if __name__ == '__main__':
    init_db()  # Inizializza il DB all'avvio
    print("Avvio del server Flask sulla porta 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)