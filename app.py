import requests
import pandas as pd
import streamlit as st

def enrich_query_with_pk_keywords(query):
    """
    Enrichit la requête de recherche initiale avec des mots-clés spécifiques aux modèles PK/PKPD.
    """
    pk_keywords = [
        "Monolix", "NONMEM", "estimated clearance", 
        "pharmacokinetics model", "pharmacodynamic model", 
        "population PK", "compartmental model", 
        "estimated parameter", "Bayesian analysis", "clearance variability",
        "PKPD modeling", "absorption rate", "elimination half-life"
    ]
    enriched_query = query + " (" + " OR ".join(pk_keywords) + ")"
    return enriched_query

def search_pubmed(query, max_results=20):
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
    response = requests.get(base_url, params=params)
    results = response.json()
    return results["esearchresult"]["idlist"]

def fetch_article_details(pubmed_ids, query_keywords):
    """
    Récupération des détails des articles à partir de leurs PubMed IDs et ajout des informations spécifiques.
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pubmed_ids),
        "retmode": "json",
    }
    response = requests.get(base_url, params=params)
    results = response.json()
    articles = []
    for id, details in results["result"].items():
        if id == "uids":  # Clé inutilisée
            continue
        article = {
            "Type de modèle": determine_model_type(details.get("title", ""), details.get("title", "")),
            "Titre": details.get("title", "Non spécifié"),
            "Date de publication": details.get("pubdate", "Non spécifié"),
            "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
            "Résumé": details.get("title", "Non spécifié"),
            "Journal": details.get("source", "Non spécifié"),
            "Nombre de sujets": extract_subject_count(details.get("title", "")),
        }
        # Score de pertinence basé sur les mots-clés
        article["Score Pertinence"] = calculate_relevance_score(article, query_keywords)
        articles.append(article)
    return sorted(articles, key=lambda x: x["Score Pertinence"], reverse=True)

def determine_model_type(title, summary):
    """
    Détermine le type de modèle (PK, PKPD, etc.) en fonction des mots-clés dans le titre ou le résumé.
    """
    model_types = ["PK", "PKPD", "mono-compartimental", "bicompartmental"]
    for model_type in model_types:
        if model_type.lower() in title.lower() or model_type.lower() in summary.lower():
            return model_type
    return "Non spécifié"

def extract_subject_count(summary):
    """
    Extrait le nombre de sujets ayant permis de développer le modèle à partir du résumé.
    """
    words = summary.lower().split()
    for i, word in enumerate(words):
        if word in ["subjects", "patients", "individuals"]:
            try:
                return int(words[i - 1])  # Retourne le nombre avant le mot clé
            except ValueError:
                continue
    return "Non spécifié"

def calculate_relevance_score(article, query_keywords):
    """
    Calcule un score de pertinence basé sur :
    - La correspondance des mots-clés dans le titre et le résumé
    """
    title = article["Titre"].lower()
    summary = article["Résumé"].lower()
    keyword_score = sum([title.count(keyword.lower()) + summary.count(keyword.lower()) for keyword in query_keywords])
    return keyword_score

# Interface Streamlit
st.title("Recherche PubMed spécialisée pour les modèles PK et PKPD")

# Entrée utilisateur
query = st.text_input("Critères de recherche (exemple : 'ICU')", "")
max_results = st.slider("Nombre d'articles à récupérer", 5, 50, 20)

if st.button("Rechercher"):
    if query:
        # Enrichir la requête avec des mots-clés spécifiques aux modèles PK/PKPD
        enriched_query = enrich_query_with_pk_keywords(query)
        st.write(f"Requête enrichie utilisée : {enriched_query}")

        st.write("Recherche en cours...")
        pubmed_ids = search_pubmed(enriched_query, max_results)
        st.write(f"{len(pubmed_ids)} articles trouvés.")

        st.write("Récupération des détails des articles et ajout des informations spécifiques...")
        articles = fetch_article_details(pubmed_ids, enriched_query.split())
        df = pd.DataFrame(articles)

        # Affichage des résultats
        st.dataframe(df)

        # Option d'export pour les résultats
        st.download_button(
            label="Télécharger les résultats en CSV",
            data=df.to_csv(index=False),
            file_name="resultats_pk_pkpd.csv",
            mime="text/csv",
        )
    else:
        st.warning("Veuillez entrer des critères de recherche.")
