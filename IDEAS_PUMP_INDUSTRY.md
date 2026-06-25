# Idées de familles de tools MCP — Industriel Pompes

> Contexte : un serveur MCP exposé à un agent IA (Claude, Open WebUI…) pour automatiser et augmenter les métiers d'une entreprise industrielle spécialisée dans les pompes (fabrication, distribution, maintenance, SAV).

---

## 1. `pump_catalog` — Catalogue produit & sélection technique

### Pourquoi
Le cœur du métier. Les commerciaux et ingénieurs passent des heures à chercher la bonne pompe pour une application. Un agent équipé de ces tools peut faire la sélection automatiquement à partir des contraintes client (débit, HMT, fluide, température…).

### Tools envisagés
| Tool | Description |
|---|---|
| `search_pumps` | Recherche dans le catalogue par critères hydrauliques (Q, H, viscosité, DN…) |
| `get_pump_datasheet` | Retourne la fiche technique complète d'un modèle (courbe, matériaux, poids) |
| `get_pump_curve` | Récupère les données de courbe Q/H pour un modèle et une vitesse |
| `compare_pumps` | Compare deux ou plusieurs modèles sur des critères pondérés |
| `get_spare_parts` | Liste les pièces de rechange associées à un modèle |
| `check_availability` | Vérifie le stock ou le délai d'approvisionnement d'un modèle |

### Comment
- **Source** : ERP (SAP, Sage…) via API REST ou requêtes SQL directes sur la base produits
- **Format** : JSON structuré avec unités SI, plus chemin vers les PDFs datasheet stockés sur Azure Blob ou S3
- **Réutilisation** : s'appuie sur la famille `sql` (déjà présente) et `azure_blob` (déjà présente) du template

---

## 2. `hydraulic_calc` — Calculs hydrauliques

### Pourquoi
Les ingénieurs d'application font des calculs répétitifs : pertes de charge, point de fonctionnement, NPSH, puissance absorbée. Les formaliser en tools permet à l'agent de les exécuter à la demande dans un devis ou une étude.

### Tools envisagés
| Tool | Description |
|---|---|
| `calc_head_loss` | Calcul des pertes de charge (Darcy-Weisbach, longueur, diamètre, rugosité) |
| `calc_operating_point` | Intersection courbe pompe / courbe réseau |
| `calc_npsh_available` | Calcul du NPSHd côté installation |
| `calc_power` | Puissance absorbée et rendement pour un point de fonctionnement |
| `calc_affinity_laws` | Lois de similitude : effet d'un changement de vitesse ou de diamètre de roue |
| `unit_convert` | Conversion d'unités (bar↔mCE, m³/h↔l/s, kW↔CV…) |

### Comment
- **Implémentation** : pure Python, aucune dépendance externe — formules standardisées ISO
- **Entrée/sortie** : paramètres typés (Pydantic), résultats avec unités explicites
- **Extension** : peut intégrer la lib `fluids` (PyPI) pour les fluides non-newtoniens

---

## 3. `maintenance` — Gestion de la maintenance (GMAO)

### Pourquoi
Les équipes maintenance gèrent des milliers de pompes sur site client. Un agent peut consulter l'historique, créer des ordres de travail, identifier les récidives de pannes et anticiper les remplacements.

### Tools envisagés
| Tool | Description |
|---|---|
| `get_equipment` | Fiche équipement d'une pompe installée (tag, site, date pose, modèle) |
| `get_maintenance_history` | Historique des interventions sur un équipement |
| `create_work_order` | Création d'un ordre de travail dans la GMAO |
| `update_work_order` | Mise à jour statut / compte-rendu d'intervention |
| `get_pending_orders` | Liste des OT ouverts pour un site ou un technicien |
| `schedule_preventive` | Planifie une maintenance préventive selon les préconisations constructeur |
| `get_failure_analysis` | Analyse les modes de défaillance récurrents sur un parc |

### Comment
- **Source** : GMAO (CARL, Infor EAM, SAP PM…) via API REST ou connecteur SQL
- **Sécurité** : les tools de création/modification exigent un scope auth spécifique (`maintenance:write`)
- **Pattern** : reprendre le pattern sessions de `azure_devops` pour les connexions GMAO authentifiées

---

## 4. `iot_monitoring` — Télésurveillance & capteurs IoT

### Pourquoi
Les pompes industrielles sont de plus en plus équipées de capteurs (vibration, température, pression, débit). Un agent peut interroger ces données en temps réel pour détecter des anomalies, corréler une panne avec une dérive de paramètre, ou déclencher une alerte.

