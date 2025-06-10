import requests
import json
import datetime
import time  # Per pause tra le richieste
from googlesearch import search  # <--- NUOVO IMPORT per Google Dorks

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
                sanction_info = {
                    "id": result.get("id", f"sn-{result.get('names', ['unknown'])[0] if result.get('names') else 'unknown'}"),
                    "caption": result.get("names", [query])[0] if result.get("names") else query,
                    "schema": result.get("type", "Unknown").capitalize(),
                    "datasets": [result.get("source")] if result.get("source") else [],
                    "referents": [],
                    "score": result.get("score", 0),
                    "match": True
                }

                # Estrai proprietà più dettagliate se disponibili
                if sanction_info["schema"] == "Individual":
                    sanction_info["birth_date"] = [result.get("birth_date")] if result.get("birth_date") else []
                    sanction_info["nationality"] = [result.get("nationality")] if result.get("nationality") else []
                    sanction_info["summary"] = result.get("summary", None)
                    sanction_info["position"] = [result.get("position")] if result.get("position") else []
                    sanction_info["alias"] = result.get("aliases", []) if result.get("aliases") else []

                results_list.append(sanction_info)

            print(f"[Sanctions.network] Trovati {len(results_list)} risultati per: {query}")
            return {
                "status": "successo",
                "query": query,
                "count": len(results_list),
                "results": results_list,
                "raw_response": raw_response_data
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

def search_google_dorks_anagrafica(nome, cognome, num_results=5, lang='it'):
    """
    Esegue ricerche Google mirate per informazioni anagrafiche.
    """
    query_base = f'"{nome} {cognome}"'  # Cerca la frase esatta
    dorks = [
        f'{query_base} "nato il"',
        f'{query_base} "data di nascita"',
        f'{query_base} "luogo di nascita"',
        f'{query_base} "born on"',
        f'{query_base} "date of birth"',
        f'{query_base} "place of birth"'
    ]

    all_dork_results = []
    print(f"[GoogleDorks] Inizio ricerca anagrafica per: {nome} {cognome}")
    for dork in dorks:
        print(f"[GoogleDorks] Esecuzione dork: {dork}")
        try:
            search_results = list(search(dork, num_results=num_results, lang=lang, sleep_interval=2.5))

            for url in search_results:
                all_dork_results.append({
                    "dork_query": dork,
                    "url_found": url
                })
            time.sleep(1)  # Pausa aggiuntiva tra i dork per essere gentili
        except Exception as e:
            print(f"[GoogleDorks] Errore durante l'esecuzione del dork '{dork}': {e}")
            all_dork_results.append({
                "dork_query": dork,
                "error": str(e)
            })

    if all_dork_results:
        print(f"[GoogleDorks] Trovati {len(all_dork_results)} potenziali URL per: {nome} {cognome}")
        return {
            "status": "successo",
            "query": f"{nome} {cognome}",
            "count": len(all_dork_results),
            "results": all_dork_results
        }
    else:
        print(f"[GoogleDorks] Nessun URL trovato per: {nome} {cognome}")
        return {"status": "vuoto", "query": f"{nome} {cognome}", "message": "Nessun URL trovato tramite Google Dorks.", "results": []}

# Funzione combinata per il modulo M1
def get_identita_anagrafica(nome, cognome, varianti=None):
    """
    Funzione principale del modulo M1 per raccogliere dati anagrafici.
    Al momento combina Sanctions.network e Google Dorks.
    'varianti' non è ancora usato ma è previsto.
    """
    print(f"[M1_Anagrafica] Avvio modulo per: {nome} {cognome}")

    main_name_query = f"{nome} {cognome}".strip()

    results = {
        "sanctions_network": {},
        "google_dorks_anagrafica": {}
    }
    
    # 1. Sanctions.network
    print(f"[M1_Anagrafica] Chiamata a Sanctions.network per '{main_name_query}'")
    results["sanctions_network"] = search_opensanctions(nome, cognome)

    # 2. Google Dorks Anagrafica
    print(f"[M1_Anagrafica] Chiamata a Google Dorks per '{main_name_query}'")
    results["google_dorks_anagrafica"] = search_google_dorks_anagrafica(nome, cognome)
    
    return results

if __name__ == '__main__':
    print("Test del modulo M1 Anagrafica Combinato...")
    
    # Test con un individuo sanzionato noto (es. da liste OFAC o ONU)
    # test_subject_nome = "Viktor"
    # test_subject_cognome = "Yanukovych"
    test_subject_nome = "Mario"  # Test con nome comune
    test_subject_cognome = "Rossi"
    
    # Chiamata alla funzione combinata
    anagrafica_data = get_identita_anagrafica(test_subject_nome, test_subject_cognome)
    
    print("\n--- Risultati Sanctions.network ---")
    if anagrafica_data["sanctions_network"]["status"] == "successo":
        print(f"Trovati {anagrafica_data['sanctions_network']['count']} risultati per '{anagrafica_data['sanctions_network']['query']}'")
        for res in anagrafica_data["sanctions_network"]["results"]:
            print(f" ID: {res.get('id')}, Caption: {res.get('caption')}, Source: {res.get('datasets')}, Score: {res.get('score')}")
            if "birth_date" in res and res["birth_date"]:
                print(f" Date di Nascita: {', '.join(res['birth_date'])}")
            if "nationality" in res and res["nationality"]:
                print(f" Nazionalità: {', '.join(res['nationality'])}")
            if "alias" in res and res["alias"]:
                print(f" Alias: {res['alias']}")
            print("-" * 20)
    else:
        print(f"Sanctions.network status: {anagrafica_data['sanctions_network']['status']} - {anagrafica_data['sanctions_network'].get('message')}")
    
    print("\n--- Risultati Google Dorks Anagrafica ---")
    if anagrafica_data["google_dorks_anagrafica"]["status"] == "successo":
        print(f"Trovati {anagrafica_data['google_dorks_anagrafica']['count']} URL per '{anagrafica_data['google_dorks_anagrafica']['query']}'")
        for res in anagrafica_data["google_dorks_anagrafica"]["results"]:
            if "url_found" in res:
                print(f" Dork: '{res['dork_query']}' -> URL: {res['url_found']}")
            elif "error" in res:
                print(f" Dork: '{res['dork_query']}' -> Errore: {res['error']}")
    else:
        print(f"Google Dorks status: {anagrafica_data['google_dorks_anagrafica']['status']} - {anagrafica_data['google_dorks_anagrafica'].get('message')}")

