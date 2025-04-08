import requests
import pandas as pd
import math
import re  # Utilisé pour détecter des valeurs numériques associées au volume de distribution
import streamlit as st

def construct_query_with_keywords(user_keywords, pharmacometry_keywords):
    """
    Construit une requête PubMed avec des mots-clés obligatoires (donnés par l'utilisateur à 100%)
    et des mots-clés pharmacométriques préférentiels.
    """
    # Mots-clés obligatoires donnés par l'utilisateur
    user_query = " AND ".join(user_keywords)

    # Mots-clés pharmacométriques ajoutés avec OR pour plus de flexibilité
    pharmacometry_query = " OR ".join(pharmacometry_keywords)

    # Construction de la requête enrichie
    enriched_query = f"({user_query}) AND ({pharmacometry_query})"
    return enriched_query

def search_pubmed(query, max_results=200):
    """
    Recherche des articles sur PubMed via l'API Entrez.
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except requests.exceptions.JSONDecodeError:
        st.error("La réponse de l'API PubMed n'est pas au format JSON. Vérifiez votre requête.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête à l'API PubMed : {str(e)}")
        return []

def fetch_article_details(pubmed_ids):
    """
    Récupération des détails des articles à partir de leurs PubMed IDs.
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pubmed_ids),
        "retmode": "json",
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        articles = []
        for id, details in data.get("result", {}).items():
            if id == "uids":  # Clé inutilisée
                continue
            article = {
                "Journal": details.get("source", "Non spécifié"),
                "Date de publication": details.get("pubdate", "Non spécifié"),
                "Titre": details.get("title", "Non spécifié"),
                "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
                "Résumé": details.get("title", "Non spécifié"),
                "Type de modèle": determine_model_type(details.get("title", ""), details.get("title", "")),
                "Volume de distribution détecté": detect_distribution_volume(details.get("title", "")),
            }
            # Inclure uniquement les articles mentionnant un volume de distribution
            if article["Volume de distribution détecté"] == "Oui":
                articles.append(article)
        return articles
    except requests.exceptions.JSONDecodeError:
        st.error("La réponse de l'API PubMed n'est pas au format JSON. Impossible de récupérer les articles.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête à l'API PubMed : {str(e)}")
        return []

def determine_model_type(title, summary):
    """
    Détermine le type de modèle (PK, PKPD, etc.) en fonction des mots-clés dans le titre ou le résumé.
    """
    model_types = ["mono-compartimental", "bi-compartimental", "avec Tlag", "modèle de transit"]
    for model_type in model_types:
        if model_type.lower() in title.lower() or model_type.lower() in summary.lower():
            return model_type
    return "Non spécifié"

def detect_distribution_volume(text):
    """
    Vérifie si le texte contient une mention du volume de distribution avec une valeur numérique.
    """
    # Expressions courantes pour le volume de distribution
    volume_patterns = [
        r"central compartment volume[:=]?\s*\d+\.?\d*\s*(mL|L|µL)",  # Exemple : "central compartment volume: 50 L"
        r"Vd[:=]?\s*\d+\.?\d*\s*(mL|L|µL)",  # Exemple : "Vd = 50 L"
        r"distribution volume[:=]?\s*\d+\.?\d*\s*(mL|L|µL)",  # Exemple : "distribution volume = 100 mL"
    ]
    for pattern in volume_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "Oui"
    return "Non"

# Interface Streamlit
st.title("Recherche PK/PKPD avec détection du volume de distribution")

query = st.text_input("Entrez vos mots-clés de recherche (ex : clearance absorption distribution volume)")
user_keywords = query.split()  # Mots donnés par l'utilisateur
num_articles = st.slider("Nombre d'articles après filtrage", 1, 50, 10)  # Limite après filtrage

pharmacometry_keywords = [
    "PK model", "bicompartimental", "monocompartimental", 
    "pharmacokinetics", "pharmacodynamics", "estimated parameters", 
    "clearance", "absorption", "distribution volume", "central compartment",
    "Monolix", "NONMEM", "Mrgsolve", "Lixoft", "population modeling", 
    "parameter variability", "elimination rate", "half-life"
]

if st.button("Rechercher"):
    if query:
        # Construire la requête avec les mots-clés utilisateur et pharmacométriques
        constructed_query = construct_query_with_keywords(user_keywords, pharmacometry_keywords)
        st.write(f"Requête utilisée : {constructed_query}")

        # Étape 1 : Récupération des articles depuis PubMed
        st.write("Recherche en cours...")
        pubmed_ids = search_pubmed(constructed_query, max_results=200)
        st.write(f"Articles trouvés après récupération initiale : {len(pubmed_ids)}")

        if pubmed_ids:
            # Étape 2 : Récupération des détails des articles
            st.write("Récupération des détails des articles...")
            articles = fetch_article_details(pubmed_ids)
            st.write(f"Articles trouvés après récupération des détails : {len(articles)}")

            # Étape 3 : Limitation au nombre demandé par l'utilisateur
            limited_articles = articles[:num_articles]
            st.write(f"Articles affichés après limitation utilisateur : {len(limited_articles)}")
            
            # Affichage des résultats finaux
            df = pd.DataFrame(limited_articles)
            st.dataframe(df)

            # Option d'export des résultats
            st.download_button(
                label="Télécharger les résultats en CSV",
                data=df.to_csv(index=False),
                file_name="resultats_pk.csv",
                mime="text/csv",
            )
        else:
            st.warning("Aucun article correspondant trouvé. Essayez d'élargir votre recherche.")
    else:
        st.warning("Veuillez entrer des mots-clés pour effectuer une recherche.")
        
