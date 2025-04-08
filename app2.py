import requests
import pandas as pd
import streamlit as st

def construct_query_with_required_keywords(query):
    """
    Construit une requête PubMed qui rend obligatoires certains mots-clés spécifiques aux modèles PK et PKPD.
    """
    required_keywords = ["pharmacometry", "estimated parameters"]
    enriched_query = query + " AND " + " AND ".join(required_keywords)
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
    response = requests.get(base_url, params=params)
    return response.json().get("esearchresult", {}).get("idlist", [])

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
    response = requests.get(base_url, params=params)
    results = response.json()

    articles = []
    for id, details in results.get("result", {}).items():
        if id == "uids":  # Clé inutilisée
            continue
        article = {
            "Titre": details.get("title", "Non spécifié"),
            "Date de publication": details.get("pubdate", "Non spécifié"),
            "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
            "Journal": details.get("source", "Non spécifié"),
            "Résumé": details.get("title", "Non spécifié"),
            "Paramètres PK": extract_pk_parameters(details.get("title", "")),
        }
        articles.append(article)
    return articles

def extract_pk_parameters(text):
    """
    Extrait les paramètres PK des titres ou résumés des articles.
    """
    pk_parameters = ["clearance", "volume of distribution", "half-life", "absorption rate"]
    extracted_params = [param for param in pk_parameters if param.lower() in text.lower()]
    return ", ".join(extracted_params) if extracted_params else "Non spécifié"

# Interface Streamlit
st.title("Recherche PK/PKPD avec extraction des paramètres pharmacocinétiques")

query = st.text_input("Entrez vos mots-clés de recherche (ex : pharmacometry PK)")
max_results = st.slider("Nombre d'articles à récupérer", 5, 50, 20)

if st.button("Rechercher"):
    if query:
        # Construire la requête enrichie avec mots-clés obligatoires
        enriched_query = construct_query_with_required_keywords(query)
        st.write(f"Requête utilisée : {enriched_query}")

        st.write("Recherche en cours...")
        pubmed_ids = search_pubmed(enriched_query, max_results)
        st.write(f"Articles trouvés : {len(pubmed_ids)}")

        if pubmed_ids:
            st.write("Récupération des détails des articles...")
            articles = fetch_article_details(pubmed_ids)
            df = pd.DataFrame(articles)

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
            st.warning("Aucun article correspondant trouvé.")
    else:
        st.warning("Veuillez entrer des mots-clés pour effectuer une recherche.")
