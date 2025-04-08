import requests
import pandas as pd
import math
import streamlit as st

def construct_query_with_keywords(user_keywords, pharmacometry_keywords):
    """
    Construit une requête PubMed avec des mots-clés obligatoires (donnés par l'utilisateur à 100%)
    et au moins 33% des mots-clés liés à la pharmacométrie.
    """
    # Mots-clés obligatoires donnés par l'utilisateur
    user_query = " AND ".join(user_keywords)

    # Mots-clés pharmacométriques : au moins 33% arrondi au supérieur
    min_keywords = math.ceil(len(pharmacometry_keywords) * 33 / 100)
    pharmacometry_query = " OR ".join(pharmacometry_keywords[:min_keywords])

    # Construction de la requête enrichie
    enriched_query = f"({user_query}) AND ({pharmacometry_query})"
    return enriched_query

def search_pubmed(query, max_results=50):
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
        response.raise_for_status()  # Vérifie les erreurs HTTP (ex: 404, 500)
        data = response.json()  # Tente de parser la réponse en JSON
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
                "Figure/Tableau avec paramètres estimés": extract_figures_tables(details.get("title", "")),
            }
            # Filtrer uniquement les articles avec une figure ou un tableau contenant des paramètres estimés
            if article["Figure/Tableau avec paramètres estimés"] == "Oui":
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

def extract_figures_tables(text):
    """
    Vérifie si le texte contient une mention de figure ou tableau avec "estimated parameters".
    """
    if "figure" in text.lower() or "table" in text.lower():
        if "estimated parameters" in text.lower():
            return "Oui"
    return "Non"

# Interface Streamlit
st.title("Recherche PK/PKPD avec tri avancé et extraction des modèles pharmacocinétiques")

query = st.text_input("Entrez vos mots-clés de recherche (ex : clearance absorption distribution volume)")
user_keywords = query.split()  # Mots donnés par l'utilisateur
max_results = st.slider("Nombre d'articles à récupérer", 5, 50, 20)

pharmacometry_keywords = [
    "PK model", "bicompartimental", "monocompartimental", 
    "pharmacokinetics", "pharmacodynamics", "estimated parameters", 
    "clearance", "absorption", "distribution volume", "central compartment",
    "Monolix", "NONMEM", "Mrgsolve", "Lixoft", "population modeling", 
    "parameter variability", "elimination rate", "half-life"
]

if st.button("Rechercher"):
    if query:
        # Construire la requête avec les mots-clés utilisateur à 100% et les mots-clés pharmacométriques à 33%
        constructed_query = construct_query_with_keywords(user_keywords, pharmacometry_keywords)
        st.write(f"Requête utilisée : {constructed_query}")

        st.write("Recherche en cours...")
        pubmed_ids = search_pubmed(constructed_query, max_results)
        st.write(f"Articles trouvés : {len(pubmed_ids)}")

        if pubmed_ids:
            st.write("Récupération des détails des articles...")
            articles = fetch_article_details(pubmed_ids)
            df = pd.DataFrame(articles)

            # Tri dynamique
            sort_column = st.selectbox("Trier les résultats par :", options=["Journal", "Date de publication"])
            if sort_column:
                df = df.sort_values(by=sort_column, ascending=True)

            # Affichage des résultats
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