### Tools envisagés
| Tool | Description |
|---|---|
| `get_live_telemetry` | Valeurs temps réel d'un équipement (dernière mesure capteurs) |
| `get_telemetry_history` | Série temporelle sur une plage de dates |
| `detect_anomalies` | Détection de dépassements de seuils ou de dérives |
| `get_alarm_log` | Journal des alarmes actives et passées |
| `acknowledge_alarm` | Acquittement d'une alarme depuis l'agent |
| `get_vibration_spectrum` | Analyse spectrale des vibrations (FFT) pour diagnostic roulement |

### Comment
- **Source** : plateforme IoT (Azure IoT Hub, InfluxDB, OSIsoft PI, Timescale)
- **Transport** : appels REST ou requêtes InfluxQL/TimescaleDB via le tool `sql` existant adapté
- **Limites** : données temps réel → timeouts courts (5s), pagination obligatoire sur l'historique

---

## 5. `field_service` — Gestion des techniciens terrain (SAV)

### Pourquoi
Le SAV pompes implique des techniciens itinérants avec des interventions urgentes. Un agent peut aider à dispatcher, préparer les interventions (pièces, docs techniques), et saisir les rapports post-intervention par dictée.

### Tools envisagés
| Tool | Description |
|---|---|
| `list_interventions` | Liste les interventions planifiées pour un technicien / une zone |
| `get_intervention_detail` | Détail d'une intervention (client, équipement, symptôme, pièces réservées) |
| `update_intervention_report` | Saisit le rapport d'intervention (travaux réalisés, pièces posées, temps) |
| `get_nearest_technician` | Trouve le technicien disponible le plus proche d'un site |
| `reserve_spare_part` | Réserve une pièce du stock pour une intervention |
| `generate_intervention_pdf` | Génère le bon d'intervention signable au format PDF |

### Comment
- **Source** : FSM (Field Service Management) — ServiceMax, Microsoft Field Service, Salesforce FSM
- **Géolocalisation** : API Google Maps ou Azure Maps pour `get_nearest_technician`
- **PDF** : lib `weasyprint` ou appel à un service de génération de documents

---

## 6. `regulatory_compliance` — Conformité réglementaire & certification

### Pourquoi
Le secteur pompes est soumis à de nombreuses normes (ATEX, PED, ISO 9906, ErP/Ecodesign). Un agent peut vérifier la conformité d'un produit, retrouver les déclarations CE, ou préparer un dossier technique.

### Tools envisagés
| Tool | Description |
|---|---|
| `get_certifications` | Liste les certifications d'un modèle (ATEX, CE, UL, WRAS…) |
| `check_erp_compliance` | Vérifie la conformité ErP/Ecodesign (classes efficacité MEI, EEI) |
| `get_declaration_of_conformity` | Retourne le PDF de la déclaration de conformité CE |
| `check_atex_classification` | Valide si un modèle est adapté à une zone ATEX donnée |
| `get_material_certificates` | Certificats matière (EN 10204 3.1) pour les composants en contact fluide |
| `search_standards` | Recherche dans la base de normes applicables à un type d'équipement |

### Comment
- **Source** : GED/Docuware (déjà intégré dans ce template !) + base de données interne certifications
- **Pattern** : s'appuyer directement sur `docuware` existant pour la récupération de documents
- **Mise à jour** : pipeline de veille réglementaire (Prefect, déjà intégré) qui alimente la base

---

## 7. `customer_portal` — Données client & CRM

### Pourquoi
Les commerciaux ont besoin d'accéder rapidement à l'historique client, aux contrats de maintenance, aux devis en cours. Un agent CRM permet de préparer une visite, de suivre un compte, ou de déclencher des actions commerciales.

### Tools envisagés
| Tool | Description |
|---|---|
| `get_customer` | Fiche client (coordonnées, secteur, CA, interlocuteurs) |
| `get_customer_equipment` | Parc installé chez un client |
| `get_quotes` | Devis en cours ou historique pour un client |
| `create_quote` | Initialise un devis depuis un besoin exprimé |
| `get_contracts` | Contrats de maintenance actifs (périmètre, SLA, échéances) |
| `get_customer_tickets` | Tickets SAV ouverts ou récents pour un client |
| `log_customer_interaction` | Enregistre un compte-rendu de visite ou d'appel dans le CRM |

### Comment
- **Source** : CRM (Salesforce, HubSpot, Microsoft Dynamics) via API REST
- **Auth** : OAuth2 Client Credentials (supporté nativement par ce template)
- **Données sensibles** : masquage des informations financières selon le rôle de l'utilisateur

---

## 8. `energy_efficiency` — Audit énergétique & optimisation

### Pourquoi
La réglementation et les enjeux de coût poussent les industriels à optimiser leur consommation. Un agent peut identifier les pompes surdimensionnées, calculer le ROI d'un variateur de vitesse, ou prioriser les remplacements par économie d'énergie.

