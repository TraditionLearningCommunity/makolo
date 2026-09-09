from __future__ import annotations

from dataclasses import dataclass, field

from ..laws.base import ModelePhysique
from ..regimes import NiveauActiviteCalcul, PolitiqueDynamique, RegimeDynamique


@dataclass(slots=True)
class ConfigurationPhysique:
    modeles: list[ModelePhysique] = field(default_factory=list)
    collisions_actives: bool = True
    conserver_historique: bool = True
    enregistrer_tous_les_n_pas: int = 1
    politique_dynamique: PolitiqueDynamique = field(default_factory=PolitiqueDynamique)
    regimes_par_corps: dict[str, RegimeDynamique] = field(default_factory=dict)
    niveaux_activite_par_corps: dict[str, NiveauActiviteCalcul] = field(default_factory=dict)

    def ajouter_modele(self, modele: ModelePhysique) -> None:
        self.modeles.append(modele)

    def modeles_actifs(self) -> tuple[ModelePhysique, ...]:
        return tuple(m for m in self.modeles if m.active)

    def regime_pour(self, corps_id: str) -> RegimeDynamique:
        return self.regimes_par_corps.get(corps_id, self.politique_dynamique.regime_par_defaut)

    def definir_regime(self, corps_id: str, regime: RegimeDynamique) -> None:
        self.regimes_par_corps[corps_id] = regime

    def niveau_activite_pour(self, corps_id: str) -> NiveauActiviteCalcul:
        return self.niveaux_activite_par_corps.get(corps_id, NiveauActiviteCalcul.ACTIVE)

    def definir_niveau_activite(self, corps_id: str, niveau: NiveauActiviteCalcul) -> None:
        self.niveaux_activite_par_corps[corps_id] = niveau
