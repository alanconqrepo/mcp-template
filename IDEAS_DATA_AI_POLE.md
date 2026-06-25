# Idées de familles de tools MCP — Pôle Data & IA

> Contexte : un pôle data & IA interne à un industriel spécialisé dans les pompes. L'équipe gère des pipelines de données, des modèles ML (maintenance prédictive, détection d'anomalies, sélection de pompe), des bases vectorielles pour le RAG, et des agents IA exposés aux métiers.
>
> **Stack déjà intégrée dans ce template** : Prefect (orchestration), Langfuse (tracing LLM), Azure Blob (stockage), SQL Server (données métier) — les tools ci-dessous s'en servent directement.

---

## 1. `ml_registry` — Registre de modèles ML

### Pourquoi
Le pôle maintient plusieurs modèles en production (détection d'anomalie vibratoire, prédiction de panne roulement, classification de défaut). Sans registre, l'agent ne sait pas quelle version est déployée, quelles métriques ont validé le modèle, ni quel dataset l'a entraîné. Ce tool permet à l'agent de choisir le bon modèle, de déclencher une réinférence, ou d'alerter si les métriques dérivent.

### Tools envisagés
| Tool | Description |
|---|---|
| `ml_list_models` | Liste les modèles enregistrés (nom, dernière version, stage : Staging/Production) |
| `ml_get_model_version` | Détails d'une version (métriques, paramètres, dataset d'entraînement, auteur) |
| `ml_compare_versions` | Compare deux versions sur leurs métriques clés |
| `ml_transition_stage` | Passe un modèle de Staging → Production (ou archive) |
| `ml_get_latest_run` | Récupère le dernier run d'entraînement pour un modèle (durée, loss, accuracy) |
| `ml_download_artifact` | Télécharge un artefact (modèle sérialisé, rapport de validation) vers Azure Blob |

### Comment
- **Source** : MLflow Tracking Server ou Azure Machine Learning Model Registry via leurs API REST
- **Auth** : jeton Azure AD ou token MLflow (OAuth2, déjà supporté par ce template)
- **Réutilisation** : `ml_download_artifact` s'appuie sur `azure_blob` existant pour le stockage
- **Pattern** : sessions stateless, chaque appel est indépendant — pas de contexte partagé entre tools

---

## 2. `vector_store` — Base vectorielle & RAG

### Pourquoi
Le pôle construit des pipelines RAG pour plusieurs usages : assistant documentation technique, chatbot de dépannage, recherche de retours d'expérience. Ces tools permettent à l'agent d'interroger directement les collections vectorielles sans passer par une couche intermédiaire, et de gérer le contenu indexé (ajout, suppression, mise à jour).

### Tools envisagés
| Tool | Description |
|---|---|
| `vector_search` | Recherche sémantique dans une collection (query texte → top-k chunks + scores) |
| `vector_get_document` | Récupère tous les chunks d'un document par son ID source |
| `vector_list_collections` | Liste les collections disponibles avec leur nombre de vecteurs |
| `vector_upsert` | Insère ou met à jour un document (texte + métadonnées) dans une collection |
| `vector_delete_document` | Supprime tous les chunks d'un document (par source_id) |
| `vector_get_collection_stats` | Taille, dimension, modèle d'embedding, date dernière ingestion |

### Comment
- **Source** : Qdrant (self-hosted Docker) ou Azure AI Search ou pgvector selon l'infra
- **Embedding** : l'embedding de la query se fait côté tool (appel à un endpoint dédié ou `azure_openai`) pour que l'agent passe du texte brut, pas des vecteurs
- **Chunking** : les documents sont pré-chunkés par un pipeline Prefect (déjà intégré) ; le tool ne chunke pas à la volée

---

## 3. `llm_ops` — Observabilité & pilotage LLM

### Pourquoi
Langfuse est déjà intégré pour tracer les tools, mais l'agent ne peut pas l'interroger. Ces tools donnent au pôle data une fenêtre de pilotage : coûts par modèle, taux d'erreur des tools, traces lentes, prompts qui échouent — le tout sans quitter le chat.

### Tools envisagés
| Tool | Description |
|---|---|
| `lf_get_usage_summary` | Tokens consommés et coût estimé par modèle sur une période |
| `lf_list_traces` | Traces récentes filtrables (par tool, par statut, par durée > seuil) |
| `lf_get_trace` | Détail d'une trace (inputs, outputs, latence par étape, erreurs) |
| `lf_list_prompts` | Liste des prompts versionnés dans Langfuse |
| `lf_get_prompt` | Récupère un prompt versionné (texte + variables attendues) |
| `lf_get_scores` | Scores d'évaluation humains ou LLM-as-judge pour un dataset de traces |
| `lf_create_score` | Enregistre un score d'évaluation sur une trace (feedback humain) |

