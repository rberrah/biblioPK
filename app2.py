import requests
import pandas as pd
import math
import re
import streamlit as st

def construct_query_with_keywords(user_keywords, pharmacometry_keywords):
    """
    Construit une requête PubMed avec des mots-clés obligatoires (donnés par l'utilisateur à 100%)
    et au moins 33% des mots-clés liés à la pharmacométrie.
    """
    user_query = " AND ".join(user_keywords)
    min_keywords = math.ceil(len(pharmacometry_keywords) * 33 / 100)
    pharmacometry_query = " OR ".join(pharmacometry_keywords[:min_keywords])
    enriched_query = f"({user_query}) AND ({pharmacometry_query})"
    return enriched_query

def search_pubmed(query, max_results=50):
    """
    Recherche des articles sur PubMed via l'API Entrez.
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête : {str(e)}")
        return []

def contains_pk_model(text):
    """
    Vérifie si un texte mentionne un modèle PK (inspiré de Monolix).
    """
    pk_models = [
        "one-compartment", "two-compartment", "three-compartment", "zero-order absorption",
        "first-order absorption", "two-compartment pk model", "transit model", "gamma model", 
        "iv bolus", "iv infusion", "oral absorption", "nonlinear mixed-effects"
    ]
    for model in pk_models:
        if model.lower() in text.lower():
            return True
    return False

def detect_estimated_parameters(text):
    """
    Vérifie la présence de paramètres estimés dans un texte.
    """
    parameter_patterns = [
        r"Vd[:=]?\s*\d+\.?\d*\s*(mL|L|µL)",
        r"CL[:=]?\s*\d+\.?\d*\s*(mL/min|L/h)", 
        r"Ka[:=]?\s*\d+\.?\d*", 
        r"Tlag[:=]?\s*\d+\.?\d*", 
        r"MTT[:=]?\s*\d+\.?\d*"
    ]
    for pattern in parameter_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def fetch_article_details(pubmed_ids, pharmacometry_keywords):
    """
    Récupère les détails des articles via leurs PubMed IDs.
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {"db": "pubmed", "id": ",".join(pubmed_ids), "retmode": "json"}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        articles = []
        for id, details in data.get("result", {}).items():
            if id == "uids":
                continue
            title = details.get("title", "Non spécifié")
            summary = title  
            article = {
                "Journal": details.get("source", "Non spécifié"),
                "Date de publication": details.get("pubdate", "Non spécifié"),
                "Titre": title,
                "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
                "Type de modèle": determine_model_type(title, summary),
                "Contient modèle PK": "Oui" if contains_pk_model(f"{title} {summary}") else "Non",
                "Paramètres estimés détectés": "Oui" if detect_estimated_parameters(f"{title} {summary}") else "Non",
                "Score mots-clés": calculate_relevance_score(f"{title} {summary}", pharmacometry_keywords)
            }
            articles.append(article)
        return articles
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête : {str(e)}")
        return []

def determine_model_type(title, summary):
    """
    Détecte le type de modèle mentionné (d'après la liste Monolix ou en combinant PK).
    """
    combined_text = f"{title} {summary}".lower()
    model_types = ["mono-compartimental", "bi-compartimental", "transit model"]
    for model_type in model_types:
        if model_type in combined_text:
            return model_type
    if "pk" in combined_text:
        return "Modèle PK"
    return "Non spécifié"

def calculate_relevance_score(text, keywords):
    """
    Calcule un score en fonction du nombre d'occurrences des mots-clés pharmacométriques.
    """
    score = 0
    text = text.lower()
    for keyword in keywords:
        score += text.count(keyword.lower())
    return score

# Interface Streamlit
st.title("Recherche PK/PKPD avec détection des modèles PK et paramètres estimés")

query = st.text_input("Entrez vos mots-clés de recherche (ex : clearance absorption volume)")
user_keywords = query.split()
max_results = st.slider("Nombre d'articles à récupérer", 5, 100, 50)

pharmacometry_keywords = [
    "PK model", "Vd", "Cl", "Ka", "Tlag", "MTT", "covariables",
    "volume central", "volume périphérique", "clairance intercompartimentale",
    "Monolix", "NONMEM", "nlmixr", "bootstrap", "Monte Carlo simulation", 
    "Visual Predictive Check", "Obs vs Pred", "residual variability", "bioavailability"
]

if st.button("Rechercher"):
    if query:
        constructed_query = construct_query_with_keywords(user_keywords, pharmacometry_keywords)
        st.write(f"Requête utilisée : {constructed_query}")
        pubmed_ids = search_pubmed(constructed_query, max_results)
        st.write(f"Articles récupérés : {len(pubmed_ids)}")
        if pubmed_ids:
            articles = fetch_article_details(pubmed_ids, pharmacometry_keywords)
            df = pd.DataFrame(articles)
            df = df.sort_values(by=["Contient modèle PK", "Paramètres estimés détectés"], ascending=[False, False])
            st.dataframe(df)
            st.download_button(
                label="Télécharger les résultats en CSV",
                data=df.to_csv(index=False),
                file_name="resultats_pk.csv",
                mime="text/csv",
            )
