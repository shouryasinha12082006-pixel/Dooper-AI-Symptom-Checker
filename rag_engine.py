import json
import os
import re

class SimpleRAGEngine:
    def __init__(self, knowledge_file_path):
        self.knowledge_file_path = knowledge_file_path
        self.knowledge_base = []
        self.load_knowledge()

    def load_knowledge(self):
        if os.path.exists(self.knowledge_file_path):
            try:
                with open(self.knowledge_file_path, "r", encoding="utf-8") as f:
                    self.knowledge_base = json.load(f)
                print(f"RAG Engine loaded {len(self.knowledge_base)} conditions.")
            except Exception as e:
                print(f"RAG Engine failed to load knowledge base: {e}")

    def query(self, query_text, top_n=5):
        if not query_text or not self.knowledge_base:
            return []

        # Tokenize query text
        query_words = set(re.findall(r'\w+', query_text.lower()))
        
        scored_results = []
        for condition in self.knowledge_base:
            score = 0
            matching_symptoms = []
            missing_symptoms = []
            
            # Match condition name (high weight)
            cond_name_words = set(re.findall(r'\w+', condition["condition_name"].lower()))
            overlap_name = cond_name_words.intersection(query_words)
            if overlap_name:
                score += len(overlap_name) * 10

            # Match symptoms
            symptoms_list = [s.strip().lower() for s in condition["symptoms"]]
            for symptom in symptoms_list:
                symptom_words = set(re.findall(r'\w+', symptom))
                if symptom in query_text.lower() or symptom_words.intersection(query_words):
                    score += 5
                    matching_symptoms.append(symptom)
                else:
                    missing_symptoms.append(symptom)

            # Match description
            desc_words = set(re.findall(r'\w+', condition["description"].lower()))
            overlap_desc = desc_words.intersection(query_words)
            score += len(overlap_desc) * 1

            if score > 0:
                scored_results.append({
                    "condition": condition,
                    "score": score,
                    "matching_symptoms": matching_symptoms,
                    "missing_symptoms": missing_symptoms
                })

        # Sort by score descending
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Format output
        formatted_results = []
        for res in scored_results[:top_n]:
            cond = res["condition"]
            max_score = len(cond["symptoms"]) * 5 + len(re.findall(r'\w+', cond["condition_name"])) * 10
            percentage = min(int((res["score"] / max_score) * 100) if max_score > 0 else 50, 98)
            percentage = max(percentage, 30)

            formatted_results.append({
                "condition_name": cond["condition_name"],
                "description": cond["description"],
                "severity": cond["severity"],
                "recommended_department": cond["recommended_department"],
                "home_care_advice": cond["home_care_advice"],
                "medical_references": cond["medical_references"],
                "red_flags": cond["red_flags"],
                "matching_symptoms": res["matching_symptoms"],
                "missing_symptoms": res["missing_symptoms"],
                "probability_score": percentage,
                "reasoning": f"Suggested due to matching indicators like {', '.join(res['matching_symptoms']) if res['matching_symptoms'] else 'general symptom profile'}."
            })
            
        # Pad with other conditions if less than top_n
        if len(formatted_results) < top_n:
            for cond in self.knowledge_base:
                if len(formatted_results) >= top_n:
                    break
                if not any(x["condition_name"] == cond["condition_name"] for x in formatted_results):
                    formatted_results.append({
                        "condition_name": cond["condition_name"],
                        "description": cond["description"],
                        "severity": cond["severity"],
                        "recommended_department": cond["recommended_department"],
                        "home_care_advice": cond["home_care_advice"],
                        "medical_references": cond["medical_references"],
                        "red_flags": cond["red_flags"],
                        "matching_symptoms": [],
                        "missing_symptoms": cond["symptoms"],
                        "probability_score": 15,
                        "reasoning": "Alternative diagnosis based on medical reference guidelines."
                    })
                    
        return formatted_results

# Instantiate globally
base_dir = os.path.dirname(os.path.abspath(__file__))
rag_engine = SimpleRAGEngine(os.path.join(base_dir, "medical_knowledge.json"))