### Comment
- **Source** : Langfuse API REST (déjà configuré via `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY`)
- **Réutilisation directe** : les credentials Langfuse sont déjà dans `config.py` — aucune config supplémentaire
- **Cas d'usage concret** : l'agent peut auto-diagnostiquer ses propres latences et suggérer des optimisations de prompt

---

## 4. `data_quality` — Contrôle qualité des données

### Pourquoi
Les modèles ML sont aussi bons que les données qui les alimentent. Les capteurs IoT dérivent, les extractions ERP ont des trous, les jointures produisent des doublons. Ces tools exposent les résultats des checks de qualité (Great Expectations, dbt tests) pour que l'agent puisse alerter proactivement ou bloquer un pipeline avant une réinférence sur des données corrompues.

### Tools envisagés
| Tool | Description |
|---|---|
| `dq_run_checkpoint` | Déclenche un checkpoint Great Expectations et retourne le résultat |
| `dq_get_latest_results` | Résultats du dernier run de validation pour un dataset |
| `dq_list_failed_expectations` | Liste les expectations échouées avec valeurs observées vs attendues |
| `dq_get_data_profile` | Profil statistique d'une table (nulls %, distributions, cardinalités) |
| `dq_compare_runs` | Compare deux runs de validation pour détecter une régression qualité |
| `dq_get_dbt_test_results` | Résultats des tests dbt pour un modèle ou un tag |

### Comment
- **Source** : Great Expectations (Data Context local ou Cloud), dbt Cloud/Core via CLI ou API
- **Stockage des résultats** : JSON sur Azure Blob (déjà intégré) — le tool lit le dernier artefact
- **Intégration Prefect** : le checkpoint GE est appelé dans un flow Prefect ; le tool `dq_run_checkpoint` déclenche ce flow via `prefect_trigger_deployment` existant

---

## 5. `data_catalog` — Catalogue & lignage de données

### Pourquoi
Le pôle gère des dizaines de tables SQL, des datasets Parquet sur Azure Blob, des features calculées, des outputs de modèles. Sans catalogue, personne ne sait ce que contient `pump_sensor_agg_v3` ni d'où viennent les données qui alimentent le modèle de prédiction. Ces tools permettent à l'agent de répondre à "d'où vient cette donnée ?" et "qui consomme ce dataset ?".

### Tools envisagés
| Tool | Description |
|---|---|
| `catalog_search` | Recherche full-text dans le catalogue (tables, datasets, features, modèles) |
| `catalog_get_asset` | Fiche complète d'un asset (description, schéma, propriétaire, tags, SLA) |
| `catalog_get_lineage_upstream` | Lignage amont d'un asset (sources dont il dépend) |
| `catalog_get_lineage_downstream` | Lignage aval (qui consomme cet asset) |
| `catalog_list_by_tag` | Liste les assets par tag (`pii`, `ml_feature`, `production`, `deprecated`) |
| `catalog_update_description` | Met à jour la description ou les tags d'un asset |

### Comment
- **Source** : DataHub (open-source, self-hosted) ou Microsoft Purview selon l'infra Azure
- **dbt comme source de vérité** : le lignage des transformations SQL vient du `manifest.json` dbt exposé via DataHub
- **Read-heavy** : `catalog_update_description` est la seule opération d'écriture — nécessite un scope `catalog:write`

---

## 6. `feature_store` — Feature engineering & store

### Pourquoi
Les features pour les modèles ML (vibration RMS 24h, MTBF par modèle de pompe, tendance température roulement) sont coûteuses à calculer. Une feature store centralise ces calculs, garantit la cohérence train/serve, et permet à l'agent de récupérer les features d'un équipement pour une inférence à la demande.

### Tools envisagés
| Tool | Description |
|---|---|
| `fs_get_features` | Récupère les features d'une entité (équipement, site) pour une date donnée |
| `fs_list_feature_views` | Liste les feature views disponibles avec leur fréquence de calcul |
| `fs_get_feature_stats` | Statistiques de distribution d'une feature sur une période |
| `fs_detect_drift` | Détecte une dérive de distribution entre deux périodes (PSI, KS-test) |
| `fs_trigger_materialization` | Déclenche la matérialisation d'une feature view (via Prefect) |
| `fs_get_training_dataset` | Génère un dataset d'entraînement point-in-time correct pour un modèle |

