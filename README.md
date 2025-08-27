# A.U.R.A. - Amaravati Urban Resilience Agent

[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![IBM watsonx](https://img.shields.io/badge/IBM%20watsonx-0062FF?style=for-the-badge&logo=ibm&logoColor=white)](https://www.ibm.com/watsonx)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

A submission for the **IBM TechXchange "Sustainable Cities" Hackathon**. A.U.R.A. is a multi-agent AI system designed to create a "digital life-force" for a city, making complex urban data accessible and actionable through a Knowledge Graph and intelligent agents.

## 🎥 Demo Video

Watch the full project walkthrough and demonstration on YouTube:

[![Project A.U.R.A. Demo](https://img.youtube.com/vi/rhjdCUSwMks/0.jpg)](https://youtu.be/rhjdCUSwMks)

**([Click to Watch](https://youtu.be/rhjdCUSwMks))**

---

## 🏙️ About the Project

The core concept is to build an AI Agentic Environment that allows users to easily access city information and generate reports on urban development and infrastructure progress. The project is conceptualized around the **Amaravati Capital City project**, an ambitious plan for a new capital for the Indian state of Andhra Pradesh.

A.U.R.A. transforms complex, siloed city data into a structured, interconnected Knowledge Graph, which can then be queried by a collaborative multi-agent system powered by IBM watsonx Orchestrate.

## ⚙️ Architecture and Workflow

The system is built on a robust pipeline that converts raw geospatial data into an intelligent, queryable knowledge base.

### 1. Ontology & Knowledge Graph Creation
* **Ontology Schema**: The foundation is a custom ontology schema named **ADTO (Amaravati Digital Twin Ontology)**, which formally defines the entities of a city (buildings, roads, pipes) and the relationships between them.
* **Technology**: The schema was developed using the `rdflib` library in Python.

### 2. Data Ingestion & Transformation
* **Data Source**: The initial data is sourced from the official Amaravati master plan.
* **Extraction**: **QGIS**, an open-source GIS software, was used to extract map data into GeoJSON format, focusing on the road network, water supply system, and official zoning for this demo.
* **Conversion**: A Python program ingests the GeoJSON data and maps it to the ADTO schema, creating a semantically structured RDF graph. The final knowledge graph is saved in the **Turtle (.ttl)** format.

### 3. Backend Infrastructure
* **Database Server**: **Apache Jena Fuseki** is used to host the knowledge graph. It provides a **SPARQL endpoint**, which allows the AI agents to query the graph directly using the SPARQL language.
* **API Server**: A **FastAPI** server acts as an intelligent middle layer. It simplifies queries by providing clean APIs for the agents and is capable of performing advanced GeoAnalytics on the data retrieved from the graph.

### 4. AI Agentic Environment
* **Platform**: The entire agentic system is built using the **IBM watsonx Orchestrate ADK (Application Development Kit)**. The ADK allows for the creation of agents and tools based on a standard OpenAPI specification.
* **Multi-Agent System**: A.U.R.A. is not a single agent but a collaborative system where different agents perform specialized tasks. A key component is the `Knowledge_graph_service_agent`, which acts as an expert on the database structure, helping other agents generate accurate SPARQL queries.

### 5. User Interface
* **WhatsApp Integration**: Instead of a traditional chat platform, the A.U.R.A. agent is connected directly to **WhatsApp**. This allows citizens and city planners to interact with the powerful backend simply by sending a message.

## 🛠️ Technologies Used

* **AI Platform**: IBM watsonx Orchestrate ADK
* **Programming Language**: Python
* **Knowledge Graph**: RDFlib, Apache Jena Fuseki, SPARQL
* **API Framework**: FastAPI
* **GIS**: QGIS
* **Data Formats**: GeoJSON, Turtle (.ttl), OpenAPI Specification

## 🚀 Future Scope

While this demo focuses on road networks, water supply, and zoning, the system is designed to be scalable. Future work can include:
* Ingesting more diverse datasets (e.g., real-time sensor data, public transport schedules, energy consumption).
* Enhancing the Knowledge Graph Question Answering (KGQA) capabilities for more natural and complex user queries.
* Developing more specialized agents for different urban domains like traffic management, disaster response, and energy distribution.
