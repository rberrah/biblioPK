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
    # Mots-clés obligatoires donnés par l'utilisateur
    user_query = " AND ".join(user_keywords)
    
    # Ici, on prend au moins 33% des mots-clés pharmacométriques (arrondi au supérieur)
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
        response.raise_for_status()  # Vérifie les erreurs HTTP
        data = response.json()  # Tente de parser la réponse en JSON
        return data.get("esearchresult", {}).get("idlist", [])
    except requests.exceptions.JSONDecodeError:
        st.error("La réponse de l'API PubMed n'est pas au format JSON. Vérifiez votre requête.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête à l'API PubMed : {str(e)}")
        return []

def contains_pk_model(text):
    """
    Détermine si le texte contient une mention d'un modèle PK selon une liste de mots clés inspirée de Monolix.
    """
    pk_model_keywords = [
        "pk model", "population pk", "nonlinear mixed effects", 
        "one-compartment", "two-compartment", "multi-compartment", "compartmental", "pk"
    ]
    for keyword in pk_model_keywords:
        if keyword.lower() in text.lower():
            return True
    return False

def model_keyword_score(text):
    """
    Calcule un score en fonction du nombre d'occurrences de mots clés relatifs aux modèles PK.
    """
    pk_model_keywords = [
        "pk model", "population pk", "nonlinear mixed effects", 
        "one-compartment", "two-compartment", "multi-compartment", "compartmental", "pk"
    ]
    score = 0
    lower_text = text.lower()
    for keyword in pk_model_keywords:
        score += lower_text.count(keyword.lower())
    return score

def determine_model_type(title, summary):
    """
    Détermine le type de modèle en cherchant des termes spécifiques.
    Inspiré de Monolix, il cherche par exemple "mono-compartimental", "bi-compartimental",
    "avec Tlag" ou "modèle de transit". Si aucun de ces termes n'est détecté mais que le texte contient
    une mention de "pk", il retourne "Modèle PK".
    """
    model_types = ["mono-compartimental", "bi-compartimental", "avec Tlag", "modèle de transit"]
    combined_text = f"{title} {summary}".lower()
    for mt in model_types:
        if mt in combined_text:
            return mt
    # Si le mot "pk" apparaît, on considère qu'il s'agit d'un modèle PK générique
    if "pk" in combined_text:
        return "Modèle PK"
    return "Non spécifié"

def fetch_article_details(pubmed_ids):
    """
    Récupère les détails des articles via leurs PubMed IDs et ajoute des informations sur le modèle PK.
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
            title = details.get("title", "Non spécifié")
            # Ici, on utilise le titre comme résumé en l'absence d'un autre champ
            summary = title  
            
            article = {
                "Journal": details.get("source", "Non spécifié"),
                "Date de publication": details.get("pubdate", "Non spécifié"),
                "Titre": title,
                "Lien": f"https://pubmed.ncbi.nlm.nih.gov/{id}/",
                "Résumé": summary,
                "Type de modèle": determine_model_type(title, summary),
                "Contient modèle PK": "Oui" if contains_pk_model(f"{title} {summary}") else "Non",
                "Score modèle PK": model_keyword_score(f"{title} {summary}")
            }
            articles.append(article)
        return articles
    except requests.exceptions.JSONDecodeError:
        st.error("La réponse de l'API PubMed n'est pas au format JSON. Impossible de récupérer les articles.")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la requête à l'API PubMed : {str(e)}")
        return []

# Interface Streamlit
st.title("Recherche PK/PKPD avec tri avancé et détection de modèles PK")

query = st.text_input("Entrez vos mots-clés de recherche (ex : clearance absorption distribution volume)")
user_keywords = query.split()  # Les mots donnés par l'utilisateur (obligatoires)
max_results = st.slider("Nombre d'articles à récupérer", 5, 50, 20)

pharmacometry_keywords = [
    "PK model", "bicompartimental", "monocompartimental", 
    "pharmacokinetics", "pharmacodynamics", "estimated parameters", 
    "clearance", "absorption", "distribution volume", "central compartment",
    "Monolix", "NONMEM", "Mrgsolve", "Lixoft", "population modeling", 
    "parameter variability", "elimination rate", "half-life", 
    "bioavailability", "rate of absorption", "compartment volume"
]

if st.button("Rechercher"):
    if query:
        # Construire la requête : les mots de l'utilisateur sont à 100% et 
        # nous prenons au moins 33% des mots-clés pharmacométriques
        constructed_query = construct_query_with_keywords(user_keywords, pharmacometry_keywords)
        st.write(f"Requête utilisée : {constructed_query}")
        
        st.write("Recherche en cours...")
        pubmed_ids = search_pubmed(constructed_query, max_results)
        st.write(f"Articles trouvés : {len(pubmed_ids)}")
        
        if pubmed_ids:
            st.write("Récupération des détails des articles...")
            articles = fetch_article_details(pubmed_ids)
            
            # Création d'une DataFrame avec les résultats
            df = pd.DataFrame(articles)
            
            # Pour prioriser, on ajoute une colonne dérivée pour faciliter le tri :
            # les articles contenant un modèle PK (flag = 0) puis tri par Score modèle PK décroissant.
            df["Flag PK"] = df["Contient modèle PK"].map({"Oui": 0, "Non": 1})
            df = df.sort_values(by=["Flag PK", "Score modèle PK"], ascending=[True, False])
            df.drop(columns=["Flag PK"], inplace=True)  # On peut supprimer ce flag si souhaité
            
            # Tri dynamique complémentaire (ex: par Journal ou Date de publication) si désiré
            sort_column = st.selectbox("Trier ensuite par :", options=["Journal", "Date de publication"], index=0)
            if sort_column in df.columns:
                df = df.sort_values(by=sort_column, ascending=True)
            
            st.dataframe(df)
            
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
