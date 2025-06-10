from flask import Flask, request, jsonify
import datetime
import os
from dotenv import load_dotenv
import sqlite3
import json
# Importa la funzione orchestratrice del modulo anagrafica
from modules.m1_anagrafica import get_identita_anagrafica  # <--- MODIFICATO IMPORT

load_dotenv()
app = Flask(__name__)

DATABASE_NAME = 'osint_agi.db'

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
            query_details TEXT,
            result_summary TEXT,
            notes TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_subject_name TEXT,
            data_category TEXT,
            source_api TEXT,
            reliability_score TEXT,
            retrieved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            content_json TEXT,
            report_id INTEGER NULL
        )
    ''')
    conn.commit()
    conn.close()
    print(f"Database '{DATABASE_NAME}' inizializzato.")

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

def save_result(target_subject_name, data_category, source_api, reliability_score, content_data):
    """Salva un risultato strutturato nel database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO results (target_subject_name, data_category, source_api, reliability_score, content_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (target_subject_name, data_category, source_api, reliability_score, json.dumps(content_data)))
        conn.commit()
        print(f"[DB] Salvato risultato da '{source_api}' per '{target_subject_name}' categoria '{data_category}'.")
    except Exception as e:
        print(f"Errore durante il salvataggio del risultato: {e}")
    finally:
        conn.close()

@app.route('/process_osint_data', methods=['POST'])
def process_osint_data():
    all_results = {}  # Dizionario per aggregare i risultati da tutti i moduli
    try:
        data = request.json
        print(f"[{datetime.datetime.now()}] Dati ricevuti da Make.com: {data}")
        
        nome = data.get('nome')
        cognome = data.get('cognome')
        # varianti = data.get('varianti')  # Per uso futuro
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
            log_audit_event(event_type="ERRORE_INPUT", target_subject_name=subject_identifier, result_summary=err_msg)
            return jsonify({"status": "errore", "message": err_msg, "raw_data_received": data}), 400
        
        print(f"Elaborazione per: {subject_identifier}")
        log_audit_event(
            event_type="INIZIO_ELABORAZIONE_SOGGETTO",
            source_module="receiver.py",
            target_subject_name=subject_identifier,
            notes="Avvio pipeline di analisi OSINT"
        )
        
        # --- MODULO M1: IDENTITÀ E ANAGRAFICA ---
        if nome and cognome:
            log_audit_event(
                event_type="AVVIO_MODULO",
                source_module="M1_Identita_Anagrafica",
                target_subject_name=subject_identifier,
                query_details={"nome": nome, "cognome": cognome}  # Aggiungere varianti se usate
            )
            
            # Chiama la funzione orchestratrice del modulo M1
            m1_results = get_identita_anagrafica(nome, cognome)  # Passare varianti se implementato
            all_results["m1_identita_anagrafica"] = m1_results
            
            log_audit_event(
                event_type="COMPLETAMENTO_MODULO",
                source_module="M1_Identita_Anagrafica",
                target_subject_name=subject_identifier,
                result_summary=f"Completato. Sanctions.network: {m1_results['sanctions_network'].get('count', 0)} | Google Dorks: {m1_results['google_dorks_anagrafica'].get('count', 0)}"
            )

            # Salva i risultati di Sanctions.network nel DB
            if m1_results["sanctions_network"]["status"] == "successo" and m1_results["sanctions_network"]["results"]:
                for res_item in m1_results["sanctions_network"]["results"]:
                    # Determina il punteggio di affidabilità basato su diversi fattori
                    reliability_score = "A"  # Default alta affidabilità
                    
                    # Logica per determinare l'affidabilità basata sui dati Sanctions.network
                    if res_item.get("match"):
                        if res_item.get("score", 0) > 0.8:
                            reliability_score = "A"  # Match forte con score alto
                        elif res_item.get("score", 0) > 0.5:
                            reliability_score = "B"  # Match buono
                        else:
                            reliability_score = "C"  # Match debole
                    else:
                        reliability_score = "C"  # Nessun match forte
                    
                    save_result(
                        target_subject_name=subject_identifier,
                        data_category="anagrafica_sanzioni",
                        source_api="Sanctions.network",  # <--- AGGIORNATO
                        reliability_score=reliability_score,
                        content_data=res_item
                    )

            # Salva i risultati dei Google Dorks nel DB
            # Questi sono URL, quindi l'affidabilità è C finché non vengono analizzati manualmente
            if m1_results["google_dorks_anagrafica"]["status"] == "successo" and m1_results["google_dorks_anagrafica"]["results"]:
                for res_item in m1_results["google_dorks_anagrafica"]["results"]:
                    if "url_found" in res_item:  # Salva solo se c'è un URL, non errori
                        save_result(
                            target_subject_name=subject_identifier,
                            data_category="anagrafica_google_dork_url",
                            source_api="GoogleDorks",
                            reliability_score="C",  # URL grezzo, richiede verifica
                            content_data=res_item  # Contiene dork_query e url_found
                        )
            
            # Log aggiuntivi per risultati vuoti o errori - Sanctions.network
            if m1_results["sanctions_network"]["status"] == "vuoto":
                log_audit_event(
                    event_type="RISULTATO_VUOTO",
                    source_module="M1_Sanctions_Network",
                    target_subject_name=subject_identifier,
                    result_summary="Nessun risultato trovato su Sanctions.network"
                )
            elif m1_results["sanctions_network"]["status"] == "errore":
                log_audit_event(
                    event_type="ERRORE_MODULO",
                    source_module="M1_Sanctions_Network",
                    target_subject_name=subject_identifier,
                    result_summary=f"Errore API: {m1_results['sanctions_network'].get('message', 'Errore sconosciuto')}"
                )
            
            # Log aggiuntivi per risultati vuoti o errori - Google Dorks
            if m1_results["google_dorks_anagrafica"]["status"] == "vuoto":
                log_audit_event(
                    event_type="RISULTATO_VUOTO",
                    source_module="M1_Google_Dorks",
                    target_subject_name=subject_identifier,
                    result_summary="Nessun URL trovato tramite Google Dorks"
                )
                
        # --- FINE MODULO M1 ---
        # Qui verranno aggiunte le chiamate ad altri moduli
        
        response_data = {
            "status": "successo",
            "message": f"Elaborazione per {subject_identifier} completata.",
            "timestamp": datetime.datetime.now().isoformat(),
            "aggregated_results": all_results  # Includi i risultati nella risposta a Make
        }
        
        log_audit_event(
            event_type="RISPOSTA_INVIATA_A_MAKE",
            source_module="receiver.py",
            target_subject_name=subject_identifier,
            result_summary="Elaborazione principale completata, risposta OK."
        )
        
        return jsonify(response_data), 200
        
    except Exception as e:
        # Cattura l'eccezione qui per loggare l'errore e restituire una risposta JSON
        error_message = f"Errore critico durante l'elaborazione: {str(e)}"
        print(error_message)
        
        # Assicurati che subject_identifier sia definito anche in caso di errore precoce
        subject_identifier_on_error = f"{data.get('nome', 'N/D')} {data.get('cognome', 'N/D')}".strip() if 'data' in locals() and isinstance(data, dict) else "Soggetto Sconosciuto"

        log_audit_event(
            event_type="ERRORE_CRITICO_PROCESSO",
            source_module="receiver.py",
            target_subject_name=subject_identifier_on_error,
            result_summary=error_message
        )
        
        return jsonify({
            "status": "errore", 
            "message": error_message, 
            "raw_data_received": data if 'data' in locals() else None
        }), 500

if __name__ == '__main__':
    init_db()
    print("Avvio del server Flask sulla porta 5000...")
    # host='0.0.0.0' per ngrok, debug=True per sviluppo
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)  # use_reloader=False se ngrok ha problemi con il riavvio
