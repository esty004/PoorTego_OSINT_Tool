import requests
import json
import datetime

# Endpoint API aggiornato per la ricerca fuzzy di Sanctions.network
OPEN_SANCTIONS_API_URL = "https://api.sanctions.network/rpc/search_sanctions"

def search_opensanctions(nome, cognome):
    """
    Cerca un soggetto su Sanctions.network, adattando la risposta al formato originale.
    """
    query = f"{nome} {cognome}".strip()
    if not query:
        return {"status": "errore", "message": "Nome e cognome non possono essere vuoti.", "results": []}

    params = {
        "name": query,
        "limit": 5,  # Limita il numero di risultati
        # Considera di aggiungere il parametro 'select' se i campi specifici sono costantemente necessari
        # es. "select": "id,names,source,birth_date,nationality,aliases,summary,position,type"
    }

    results_list = []
    raw_response_data = None
    try:
        print(f"[Sanctions.network] Inizio ricerca per: {query}")
        response = requests.get(OPEN_SANCTIONS_API_URL, params=params, timeout=15)
        response.raise_for_status()  # Solleva un'eccezione per errori HTTP (4xx o 5xx)

        raw_response_data = response.json()

        # Sanctions.network restituisce un elenco di dizionari direttamente se ha successo
        if raw_response_data and isinstance(raw_response_data, list):
            for result in raw_response_data:
                # Mappa i campi di Sanctions.network alla struttura originale simile a OpenSanctions
                # Nota: la disponibilità dei campi e i nomi esatti potrebbero richiedere test sull'API effettiva
                # e potenzialmente l'uso del parametro 'select' per coerenza.
                sanction_info = {
                    "id": result.get("id", f"sn-{result.get('names', ['unknown'])[0] if result.get('names') else 'unknown'}"),  # Usa il loro ID o generane uno
                    "caption": result.get("names", [query])[0] if result.get("names") else query,  # Usa il primo nome da 'names' come didascalia
                    "schema": result.get("type", "Unknown").capitalize(),  # 'type' potrebbe essere 'individual', 'entity'
                    "datasets": [result.get("source")] if result.get("source") else [],  # 'source' è tipicamente una stringa come 'ofac', 'unsc', 'eu'
                    "referents": [],  # Sanctions.network non sembra avere un equivalente diretto per 'referents'
                    "score": result.get("score", 0),  # Assumendo che un campo score possa esistere, predefinito a 0
                    "match": True  # Per ora, assumi che qualsiasi risultato restituito sia una corrispondenza
                }

                # Estrai proprietà più dettagliate se disponibili
                if sanction_info["schema"] == "Individual":  # Controlla in base al 'type' da Sanctions.network
                    sanction_info["birth_date"] = [result.get("birth_date")] if result.get("birth_date") else []
                    sanction_info["nationality"] = [result.get("nationality")] if result.get("nationality") else []
                    sanction_info["summary"] = result.get("summary", None)  # Se disponibile
                    sanction_info["position"] = [result.get("position")] if result.get("position") else []  # Se disponibile
                    sanction_info["alias"] = result.get("aliases", [])  # Assumendo il campo 'aliases' per altri nomi

                results_list.append(sanction_info)

            print(f"[Sanctions.network] Trovati {len(results_list)} risultati per: {query}")
            return {
                "status": "successo",
                "query": query,
                "count": len(results_list),
                "results": results_list,
                "raw_response": raw_response_data  # Utile per il debug o analisi più approfondite
            }
        else:
            print(f"[Sanctions.network] Nessun risultato o formato risposta inatteso per: {query}")
            return {"status": "vuoto", "query": query, "message": "Nessun risultato trovato o formato risposta inatteso.", "results": []}
    except requests.exceptions.RequestException as e:
        print(f"[Sanctions.network] Errore API per {query}: {e}")
        return {"status": "errore", "query": query, "message": str(e), "results": []}
    except Exception as e:
        print(f"[Sanctions.network] Errore generico durante la ricerca per {query}: {e}")
        return {"status": "errore", "query": query, "message": f"Errore generico: {str(e)}", "results": []}

if __name__ == '__main__':
    print("Test del modulo Sanctions.network...")
    # Test con un individuo sanzionato noto (es. da liste OFAC o ONU)
    test_results = search_opensanctions("Viktor", "Yanukovych")
    # test_results = search_opensanctions("Mario", "Rossi")  # Per un caso senza risultati

    if test_results["status"] == "successo":
        print(f"Risultati per '{test_results['query']}':")
        for res in test_results["results"]:
            print(f" ID: {res.get('id')}, Caption: {res.get('caption')}, Source: {res.get('datasets')}, Score: {res.get('score')}")
            if "birth_date" in res and res["birth_date"]:
                print(f" Date di Nascita: {', '.join(res['birth_date'])}")
            if "nationality" in res and res["nationality"]:
                print(f" Nazionalità: {', '.join(res['nationality'])}")
            if "alias" in res and res["alias"]:
                print(f" Alias: {res['alias']}")
            print("-" * 20)
    elif test_results["status"] == "errore":
        print(f"Errore: {test_results['message']}")
    else:
        print(f"Nessun risultato per '{test_results['query']}' o altro status: {test_results['status']}")