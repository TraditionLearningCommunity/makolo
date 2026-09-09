# Benchmark de montée en charge

Le benchmark `benchmarks/benchmark_scaling.py` mesure le solveur de gravité arborescent compilé sans confondre vitesse et précision.

Il génère une population déterministe, chauffe le kernel Numba, mesure une évaluation gravitationnelle, et compare à `SolveurGraviteDirect` jusqu'à `--max-direct`. Chaque taille est lancée dans un processus distinct avec un timeout : une taille trop lourde est donc marquée `timeout`, elle ne bloque pas toute la campagne.

Exemple :

```bash
pip install -e '.[performance]'
python benchmarks/benchmark_scaling.py --timeout 60
```

## Mesures indicatives du 9 septembre 2026

Environnement de développement : 5 threads CPU, NumPy + Numba 0.65.1. Ces valeurs ne sont pas des garanties de performance sur une autre machine.

Pour le compromis `theta=0.8`, `leaf_capacity=48` :

- validation à 2 500 corps contre Direct N-body : erreur médiane ~0,84 %, erreur p95 ~2,39 % ;
- 100 000 corps : environ 0,7–1,1 s suivant le run ;
- 500 000 corps : environ 4,6 s après batching des targets ;
- 1 000 000 corps : **pas encore validé dans la fenêtre d'exécution actuelle** ; le benchmark doit le déclarer comme timeout plutôt que le présenter comme supporté.

Les seuils doivent être re-mesurés après chaque changement du solveur, du matériel ou des paramètres d'ouverture. Le solveur direct reste l'étalon d'exactitude sur les petites populations.