### Comment
- **Source** : Feast (open-source) avec offline store sur Azure Blob (Parquet) et online store sur Redis
- **`fs_trigger_materialization`** : appelle `prefect_trigger_deployment` existant avec les bons paramètres
- **Point-in-time correctness** : capital pour éviter le data leakage — `fs_get_training_dataset` délègue à Feast qui gère cela nativement

---

## 7. `experiment_tracking` — Suivi des expériences ML

### Pourquoi
Les data scientists lancent des dizaines d'expériences pour chaque modèle (hyperparamètres, architectures, features). Ces tools permettent à l'agent de retrouver la meilleure expérience, de comparer des runs, ou de contextualiser pourquoi le modèle en production a ces métriques.

### Tools envisagés
| Tool | Description |
|---|---|
| `exp_list_experiments` | Liste les expériences MLflow (nom, date, nombre de runs) |
| `exp_list_runs` | Runs d'une expérience filtrables par métrique, tag, statut |
| `exp_get_run` | Détails d'un run (paramètres, métriques, tags, artefacts) |
| `exp_get_best_run` | Meilleur run d'une expérience selon une métrique (min ou max) |
| `exp_compare_runs` | Tableau comparatif de plusieurs runs sur leurs métriques clés |
| `exp_get_metric_history` | Courbe d'entraînement d'une métrique (loss par epoch) |

### Comment
- **Source** : MLflow Tracking Server (API REST, bien documentée)
- **Lien avec `ml_registry`** : un run MLflow peut être promu en version de modèle — les deux families se complètent
- **Read-only** : aucune opération d'écriture ici — les runs sont créés par le code d'entraînement, pas par l'agent

---

## 8. `pipeline_ops` — Opérations avancées sur les pipelines data

### Pourquoi
Prefect est déjà intégré (flows, runs, logs, deployments). Cette famille étend l'usage vers des patterns spécifiques data : déclencher une reingestion sur une plage de dates, surveiller un SLA de fraîcheur de données, rejouer un run échoué avec des paramètres corrigés.

### Tools envisagés
| Tool | Description |
|---|---|
| `pipeline_backfill` | Déclenche un backfill sur une plage de dates pour un pipeline donné |
| `pipeline_check_freshness` | Vérifie si une table/dataset est à jour selon son SLA (ex : < 2h) |
| `pipeline_list_sla_breaches` | Liste les datasets qui ont dépassé leur SLA de fraîcheur |
| `pipeline_retry_failed` | Rejoue les runs échoués d'un deployment sur les 24 dernières heures |
| `pipeline_get_dependency_graph` | Retourne le graphe de dépendances d'un pipeline (quels flows en amont/aval) |
| `pipeline_pause_schedule` | Met en pause le schedule d'un deployment (pour maintenance) |

### Comment
- **Source** : Prefect API (déjà intégré) — ces tools sont des wrappers de haut niveau sur les tools Prefect existants
- **`pipeline_check_freshness`** : compare `MAX(updated_at)` via le tool `sql` existant à l'heure courante
- **`pipeline_backfill`** : appelle `prefect_trigger_deployment` avec les paramètres `start_date` / `end_date`
- **Scope** : `pipeline:write` requis pour pause et retry

---

## 9. `bi_reporting` — Requêtage BI & indicateurs métier

### Pourquoi
Le pôle data publie des dashboards Power BI / Metabase pour les opérationnels. Ces tools permettent à l'agent de récupérer des métriques clés sans que l'utilisateur ouvre un dashboard, ou de détecter une anomalie sur un KPI avant que quelqu'un le remarque.

### Tools envisagés
| Tool | Description |
|---|---|
| `bi_get_kpi` | Valeur actuelle d'un KPI nommé (taux de pannes, MTTR, disponibilité parc) |
| `bi_get_kpi_trend` | Évolution d'un KPI sur une période (valeurs + variation %) |
| `bi_list_reports` | Liste les rapports publiés avec leur date de dernière actualisation |
| `bi_refresh_dataset` | Déclenche un refresh d'un dataset Power BI |
| `bi_get_alert_rules` | Liste les alertes configurées sur les dashboards et leur statut |
| `bi_export_data` | Exporte les données sous-jacentes d'un visuel en JSON |

