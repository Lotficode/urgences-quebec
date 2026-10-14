"""API REST : situation actuelle, prévisions et recommandation de l'urgence la moins pleine.

    uvicorn urgences.api:app --reload
    puis ouvrir http://127.0.0.1:8000/docs
"""
from fastapi import FastAPI, HTTPException, Query

from urgences import base, config, modele


def _enregistrements(tableau):
    tableau = tableau.copy()
    for colonne in tableau.columns:
        if str(tableau[colonne].dtype).startswith("datetime"):
            tableau[colonne] = tableau[colonne].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return tableau.astype(object).where(tableau.notna(), None).to_dict(orient="records")


def creer_app(chemin_base=None) -> FastAPI:
    app = FastAPI(
        title="Urgences Québec",
        description="Prévision du taux d'occupation des urgences du Québec à partir des données ouvertes du MSSS.",
        version="1.0.0",
    )
    cache_modeles: dict[int, modele.ModeleUrgences] = {}

    def obtenir_modele(horizon: int) -> modele.ModeleUrgences:
        if horizon not in cache_modeles:
            charge = modele.charger(horizon)
            if charge is None:
                raise HTTPException(503, f"Aucun modèle entraîné pour l'horizon {horizon} h.")
            cache_modeles[horizon] = charge
        return cache_modeles[horizon]

    def historique():
        with base.connecter(chemin_base) as connexion:
            return base.lire_historique(connexion)

    @app.get("/sante")
    def sante():
        with base.connecter(chemin_base) as connexion:
            nombre, derniere = connexion.execute(
                "SELECT COUNT(*), MAX(heure_extraction) FROM releves"
            ).fetchone()
        return {"statut": "ok", "releves": nombre, "dernier_releve": derniere}

    @app.get("/urgences")
    def urgences(region: str | None = None):
        with base.connecter(chemin_base) as connexion:
            situation = base.dernier_releve(connexion)
        if region:
            situation = situation[situation["region"].str.contains(region, case=False, na=False)]
        return _enregistrements(situation)

    @app.get("/urgences/{no_permis}/prevision")
    def prevision(no_permis: str, horizon: int = Query(4, ge=1, le=24)):
        previsions = modele.predire(obtenir_modele(horizon), historique())
        ligne = previsions[previsions["no_permis"] == no_permis] if len(previsions) else previsions
        if ligne.empty:
            raise HTTPException(404, f"Urgence {no_permis} introuvable.")
        return _enregistrements(ligne)[0]

    @app.get("/recommandations")
    def recommandations(
        region: str | None = None,
        horizon: int = Query(4, ge=1, le=24),
        limite: int = Query(5, ge=1, le=50),
    ):
        """Les urgences qui devraient être les moins pleines dans `horizon` heures."""
        previsions = modele.predire(obtenir_modele(horizon), historique())
        if region and len(previsions):
            previsions = previsions[previsions["region"].str.contains(region, case=False, na=False)]
        return _enregistrements(previsions.sort_values("taux_prevu").head(limite))

    @app.get("/modele/metriques")
    def metriques(horizon: int = Query(4, ge=1, le=24)):
        return obtenir_modele(horizon).metriques

    return app


app = creer_app()
