from urgences import base, collecte


def test_ne_garde_que_les_installations(csv_officiel):
    releves = collecte.nettoyer(collecte.lire_csv(csv_officiel))
    assert list(releves["no_permis"]) == ["11111111", "22222222"]   # totaux retirés


def test_convertit_les_nombres_et_calcule_le_taux(csv_officiel):
    releves = collecte.nettoyer(collecte.lire_csv(csv_officiel)).set_index("no_permis")
    a = releves.loc["11111111"]
    assert a["civieres_occupees"] == 52
    assert a["patients_plus_48h"] == 3
    assert a["dms_civiere"] == 22.5                     # virgule décimale acceptée
    assert a["taux_occupation"] == 1.3                  # 52 / 40
    assert a["heure_extraction"] == "2026-10-13T14:00:00"
    assert a["nom_installation"] == "Hôpital Démo A"     # accents lus correctement (cp1252)


def test_import_idempotent(csv_officiel, tmp_path):
    releves = collecte.nettoyer(collecte.lire_csv(csv_officiel))
    with base.connecter(tmp_path / "t.db") as connexion:
        assert base.enregistrer(connexion, releves) == 2
        assert base.enregistrer(connexion, releves) == 0   # relancer ne crée aucun doublon
        assert connexion.execute("SELECT COUNT(*) FROM releves").fetchone()[0] == 2


def test_civieres_nulles_ne_plantent_pas(csv_officiel):
    brut = collecte.lire_csv(csv_officiel)
    brut.loc[0, "Nombre_de_civieres_fonctionnelles"] = "0"
    releves = collecte.nettoyer(brut)
    assert releves["taux_occupation"].isna().iloc[0]