### Comment
- **Source** : Power BI REST API (Azure AD OAuth2) ou Metabase API (token)
- **KPI nommés** : un fichier de configuration mappe les noms métier (`taux_pannes_q1`) aux requêtes DAX/SQL correspondantes — l'agent n'a pas à connaître les requêtes
- **`bi_refresh_dataset`** : utile après un backfill Prefect pour forcer la mise à jour du dashboard associé

---

## 10. `ai_eval` — Évaluation & benchmark des agents IA

### Pourquoi
Le pôle déploie plusieurs agents IA (assistant technique, agent sélection pompe, agent SAV). Il faut mesurer objectivement leur qualité : taux de réponse correcte, fidélité au contexte RAG, taux de hallucination, latence P95. Ces tools permettent de lancer des évaluations automatiques et de comparer deux versions d'un agent.

### Tools envisagés
| Tool | Description |
|---|---|
| `eval_run_benchmark` | Lance un benchmark sur un dataset de questions/réponses attendues |
| `eval_get_results` | Résultats d'un benchmark (scores par catégorie, exemples échoués) |
| `eval_compare_agents` | Compare deux agents (ou deux prompts) sur le même dataset |
| `eval_get_ragas_scores` | Métriques RAG (faithfulness, answer relevancy, context recall) via RAGAS |
| `eval_list_datasets` | Liste les datasets d'évaluation disponibles par domaine |
| `eval_add_example` | Ajoute un exemple au dataset d'évaluation (question + réponse de référence) |

### Comment
- **Framework** : RAGAS pour les métriques RAG, LangSmith ou Langfuse Datasets pour les datasets
- **Langfuse déjà intégré** : `eval_get_ragas_scores` écrit ses résultats comme scores Langfuse → visibles dans le dashboard existant
- **Déclenchement** : `eval_run_benchmark` déclenche un flow Prefect (déjà intégré) qui orchestre les appels LLM en batch

---

## Matrice de priorité

| Famille | Impact pôle data | Complexité impl. | Dépendances existantes | Priorité |
|---|---|---|---|---|
| `llm_ops` | Très élevé | Très faible | Langfuse déjà là | **P0** |
| `pipeline_ops` | Élevé | Très faible | Prefect déjà là | **P0** |
| `vector_store` | Très élevé | Faible | Azure Blob déjà là | **P0** |
| `data_quality` | Élevé | Moyenne | Prefect + Azure Blob | **P1** |
| `experiment_tracking` | Élevé | Faible | MLflow REST | **P1** |
| `ml_registry` | Élevé | Moyenne | MLflow / Azure ML | **P1** |
| `data_catalog` | Moyen | Moyenne | DataHub / Purview | **P2** |
| `bi_reporting` | Moyen | Faible | Power BI API | **P2** |
| `feature_store` | Élevé | Élevée | Feast + Redis | **P2** |
| `ai_eval` | Élevé | Moyenne | Langfuse + Prefect | **P2** |

---

## Architecture transversale du pôle data

```
Agent IA (Open WebUI / Claude)
         │
         ▼
    MCP Server (ce template)
         │
    ┌────┴─────────────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          ▼
[llm_ops]──────► Langfuse (déjà intégré)         [pipeline_ops]──► Prefect (déjà intégré)
[vector_store]─► Qdrant / Azure AI Search         [data_quality]─► GE → Azure Blob (déjà intégré)
[ml_registry]──► MLflow / Azure ML                [feature_store]► Feast + Azure Blob (déjà intégré)
[experiment_tracking]──► MLflow Tracking           [bi_reporting]─► Power BI API
[data_catalog]─► DataHub / Purview                [ai_eval]──────► RAGAS + Langfuse
```

### Principes à respecter pour le pôle data

- **Idempotence** : tous les tools de déclenchement (backfill, matérialisation, benchmark) doivent être idempotents — l'agent peut les appeler deux fois sans casser l'état.
- **Résultats bornés** : les tools qui retournent des séries temporelles ou des listes de runs doivent imposer `limit` par défaut (≤ 100 lignes) pour ne pas saturer le contexte de l'agent.
- **Pas de secrets dans les réponses** : les tools ne retournent jamais de clés API, tokens, ou données PII — filtrer à la sortie.
- **Versioning explicite** : chaque réponse incluant un modèle ou un prompt doit exposer sa version — l'agent a besoin de cette information pour des comparaisons reproductibles.
