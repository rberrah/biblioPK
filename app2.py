import requests
import pandas as pd
import math
import re
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

def fetch_article_details(pubmed_ids, pharmacometry_keywords):
    """
    Récupération des détails des articles à partir de leurs PubMed IDs et ajout du score de pertinence.
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
        
        # Affichage des données brutes pour débogage
        st.write("Données brutes retournées par l'API esummary :")
        st.write(data)
        
        articles = []
        for id, details in data.get("result", {}).items():
            if id == "uids":  # Clé inutilisée
                continue
            title = details.get("title", "Non spécifié")
            summary = title  # Pour simplifier, le résumé est le titre dans cet exemple

            # Calcul du score de pertinence basé sur les mots-clés
            score = calculate_relevance_score(title, summary, pharmacometry_keywords)

            article = {
                "Journal": details.get("source", "Non spécifié"),
                "Date de publication": details.get("pubdate", "Non spécifié"),
                "Titre": title,
                "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
                "Résumé": summary,
                "Type de modèle": determine_model_type(title, summary),
                "Volume de distribution détecté": detect_distribution_volume(title),
                "Score de pertinence": score,
            }
            articles.append(article)

        # Réorganiser les articles : prioriser ceux avec un volume détecté
        articles_sorted = sorted(
            articles,
            key=lambda x: (x["Volume de distribution détecté"] == "Non", -x["Score de pertinence"])
        )
        return articles_sorted
    except requests.exceptions.JSONDecodeError:
        st.error("La réponse de l'API PubMed n'est pas au format JSON. Impossible de récupérer les articles.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête à l'API PubMed : {str(e)}")
        return []

def calculate_relevance_score(title, summary, keywords):
    """
    Calcule un score de pertinence en fonction du nombre de mots-clés présents dans le titre et le résumé.
    """
    text = f"{title} {summary}".lower()
    return sum(1 for keyword in keywords if keyword.lower() in text)

def determine_model_type(title, summary):
    """
    Détermine le type de modèle (PK, PKPD, etc.) en fonction des mots-clés dans le titre ou le résumé.
    """
    model_types = ["mono-compartimental", "bi-compartimental", "avec Tlag", "modèle de transit"]
    for model_type in model_types:
        if model_type.lower() in (title + summary).lower():
            return model_type
    return "Non spécifié"

def detect_distribution_volume(text):
    """
    Vérifie si le texte contient une mention du volume de distribution avec une valeur numérique.
    """
    volume_patterns = [
        r"central compartment volume[:=]?\s*\d+\.?\d*\s*(mL|L|µL)",
        r"Vd[:=]?\s*\d+\.?\d*\s*(mL|L|µL)",
        r"distribution volume[:=]?\s*\d+\.?\d*\s*(mL|L|µL)"
    ]
    for pattern in volume_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return "Oui"
    return "Non"

# Interface Streamlit
st.title("Recherche PK/PKPD avec tri avancé basé sur la pertinence")

query = st.text_input("Entrez vos mots-clés de recherche (ex : clearance absorption distribution volume)")
user_keywords = query.split()
num_articles = st.slider("Nombre maximal d'articles à afficher", 1, 50, 10)

pharmacometry_keywords = [
    "PK model", "bicompartimental", "monocompartimental", 
    "pharmacokinetics", "pharmacodynamics", "estimated parameters", 
    "clearance", "absorption", "distribution volume", "central compartment",
    "Monolix", "NONMEM", "Mrgsolve", "Lixoft", "population modeling", 
    "parameter variability", "elimination rate constant", "half-life", 
    "bioavailability", "rate of absorption", "compartment volume"
]

if st.button("Rechercher"):
    if query:
        constructed_query = construct_query_with_keywords(user_keywords, pharmacometry_keywords)
        st.write(f"Requête utilisée : {constructed_query}")

        pubmed_ids = search_pubmed(constructed_query, max_results=200)
        st.write(f"Articles trouvés après récupération initiale : {len(pubmed_ids)}")

        if pubmed_ids:
            articles = fetch_article_details(pubmed_ids, pharmacometry_keywords)
            st.write(f"Articles après tri par pertinence et présence de paramètres estimés : {len(articles)}")

            limited_articles = articles[:num_articles]
            st.write(f"Articles affichés : {len(limited_articles)}")
            df = pd.DataFrame(limited_articles)
            st.dataframe(df)

            st.download_button(
                label="Télécharger les résultats en CSV",
                data=df.to_csv(index=False),
                file_name="resultats_pk.csv",
                mime="text/csv",
            )
        else:
            st.warning("Aucun article trouvé.")
    else:
        st.warning("Veuillez entrer des mots-clés pour effectuer une recherche.")