### Tools envisagés
| Tool | Description |
|---|---|
| `calc_energy_consumption` | Calcule la consommation annuelle d'une pompe (kWh, €) |
| `calc_vsd_savings` | Économies potentielles avec un variateur de vitesse (lois des similitudes) |
| `audit_pump_efficiency` | Compare le point de fonctionnement réel vs point best efficiency (BEP) |
| `rank_replacement_priority` | Classe un parc par ordre de priorité de remplacement (économies vs coût) |
| `calc_co2_footprint` | Empreinte carbone d'un système de pompage |
| `get_energy_benchmark` | Benchmark consommation vs parc similaire / secteur industriel |

### Comment
- **Source** : données IoT (consommation électrique) + catalogue produits (courbes rendement)
- **Réutilisation** : combine `iot_monitoring` (consommation réelle) + `hydraulic_calc` (point BEP)
- **Output** : rapport structuré avec recommandations priorisées, prêt à intégrer dans un devis

---

## 9. `procurement` — Achats & chaîne d'approvisionnement

### Pourquoi
Les délais et coûts d'approvisionnement des pièces détachées et composants sont critiques. Un agent peut interroger les stocks, comparer les fournisseurs, et automatiser les demandes d'achat pour les besoins récurrents.

### Tools envisagés
| Tool | Description |
|---|---|
| `get_stock_level` | Niveau de stock d'un article (entrepôt central + dépôts régionaux) |
| `get_reorder_suggestions` | Articles sous seuil de réapprovisionnement |
| `create_purchase_request` | Crée une demande d'achat dans l'ERP |
| `get_supplier_lead_times` | Délais fournisseurs pour un article |
| `compare_suppliers` | Compare prix et délais sur plusieurs fournisseurs pour un article |
| `get_pending_orders` | Commandes fournisseurs en attente de livraison |

### Comment
- **Source** : ERP (SAP MM, Sage Achats) via API ou requêtes SQL
- **Automatisation** : Prefect (déjà intégré) peut déclencher des demandes d'achat automatiques quand le stock descend sous seuil
- **Sécurité** : `procurement:write` scope requis pour la création de demandes d'achat

---

## 10. `technical_documentation` — Base documentaire technique

### Pourquoi
Manuels d'installation, schémas de principe, notes de calcul, retours d'expérience : la documentation technique est dispersée et souvent difficile à retrouver. Un agent documentaire permet de répondre instantanément à des questions techniques en s'appuyant sur le bon document.

### Tools envisagés
| Tool | Description |
|---|---|
| `search_docs` | Recherche plein-texte dans la base documentaire (manuels, notes, plans) |
| `get_installation_manual` | Récupère le manuel d'installation d'un modèle (PDF ou chunks texte) |
| `get_troubleshooting_guide` | Guide de dépannage pour un symptôme ou un modèle |
| `get_drawing` | Récupère un plan (P&ID, coupe, encombrement) par référence |
| `list_documents` | Liste les documents disponibles pour un produit ou un projet |
| `get_revision_history` | Historique des révisions d'un document |

### Comment
- **Source** : GED Docuware (déjà intégré !), SharePoint, ou base vectorielle (Qdrant, Azure AI Search)
- **RAG** : les tools `search_docs` et `get_troubleshooting_guide` peuvent alimenter un pipeline RAG pour des réponses contextuelles
- **Format** : retourner des chunks texte plutôt que des PDFs complets pour une meilleure exploitation par l'agent

---

## Matrice de priorité suggérée

| Famille | Impact métier | Complexité impl. | Priorité |
|---|---|---|---|
| `pump_catalog` | Très élevé | Moyenne | P0 |
| `hydraulic_calc` | Élevé | Faible | P0 |
| `technical_documentation` | Élevé | Faible (Docuware déjà dispo) | P0 |
| `maintenance` | Élevé | Moyenne | P1 |
| `customer_portal` | Élevé | Moyenne | P1 |
| `field_service` | Moyen | Élevée | P1 |
| `iot_monitoring` | Élevé | Élevée | P2 |
| `energy_efficiency` | Moyen | Faible (calculs) | P2 |
| `regulatory_compliance` | Moyen | Faible (Docuware déjà dispo) | P2 |
| `procurement` | Moyen | Moyenne | P2 |

---

## Notes d'architecture transversales

- **Réutilisation maximale** : `pump_catalog`, `technical_documentation`, et `regulatory_compliance` s'appuient sur `docuware`, `azure_blob`, et `sql` déjà présents dans le template — coût de développement minimal.
- **Sécurité** : les tools d'écriture (`create_work_order`, `create_purchase_request`…) doivent exiger un scope auth dédié pour éviter les actions non souhaitées par l'agent.
- **Pagination** : tout tool retournant une liste doit supporter `limit` et `offset` pour éviter des réponses trop volumineuses pour le contexte de l'agent.
- **Unités explicites** : systématiquement inclure les unités dans les réponses JSON (`"flow_rate": {"value": 45.2, "unit": "m3/h"}`) pour éviter les erreurs de conversion par l'agent.
