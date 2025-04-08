import requests
import pandas as pd
import streamlit as st

# Fonction pour rechercher des articles sur PubMed
def search_pubmed(query, max_results=20):
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

# Fonction pour récupérer les détails des articles
def fetch_article_details(pubmed_ids, query_keywords):
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
            "Titre": details.get("title", "Non spécifié"),
            "Date de publication": details.get("pubdate", "Non spécifié"),
            "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
            "Résumé": details.get("title", "Non spécifié"),
            "Journal": details.get("source", "Non spécifié"),
        }
        # Score de pertinence basé sur les mots-clés
        article["Score Pertinence"] = calculate_relevance_score(article, query_keywords)
        articles.append(article)
    return sorted(articles, key=lambda x: x["Score Pertinence"], reverse=True)

# Fonction pour calculer le score de pertinence
def calculate_relevance_score(article, query_keywords):
    title = article["Titre"].lower()
    summary = article["Résumé"].lower()
    keyword_score = sum([title.count(keyword.lower()) + summary.count(keyword.lower()) for keyword in query_keywords])
    return keyword_score

# Initialisation de la session Streamlit
if "results" not in st.session_state:
    st.session_state["results"] = None  # Pour les résultats de recherche
if "query_keywords" not in st.session_state:
    st.session_state["query_keywords"] = None  # Pour les mots-clés
if "refine_keywords" not in st.session_state:
    st.session_state["refine_keywords"] = None  # Pour les commentaires d'affinage

# Interface Streamlit
st.title("Recherche PubMed avec Classement par Pertinence")

# Entrée utilisateur
query = st.text_input("Critères de recherche (exemple : 'antibiotic ICU')", "")
max_results = st.slider("Nombre d'articles à récupérer", 5, 50, 20)

if st.button("Rechercher"):
    if query:
        st.write("Recherche en cours...")
        pubmed_ids = search_pubmed(query, max_results)
        st.session_state["query_keywords"] = query.split()
        articles = fetch_article_details(pubmed_ids, st.session_state["query_keywords"])
        st.session_state["results"] = articles
        st.write(f"{len(articles)} articles trouvés.")

if st.session_state["results"]:
    df = pd.DataFrame(st.session_state["results"])
    st.dataframe(df)

    # Option d'affinage des résultats
    st.markdown("### Affiner la recherche")
    refine_keywords = st.text_input("Ajouter des mots-clés pour affiner les résultats (exemple : 'macrolides, vancomycin')", "")
    if st.button("Affiner") and refine_keywords:
        st.session_state["refine_keywords"] = refine_keywords.split(",")
        refined_articles = [
            article for article in st.session_state["results"]
            if any(keyword.strip().lower() in article["Titre"].lower() or keyword.strip().lower() in article["Résumé"].lower()
                   for keyword in st.session_state["refine_keywords"])
        ]
        refined_df = pd.DataFrame(refined_articles)
        st.dataframe(refined_df)

        # Option d'export pour les résultats affinés
        st.download_button(
            label="Télécharger les résultats affinés en CSV",
            data=refined_df.to_csv(index=False),
            file_name="resultats_pubmed_affines.csv",
            mime="text/csv",
        )

    # Option d'export pour les résultats initiaux
    st.download_button(
        label="Télécharger les résultats en CSV",
        data=df.to_csv(index=False),
        file_name="resultats_pubmed_classe.csv",
        mime="text/csv",
    )
else:
    st.warning("Veuillez effectuer une recherche pour voir les résultats.")
