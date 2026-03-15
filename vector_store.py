import os
import chromadb
from chromadb.utils import embedding_functions

class VectorStore:
    """ChromaDB-backed vector store for semantic email search (RAG retrieval layer)."""
    
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        
        # Use ChromaDB's default embedding: all-MiniLM-L6-v2 (~80MB, auto-downloads)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        self.collection = self.client.get_or_create_collection(
            name="promotional_emails",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_email(self, email_id: str, subject: str, sender: str, 
                  body_text: str, date_received: str, account_email: str = ""):
        """Embeds and stores a single email. Skips if already indexed."""
        # Check if already in ChromaDB
        existing = self.collection.get(ids=[email_id])
        if existing and existing['ids']:
            return
        
        # Create embedding text: subject + truncated body
        embed_text = f"{subject}\n{body_text[:1000]}" if body_text else subject
        
        self.collection.add(
            ids=[email_id],
            documents=[embed_text],
            metadatas=[{
                "subject": subject or "",
                "sender": sender or "",
                "date_received": str(date_received) if date_received else "",
                "account_email": account_email
            }]
        )
    
    def search(self, query: str, top_k: int = 15) -> list[dict]:
        """Semantic similarity search. Returns top_k most relevant email metadata."""
        if self.collection.count() == 0:
            return []
        
        # Don't request more results than we have documents
        actual_k = min(top_k, self.collection.count())
        
        results = self.collection.query(
            query_texts=[query],
            n_results=actual_k,
            include=["documents", "metadatas", "distances"]
        )
        
        output = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i] if results['metadatas'] else {}
                doc = results['documents'][0][i] if results['documents'] else ""
                distance = results['distances'][0][i] if results['distances'] else 0
                
                output.append({
                    "email_id": doc_id,
                    "subject": meta.get("subject", ""),
                    "sender": meta.get("sender", ""),
                    "date_received": meta.get("date_received", ""),
                    "body_preview": doc[:1500],
                    "similarity": round(1 - distance, 3)  # cosine: 1=identical, 0=unrelated
                })
        
        return output
    
    def count(self) -> int:
        """Returns total number of indexed emails."""
        return self.collection.count()
    
    def reindex_from_db(self, db_manager):
        """Re-indexes all emails from SQLite into ChromaDB."""
        from models import RawEmailModel
        with db_manager.get_session() as session:
            emails = session.query(RawEmailModel).all()
            indexed = 0
            for email in emails:
                self.add_email(
                    email_id=email.email_id,
                    subject=email.subject,
                    sender=email.sender,
                    body_text=email.body_text or "",
                    date_received=str(email.date_received) if email.date_received else "",
                    account_email=email.account_email
                )
                indexed += 1
            return indexed
