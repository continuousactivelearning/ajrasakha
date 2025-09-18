from typing import List
from llama_index.core import VectorStoreIndex
from llama_index.core.base.base_retriever import BaseRetriever
from llama_index.vector_stores.mongodb import MongoDBAtlasVectorSearch
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.schema import BaseNode, NodeWithScore
from constants import DB_NAME, EMBEDDING_MODEL, INDEX_NAME
from pymongo import MongoClient

from models import ContextPOP, ContextQuestionAnswerPair, POPMetaData, QuestionAnswerPairMetaData

def get_retriever(client: MongoClient, collection_name: str, similarity_top_k: int = 3) -> BaseRetriever:
    embed_model= HuggingFaceEmbedding(model_name=EMBEDDING_MODEL, cache_folder="./hf_cache", trust_remote_code=True)
    vector_store = MongoDBAtlasVectorSearch(
        client,
        db_name=DB_NAME,
        collection_name=collection_name,
        vector_index_name=INDEX_NAME,
        embedding_key="embedding",
        text_key="text",
        metadata_key="metadata",
    )
    index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
    retriever = index.as_retriever(similarity_top_k=similarity_top_k)
    return retriever



async def process_nodes_qa(nodes: List[NodeWithScore]) -> List[ContextQuestionAnswerPair]:
    # Your stored format: "Question: ...\n\nAnswer: ..."
    context: List[ContextQuestionAnswerPair] = []
    for node in nodes:
        text=node.text
        q, a = text, ""
        if "\n\nAnswer:" in text:
            parts = text.split("\n\nAnswer:", 1)
            q = parts[0].replace("Question:", "", 1).strip()
            a = parts[1].strip()
        
        question_answer_pair=ContextQuestionAnswerPair(
            question=q,
            answer=a,
            meta_data=QuestionAnswerPairMetaData(
                agri_specialist=node.metadata.get("Agri Specialist", "Not Available"),
                crop=node.metadata.get("Crop", "Not Available"),
                sources=node.metadata.get("Source [Name and Link]", "Source Not Available"),
                state=node.metadata.get("State", "Not Available"),
                similarity_score=node.score 
            )
        )
        context.append(question_answer_pair)
    return context




async def process_nodes_pop(nodes: List[NodeWithScore]) -> List[ContextPOP]:
    # Your stored format: "Question: ...\n\nAnswer: ..."
    context: List[ContextPOP] = []
    for node in nodes:
        question_answer_pair=ContextPOP(
            text=node.text,
            meta_data=POPMetaData(
                page_no=node.metadata.get("page_no", "Not Available"),
                source=node.metadata.get("source", "https://linknotavailable.com"),
                topics=node.metadata.get("headings", "No topics available"),
                similarity_score=node.score
            )
        )
        context.append(question_answer_pair)
    return context



def _truncate(text: str, max_len: int = 300) -> str:
    """Helper to truncate long text safely."""
    return text if len(text) <= max_len else text[:max_len].rstrip() + "..."


async def render_qa_markdown(results: List[ContextQuestionAnswerPair], truncate:bool = True, max_len: int = 300) -> str:
    """Render ContextQuestionAnswerPair objects into Markdown with truncation."""
    md_output = []
    for r in results:
        question = _truncate(r.question, max_len) if truncate else r.question
        answer = _truncate(r.answer if r.answer else "Answer not available", max_len) if truncate else r.answer

        md_output.append(f"""### ❓Golden Dataset Question
{question}

### ✅ Answer
{answer}

**Metadata**
- 👨‍🌾 Agri Specialist: {r.meta_data.agri_specialist}
- 🌱 Crop: {r.meta_data.crop}
- 📖 Source: {r.meta_data.sources}
- 🏞 State: {r.meta_data.state}
- 🔗 Similarity Score: {r.meta_data.similarity_score:.2f}
---
""")
    return "\n".join(md_output)


async def render_pop_markdown(results: List[ContextPOP], truncate: bool= True, max_len: int = 300) -> str:
    """Render ContextPOP objects into Markdown with truncation."""
    md_output = []
    for r in results:
        text = _truncate(r.text, max_len) if truncate else r.text

        md_output.append(f"""### 📄 POP Reference
**Text**  
{text}

**Metadata**
- 📑 Page No: {r.meta_data.page_no}
- 📖 Source: {r.meta_data.source}
- 🏷 Topics: {r.meta_data.topics}
- 🔗 Similarity Score: {r.meta_data.similarity_score:.2f}
---
""")
    return "\n".join(md_output)
