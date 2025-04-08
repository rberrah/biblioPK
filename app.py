import requests
import pandas as pd
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk
import streamlit as st

# Assurez-vous que NLTK est configuré correctement
nltk.download('punkt')
nltk.download('stopwords')

def search_pubmed(query, max_results=20):
    """Recherche des articles sur PubMed via l'API Entrez."""
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
    """Récupération des détails des articles à partir de leurs PubMed IDs et ajout d'un score de pertinence."""
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
            "Population étudiée": extract_population(details.get('title', "")),
            "Journal": details.get("source", "Non spécifié"),
        }
        # Calcul du score de pertinence
        article["Score Pertinence"] = calculate_relevance_score(article, query_keywords)
        articles.append(article)
    return sorted(articles, key=lambda x: x["Score Pertinence"], reverse=True)

def extract_population(title):
    """Utilise un traitement NLP pour détecter des mots-clés relatifs à la population étudiée dans le titre ou le résumé."""
    tokens = word_tokenize(title)
    stop_words = set(stopwords.words('english'))
    filtered_tokens = [word for word in tokens if word.lower() not in stop_words]
    populations = ['mice', 'rats', 'humans', 'children', 'adults']
    for token in filtered_tokens:
        if token.lower() in populations:
            return token.capitalize()
    return "Non spécifié"

def calculate_relevance_score(article, query_keywords):
    """
    Calcule un score de pertinence basé sur :
    - La correspondance des mots-clés dans le titre et le résumé
    - La date de publication (plus récent = meilleur score)
    """
    title = article["Titre"].lower()
    summary = article["Résumé"].lower()
    date = article["Date de publication"]

    # Score pour les mots-clés
    keyword_score = sum([title.count(keyword.lower()) + summary.count(keyword.lower()) for keyword in query_keywords])

    # Score pour la date (articles récents ont un score plus élevé)
    date_score = 0
    if " " in date:  # Si la date est au format complet (ex: "2023 Apr 01")
        year = int(date.split(" ")[0])
        date_score = max(0, 2025 - year)  # Hypothèse : date actuelle = 2025

    # Combiner les scores
    total_score = keyword_score - date_score
    return total_score

# Interface Streamlit
st.title("Recherche PubMed avec Classement par Pertinence")
st.markdown("Entrez vos critères de recherche pour obtenir une liste d'articles scientifiques classée par pertinence.")

# Entrée utilisateur
query = st.text_input("Critères de recherche (exemple : 'antibiotic mice pharmacokinetics')", "")
max_results = st.slider("Nombre d'articles à récupérer", 5, 50, 20)

if st.button("Rechercher"):
    if query:
        st.write("Recherche en cours...")
        query_keywords = query.split()
        pubmed_ids = search_pubmed(query, max_results)
        st.write(f"{len(pubmed_ids)} articles trouvés.")

        st.write("Récupération des détails des articles et calcul des pertinences...")
        articles = fetch_article_details(pubmed_ids, query_keywords)
        df = pd.DataFrame(articles)

        # Affichage des résultats
        st.dataframe(df)

        # Option d'export
        st.download_button(
            label="Télécharger les résultats en CSV",
            data=df.to_csv(index=False),
            file_name="resultats_pubmed_classe.csv",
            mime="text/csv",
        )
    else:
        st.warning("Veuillez entrer des critères de recherche.")
