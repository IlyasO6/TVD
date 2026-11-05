"""Sistema recomanador immobiliari basat en regles (Exercici 7).

Iteració 0 = comportament de l'Exercici 6 portat tal qual des del notebook.
Bloc 1 = flux reordenat (sense ingressos) i instruccions més clares (house_data_v2.json).

Mòduls:
    config            constants i paràmetres configurables
    data_loader       càrrega del JSON
    io_adapter        entrada/sortida injectable (consola, Colab o guions de prova)
    state             estat del diàleg
    nlu               preprocessament i interpretació de les respostes de l'usuari
    recommender       filtratge (i, més endavant, recompte de matches)
    nlg               microplanificació i realització superficial
    dialogue_manager  política del diàleg i bucle principal
"""

from .dialogue_manager import run

__all__ = ["run"]
