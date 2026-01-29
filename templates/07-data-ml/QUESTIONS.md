# 📋 Data/ML Pipeline - Projekt-Fragebogen
## Template: 07-data-ml (Python + Jupyter + scikit-learn)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **Projekt Name** | |
| **Problem-Typ** | Classification, Regression, Clustering, NLP |
| **Datenquelle** | CSV, Database, API, Streaming |

---

## A. PROBLEM DEFINITION

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| A1 | Was ist das Ziel? | Vorhersage, Klassifikation, Anomaly Detection | |
| A2 | Target Variable? | Was wird vorhergesagt | |
| A3 | Erfolgsmetrik? | Accuracy, F1, RMSE, AUC | |
| A4 | Baseline? | Aktuelle Methode/Performance | |
| A5 | Business Impact? | Was bedeutet 1% Verbesserung | |

---

## B. DATEN

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Datenquelle(n)? | CSV, PostgreSQL, API, S3 | |
| B2 | Datenmenge? | Rows, GB | |
| B3 | Update-Frequenz? | Einmalig, Täglich, Streaming | |
| B4 | Datenqualität? | Missing Values, Outliers | |
| B5 | Sensible Daten? | PII, DSGVO-relevant | |
| B6 | Features bekannt? | Oder Feature Engineering nötig | |

---

## C. ML PROBLEM TYP

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| C1 | Supervised/Unsupervised? | [ ] Supervised [ ] Unsupervised [ ] Semi-supervised | |
| C2 | Klassifikation? | [ ] Binary [ ] Multi-class [ ] Multi-label | |
| C3 | Regression? | [ ] Linear [ ] Non-linear [ ] Time Series | |
| C4 | Clustering? | [ ] K-Means [ ] DBSCAN [ ] Hierarchical | |
| C5 | NLP? | [ ] Classification [ ] NER [ ] Summarization [ ] Embedding | |
| C6 | Computer Vision? | [ ] Classification [ ] Detection [ ] Segmentation | |

---

## D. TECH-STACK ENTSCHEIDUNGEN

### Data Processing

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D1 | Data Processing? | [ ] pandas (default) [ ] Polars [ ] Dask | |
| D2 | Feature Engineering? | [ ] Manual [ ] Feature-engine [ ] tsfresh (time series) | |
| D3 | Data Validation? | [ ] pandera [ ] Great Expectations [ ] Custom | |

### ML Framework

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D4 | ML Framework? | [ ] scikit-learn (default) [ ] XGBoost [ ] LightGBM [ ] CatBoost | |
| D5 | Deep Learning? | [ ] Nein [ ] PyTorch [ ] TensorFlow [ ] Keras | |
| D6 | AutoML? | [ ] Nein [ ] FLAML [ ] AutoGluon [ ] H2O | |
| D7 | Hyperparameter Tuning? | [ ] GridSearch [ ] Optuna [ ] Ray Tune | |

### Experiment Tracking

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D8 | Experiment Tracking? | [ ] Keins [ ] MLflow [ ] Weights & Biases [ ] Neptune | |
| D9 | Model Registry? | [ ] Keins [ ] MLflow [ ] DVC | |
| D10 | Reproducibility? | [ ] Seeds [ ] DVC Pipelines [ ] Kedro | |

### Visualization

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| D11 | Visualization? | [ ] matplotlib [ ] plotly [ ] seaborn [ ] Altair | |
| D12 | Interactive Dashboards? | [ ] Nein [ ] Streamlit [ ] Gradio [ ] Panel | |

---

## E. DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Deployment Target? | [ ] Jupyter only [ ] API [ ] Batch [ ] Edge | |
| E2 | Model Serving? | [ ] FastAPI [ ] BentoML [ ] Seldon [ ] SageMaker | |
| E3 | Containerisierung? | [ ] Docker [ ] None | |
| E4 | Orchestrierung? | [ ] None [ ] Airflow [ ] Prefect [ ] Dagster | |
| E5 | Model Format? | [ ] Pickle [ ] ONNX [ ] PMML | |

---

## F. PERFORMANCE REQUIREMENTS

| # | Frage | Antwort |
|---|-------|---------|
| F1 | Inference Latenz? | <100ms, <1s, <10s |
| F2 | Throughput? | Requests/Second |
| F3 | Model Size Limit? | MB |
| F4 | Hardware? | CPU, GPU, TPU |
| F5 | Memory Limit? | GB |

---

## G. MONITORING & RETRAINING

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| G1 | Model Monitoring? | [ ] Nein [ ] Evidently [ ] Arize [ ] Fiddler | |
| G2 | Data Drift Detection? | [ ] Nein [ ] Evidently [ ] Custom | |
| G3 | Retraining Trigger? | [ ] Scheduled [ ] Drift-based [ ] Manual | |
| G4 | A/B Testing? | [ ] Nein [ ] Ja | |

---

## H. DEVELOPMENT ENVIRONMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Notebook Environment? | [ ] Jupyter Lab [ ] VS Code [ ] Colab [ ] SageMaker | |
| H2 | Package Manager? | [ ] pip + venv [ ] Poetry [ ] Conda | |
| H3 | Testing? | [ ] pytest [ ] unittest | |
| H4 | Code Quality? | [ ] ruff [ ] black + isort [ ] None | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Data Loading Pipeline
- [ ] Feature Engineering
- [ ] Model Training Script
- [ ] Evaluation Metrics
- [ ] Prediction API
- [ ] Jupyter Notebooks
- [ ] Docker Setup
- [ ] MLflow Integration

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "07-data-ml",
  "data": {
    "processing": "pandas",
    "validation": "pandera",
    "storage": "PostgreSQL / S3"
  },
  "ml": {
    "framework": "scikit-learn",
    "deep_learning": "PyTorch (optional)",
    "tuning": "Optuna"
  },
  "experiment": {
    "tracking": "MLflow",
    "visualization": "plotly"
  },
  "deployment": {
    "api": "FastAPI",
    "serving": "Docker",
    "orchestration": "Airflow"
  }
}
```
